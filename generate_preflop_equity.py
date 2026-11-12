#!/usr/bin/env python3
"""Offline reproducible Monte Carlo equities for all 169 Hold'em classes.

Ranges are ranked by a separate random-hand equity pilot and weighted by the
actual 6/4/12 pair/suited/offsuit combinations. The boundary class is partially
weighted to make exactly 10%, 20%, 35%, or 50% before card removal. Hero cards
are removed from each range before sampling. Ties count as half a win.
No sampling, evaluator, file access or network is needed in bot decisions.
"""
import argparse
from bisect import bisect_left
from concurrent.futures import ProcessPoolExecutor
import itertools
import json
from pathlib import Path
import random

from poker_eval import evaluate_ids

RANKS = '23456789TJQKA'
DECK = tuple((r, s) for r in range(2, 15) for s in range(4))
FRACTIONS = (0.10, 0.20, 0.35, 0.50)


def key(cards):
    a, b = sorted(cards, reverse=True)
    return RANKS[a[0] - 2] + RANKS[b[0] - 2] + ('' if a[0] == b[0] else
            's' if a[1] == b[1] else 'o')


COMBOS = {}
for combo in itertools.combinations(DECK, 2):
    COMBOS.setdefault(key(combo), []).append(combo)
HANDS = sorted(COMBOS)


def random_equity(task):
    hand, count, seed = task
    hero = COMBOS[hand][0]
    deck = tuple(c for c in DECK if c not in hero)
    rng = random.Random(seed)
    total = 0
    for _ in range(count):
        sample = rng.sample(deck, 7)
        board = tuple(sample[2:])
        a = evaluate_ids(hero + board)
        b = evaluate_ids(tuple(sample[:2]) + board)
        total += (a > b) + .5 * (a == b)
    return hand, total / count


def range_equities(task):
    hand, count, seed, ranking = task
    hero = COMBOS[hand][0]
    rng = random.Random(seed)
    results = []
    for fraction in FRACTIONS:
        target = 1326 * fraction
        cumulative, villains, decks = [], [], []
        weight_sum = 0
        for name in ranking:
            weight = min(1.0, target / len(COMBOS[name]))
            target -= len(COMBOS[name]) * weight
            for villain in COMBOS[name]:
                if any(c in hero for c in villain):
                    continue
                weight_sum += weight
                cumulative.append(weight_sum)
                villains.append(villain)
                decks.append(tuple(c for c in DECK if c not in hero and c not in villain))
            if target < 1e-9:
                break
        total = 0
        for _ in range(count):
            i = bisect_left(cumulative, rng.random() * weight_sum)
            board = tuple(rng.sample(decks[i], 5))
            a = evaluate_ids(hero + board)
            b = evaluate_ids(villains[i] + board)
            total += (a > b) + .5 * (a == b)
        results.append(total / count)
    return hand, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=20000)
    parser.add_argument('--seed', type=int, default=721935)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--output', default='preflop_equity.py')
    args = parser.parse_args()
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        pilot = dict(executor.map(random_equity,
                     [(h, args.samples, args.seed + i) for i, h in enumerate(HANDS)]))
        ranking = sorted(HANDS, key=lambda h: (-pilot[h], h))
        print('Random equities complete; computing four blocker-adjusted ranges.', flush=True)
        ranged = dict(executor.map(range_equities,
                      [(h, args.samples, args.seed + 1000 + i, ranking) for i, h in enumerate(HANDS)]))
    output = ['"""Generated offline by generate_preflop_equity.py; do not hand-edit.',
              'Values: equity vs random, top 10%, 20%, 35%, 50%.',
              f'{args.samples:,} samples/cell; maximum Monte Carlo SE <= {0.5 / args.samples ** .5:.5f}.',
              '"""', f'SAMPLES = {args.samples}', f'SEED = {args.seed}',
              f'RANGE_ORDER = {tuple(ranking)!r}', 'EQUITY = {']
    for h in HANDS:
        output.append(f'    {h!r}: {tuple(round(x, 6) for x in (pilot[h], *ranged[h]))!r},')
    output.append('}\n')
    Path(args.output).write_text('\n'.join(output))
    print(f'Saved {args.output}: 169 hands x 5 ranges.', flush=True)


if __name__ == '__main__':
    main()
