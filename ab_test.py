#!/usr/bin/env python3
"""Deterministic paired tournament evaluation; no decision timers in workers.

python3 ab_test.py --tables 10000 --baseline versions.my_bot_v6 --candidate my_bot
All three payout vectors rescore the SAME trajectories. Policies receive TOP3
unless --policy-payout is supplied; this isolates scoring sensitivity.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import statistics
import shutil
import time

from simulator import Tournament
from opponent_bots import POOLS
from tournament_scoring import PAYOUTS, BLIND_GROWTH

ROOT = Path(__file__).resolve().parent
ENGINE_FILES = ('simulator.py', 'opponent_bots.py', 'poker_eval.py',
                'tournament_scoring.py', 'versions/my_bot_v2.py', 'versions/my_bot_v6.py')


def fingerprint(module):
    h = hashlib.sha256()
    h.update(module.encode())  # Identical A/B modules still run independently.
    source = ROOT / (module.replace('.', '/') + '.py')
    extra = tuple(name + '.py' for name in ('preflop_equity', 'push_fold_chart', 'hu_nash')
                  if name in source.read_text())
    for name in (*ENGINE_FILES, str(source.relative_to(ROOT)), *extra):
        path = ROOT / name
        if path.exists():
            h.update(path.read_bytes())
    return h.hexdigest()[:20]


def worker(task):
    module, pool, schedule, policy_payout, seeds = task
    cls = importlib.import_module(module).MyBot
    rows = []
    for seed in seeds:
        t = Tournament(seed, hero_class=cls, pool=pool, blind_schedule=schedule,
                       payouts=policy_payout, measure_timing=False)
        result = t.run()
        rows.append((seed, result.probabilities()['my_bot'],
                     t.errors['my_bot'], t.illegal['my_bot'], t.hand_number,
                     len(result.survivors)))
    return pool, schedule, rows


def alias_cache(source, target):
    """Reuse completed trajectories when archiving a byte-identical winner."""
    if (ROOT / (source.replace('.', '/') + '.py')).read_bytes() != (
            ROOT / (target.replace('.', '/') + '.py')).read_bytes():
        raise ValueError('Only byte-identical strategy archives may share cache')
    old = ROOT / 'results' / 'cache' / fingerprint(source)
    new = ROOT / 'results' / 'cache' / fingerprint(target)
    new.mkdir(parents=True, exist_ok=True)
    for path in old.glob('*.json'):
        shutil.copyfile(path, new / path.name)


def run_module(module, args, executor):
    digest = fingerprint(module)
    directory = ROOT / 'results' / 'cache' / digest
    directory.mkdir(parents=True, exist_ok=True)
    data, pending, paths = {}, {}, {}
    for pool in args.pools:
        for schedule in args.schedules:
            key = pool, schedule
            path = directory / f'{pool}_{schedule}_{args.policy_payout}_{args.seed}_{args.tables}.json'
            paths[key] = path
            if path.exists():
                data[key] = json.loads(path.read_text())
            else:
                data[key] = []
                for start in range(args.seed, args.seed + args.tables, args.chunk):
                    task = (module, pool, schedule, args.policy_payout,
                            list(range(start, min(start + args.chunk, args.seed + args.tables))))
                    pending[executor.submit(worker, task)] = key
    print(f'{module} {digest}: {len(pending)} batches to run', flush=True)
    last = time.monotonic()
    done = 0
    for future in as_completed(pending):
        pool, schedule, rows = future.result()
        key = pool, schedule
        data[key].extend(rows)
        done += len(rows)
        if len(data[key]) == args.tables:
            data[key].sort(key=lambda row: row[0])
            paths[key].write_text(json.dumps(data[key], separators=(',', ':')))
        if time.monotonic() - last > 25:
            print(f'{module}: {done:,} newly simulated tables complete', flush=True)
            last = time.monotonic()
    return data


def summarize(a, b, n):
    rows = []
    for pool, schedule in a:
        left, right = a[pool, schedule], b[pool, schedule]
        assert len(left) == len(right) == n
        assert all(x[0] == y[0] for x, y in zip(left, right))
        for payout, awards in PAYOUTS.items():
            score = lambda row: sum(p * v for p, v in zip(row[1], awards))
            x, y = list(map(score, left)), list(map(score, right))
            delta = [v - u for u, v in zip(x, y)]
            se = statistics.stdev(delta) / math.sqrt(n) if n > 1 else 0
            rows.append(dict(pool=pool, blinds=schedule, payout=payout, tables=n,
                             baseline=statistics.mean(x), candidate=statistics.mean(y),
                             difference=statistics.mean(delta), se=se,
                             baseline_errors=sum(r[2] for r in left),
                             candidate_errors=sum(r[2] for r in right),
                             baseline_illegal=sum(r[3] for r in left),
                             candidate_illegal=sum(r[3] for r in right)))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tables', type=int, default=10000)
    parser.add_argument('--seed', type=int, default=100001)
    parser.add_argument('--baseline', default='versions.my_bot_v6')
    parser.add_argument('--candidate', default='my_bot')
    parser.add_argument('--workers', type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument('--chunk', type=int, default=50)
    parser.add_argument('--pools', nargs='+', choices=POOLS, default=list(POOLS))
    parser.add_argument('--schedules', nargs='+', choices=BLIND_GROWTH, default=list(BLIND_GROWTH))
    parser.add_argument('--policy-payout', choices=PAYOUTS, default='TOP3')
    parser.add_argument('--output', default='results/ab.json')
    args = parser.parse_args()
    if args.tables < 2 or args.workers < 1:
        parser.error('at least two tables and one worker required')
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        baseline = run_module(args.baseline, args, executor)
        candidate = run_module(args.candidate, args, executor)
    rows = summarize(baseline, candidate, args.tables)
    print('pool   blinds   payout    baseline candidate     delta        SE', flush=True)
    for row in rows:
        print(f"{row['pool']:6} {row['blinds']:8} {row['payout']:6} "
              f"{row['baseline']:10.4f} {row['candidate']:9.4f} "
              f"{row['difference']:+9.4f} {row['se']:9.4f}", flush=True)
    primary = next((r for r in rows if (r['pool'], r['blinds'], r['payout']) ==
                    ('MIXED', 'doubling', 'TOP3')), None)
    regressions = [r for r in rows if r['difference'] < -2 * r['se']]
    accepted = bool(primary and primary['difference'] > 2 * primary['se'] and not regressions)
    report = dict(baseline=args.baseline, candidate=args.candidate, seed=args.seed,
                  baseline_hash=fingerprint(args.baseline), candidate_hash=fingerprint(args.candidate),
                  policy_payout=args.policy_payout, tables_per_configuration=args.tables,
                  decision_timing=False, seconds=time.monotonic() - started,
                  passes_score_gate=accepted, rows=rows)
    path = ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Score gate: {accepted}; elapsed {report["seconds"]:.1f}s; saved {path}', flush=True)


if __name__ == '__main__':
    main()
