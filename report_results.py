#!/usr/bin/env python3
"""Generate the requested report from recorded measurements, without rerunning games."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_text())


def primary(report):
    return next(r for r in report['rows'] if
                (r['pool'], r['payout'], r['blinds']) == ('MIXED', 'TOP3', 'doubling'))


def main():
    decisions = read('results/decisions.json')
    final = read('results/final_v7_vs_v6.json')
    timing = read('results/timing_final.json')
    safety = read('results/safety_final.json')
    identity = read('results/baseline_identity.json')
    equivalence = read('results/final_equivalence.json')
    assert safety['passed'] and timing['passed'] and equivalence['passed']
    assert final['tables_per_configuration'] >= 10000
    assert all(r['candidate_errors'] == r['candidate_illegal'] == 0 for r in final['rows'])
    p = primary(final)
    text = [
        '# Pokerbot v7 evaluation', '',
        f"Final fresh-seed MIXED/TOP3/doubling: **{p['candidate']:.4f} vs {p['baseline']:.4f} "
        f"points/table**, a gain of **{p['difference']:+.4f}**, paired SE **{p['se']:.4f}**.", '',
        'Use `my_bot_v7.py` with `preflop_equity.py` in the same directory. '
        '`my_bot.py` is the identical live copy. The final bot imports only the '
        'standard library and that generated local data file.', '',
        'Kept: stack depth, priced all-in calls, position, and postflop play. '
        'Reverted: wholesale equity ranking, ICM pressure, the combined endgame '
        'change, and opponent reads. Reads passed the score test but failed the '
        'strict wall-time validation, even after behavior-preserving optimizations.', '',
        '## Experiment decisions', '',
        'Every idea used 10,000 paired tables per pool/blind cell, rescored under '
        'all three payouts (18 configurations). The effect below is versus the '
        '**then-current accepted baseline**, not always v6. Acceptance required '
        'primary gain > 2 paired SE, no other loss > 2 paired SE, and safety/timing.', '',
        '| Idea | Decision | Primary point change | Paired SE | Reason |',
        '|---|---|---:|---:|---|',
    ]
    reasons = {
        1: 'All 18 score configurations improved; safety passed.',
        2: 'TOUGH/LINEAR: −0.1045 (SE 0.0260) doubling; −0.0725 (SE 0.0235) ×1.5.',
        3: 'All 18 score configurations improved; safety passed.',
        4: 'All 18 score configurations improved; safety passed.',
        5: 'All 18 score configurations improved; safety passed.',
        6: 'No significant primary improvement.',
        7: 'Primary failed; clear losses in WEAK/doubling and MIXED/TOUGH ×1.5.',
        8: 'Scores passed; 0.2 ms wall-time safety gate failed. All read logic removed.',
    }
    for decision in decisions:
        report = read(decision['results'])
        row = primary(report)
        text.append(f"| {decision['idea']}. {decision['name']} | "
                    f"{'Kept' if decision['kept'] else 'Reverted'} | "
                    f"{row['difference']:+.4f} | {row['se']:.4f} | {reasons[decision['idea']]} |")
    text += ['', 'Full eighteen-row measurements for each idea are in '
             '`results/idea_1.json` through `results/idea_8.json`. Exact candidate '
             'sources remain in `experiments/`; rejected logic is absent from v7.', '',
             '## Final v7 versus frozen v6', '',
             f"Fresh seeds {final['seed']}–{final['seed'] + final['tables_per_configuration'] - 1}; "
             '10,000 pairs per pool/blind cell. These seeds were not used for feature selection. '
             'All three payouts use the same trajectories. The policy setting remains TOP3; '
             'these are scoring-sensitivity results, not independently retuned policies.', '',
             '| Pool | Blinds | Payout | v6 average | v7 average | Difference | Paired SE |',
             '|---|---|---|---:|---:|---:|---:|']
    for r in final['rows']:
        text.append(f"| {r['pool']} | {r['blinds']} | {r['payout']} | "
                    f"{r['baseline']:.4f} | {r['candidate']:.4f} | "
                    f"{r['difference']:+.4f} | {r['se']:.4f} |")
    text += ['', '## Safety and timing', '',
             'All 70 unit tests passed. `stress_test.py` passed 10,000 adversarial '
             'states with zero crashes, illegal actions, unsafe fallbacks, or >1 ms calls. '
             'The final fresh-seed tournament run also recorded zero hero exceptions '
             'and zero illegal actions.', '',
             f"Dedicated benchmark: **{timing['decisions']:,} decisions**, "
             f"**{timing['maximum_ms']:.6f} ms worst wall time**, "
             f"{timing['median_us']:.3f} μs median, {timing['p99_us']:.3f} μs p99. "
             f"Maximum thread CPU time was {timing['maximum_cpu_ms']:.6f} ms. "
             'Zero calls exceeded 0.2 ms; zero samples were excluded.', '',
             'Inputs were prepared before measurement (1,032 cases, including full '
             'public-history payloads). GC stayed enabled; all simulation/equity '
             'workers had exited. macOS interactive thread QoS was used. Other desktop '
             'applications and OS activity were not stopped. This is a local observation; '
             'it cannot certify unknown hardware or arbitrary scheduling delays.', '',
             'Earlier failures are preserved: idea 1 diagnostics reached 12.026 ms wall '
             'time during descheduling before its dedicated benchmark passed. The read '
             'candidate reached 15.400583 ms in its initial dedicated run; its last '
             'optimized run reached 5.636125 ms (maximum thread CPU 0.168041 ms). '
             'It was reverted instead of substituting CPU time for the wall-time gate.', '',
             '| Accepted change | Worst dedicated wall time (100,000 decisions) |',
             '|---|---:|']
    for idea in (1, 3, 4, 5):
        t = read(f'results/timing_idea_{idea}.json')
        text.append(f"| Idea {idea} | {t['maximum_ms']:.6f} ms |")
    text += [f"| Final v7 build | {timing['maximum_ms']:.6f} ms |", '',
             'The final reorganization matched the accepted strategy on 100,000 '
             'decision inputs and 300 paired tournaments across all pools and blind '
             'schedules. It precomputes card features at import, embeds its evaluator '
             'and charts, and keeps the outer legal-action/exception guard.', '',
             '## How v7 plays — ten points', '',
             '- Measures effective stacks in big blinds, including chips already posted.',
             '- Above 40 BB, uses small 2.25-BB opens and avoids costly weak preflop calls.',
             '- At 15–40 BB, raises or folds and re-raises premium hands all-in.',
             '- Below 15 BB, uses position-aware push/fold charts; below 6 BB those ranges widen sharply.',
             '- Opens tightly early, wider on the button and small blind, and defends the big blind selectively against small raises.',
             '- Prices all-in calls using offline equity against a range estimated from the shover’s stack.',
             '- Adds more risk premium when losing would bust or cripple it, and discounts multiway equity.',
             '- Classifies postflop hands using board texture, including shared-board hands and weak flushes.',
             '- Value-bets strong hands, occasionally bets draws, and caps weaker-hand investment at one-third of the starting stack unless already committed.',
             '- Validates every action, clamps raises, and safely checks or folds on errors; it starts each table fresh.', '',
             '## Flat payouts: which settings change?', '',
             'For scoring, use `--payout FLAT` in the simulator. The configured vector '
             'is `PAYOUTS["FLAT"] = (40, 30, 20, 10, 0, 0, 0, 0)` in '
             '`tournament_scoring.py`. A/B always reports FLAT as well as TOP3 and LINEAR.', '',
             'No bot constant must change to reproduce the measured FLAT results. '
             'The payout-aware ICM idea was reverted, so the retained bot has no automatic '
             'payout switch. Its main risk-tuning constants are `BUST_RISK_PREMIUM=0.09`, '
             '`CRIPPLE_RISK_PREMIUM=0.05`, `COVERED_RISK_PREMIUM=0.015`, and '
             '`POST_CALL_MARGIN=0.03`. Change these only as a new paired experiment; '
             'different FLAT-specific values have not been validated.', '',
             '## Identity baseline', '',
             'Before editing the bot, v6 and identical my_bot were independently run '
             'on 10,000 pairs per cell. Every difference and SE was exactly zero.', '',
             '| Pool | Blinds | TOP3 average | FLAT average | LINEAR average |',
             '|---|---|---:|---:|---:|']
    for pool in ('WEAK', 'MIXED', 'TOUGH'):
        for blinds in ('doubling', 'x1.5'):
            rows = {r['payout']: r for r in identity['rows'] if r['pool'] == pool and r['blinds'] == blinds}
            text.append(f"| {pool} | {blinds} | {rows['TOP3']['baseline']:.4f} | "
                        f"{rows['FLAT']['baseline']:.4f} | {rows['LINEAR']['baseline']:.4f} |")
    text += ['', '## Reproduction and limitations', '',
             '```sh',
             'python3 ab_test.py --tables 10000 --seed 200001 --baseline versions.my_bot_v6 --candidate my_bot_v7 --output results/final_v7_vs_v6.json',
             'python3 verify_final.py', 'python3 safety_check.py --label final',
             'python3 report_results.py', '```', '',
             'Each comparison uses seeded opponent draws, seats, independent deck and '
             'opponent random streams, and fresh bot instances. Parallel simulation never '
             'measures decision timing. Remaining cap payouts use exact ICM, including '
             'same-hand elimination ties. SE is computed from paired point differences.', '',
             'Offline equity uses 20,000 samples per hand/range, actual card-combination '
             'weights and blocker removal; worst-case Monte Carlo SE per cell is 0.00354. '
             'The retained push/fold chart is heuristic. The rejected endgame experiment '
             'used the [HoldemResources no-ante heads-up chart](https://www.holdemresources.net/hune); '
             'its three-handed adjustment was an approximation.', '',
             'These pools model plausible one-hour opponents, including weak and broken '
             'bots; results do not prove superiority against every unseen strategy. '
             'Final v7 does not depend on the optional action-history field. For another '
             'poker variant, replace the card validation, hand features, strength functions '
             'and lookup data in part 2; the tournament logic is separated in part 3.', '',
             f"Frozen v6 SHA-256: `{equivalence['v6_sha256']}`.",
             f"Final v7 SHA-256: `{equivalence['v7_sha256']}`.", '']
    (ROOT / 'REPORT.md').write_text('\n'.join(text))
    with (ROOT / 'results/final_v7_vs_v6.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(final['rows'][0]))
        writer.writeheader()
        writer.writerows(final['rows'])
    print('Saved REPORT.md and results/final_v7_vs_v6.csv')


if __name__ == '__main__':
    main()
