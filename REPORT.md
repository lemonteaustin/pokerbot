# Pokerbot v7 evaluation

Final fresh-seed MIXED/TOP3/doubling: **27.1512 vs 21.9305 points/table**, a gain of **+5.2207**, paired SE **0.2519**.

Use `my_bot_v7.py` with `preflop_equity.py` in the same directory. `my_bot.py` is the identical live copy. The final bot imports only the standard library and that generated local data file.

Kept: stack depth, priced all-in calls, position, and postflop play. Reverted: wholesale equity ranking, ICM pressure, the combined endgame change, and opponent reads. Reads passed the score test but failed the strict wall-time validation, even after behavior-preserving optimizations.

## Experiment decisions

Every idea used 10,000 paired tables per pool/blind cell, rescored under all three payouts (18 configurations). The effect below is versus the **then-current accepted baseline**, not always v6. Acceptance required primary gain > 2 paired SE, no other loss > 2 paired SE, and safety/timing.

| Idea | Decision | Primary point change | Paired SE | Reason |
|---|---|---:|---:|---|
| 1. Stack-depth play | Kept | +3.1552 | 0.2210 | All 18 score configurations improved; safety passed. |
| 2. Real hand strength | Reverted | +0.5928 | 0.2223 | TOUGH/LINEAR: −0.1045 (SE 0.0260) doubling; −0.0725 (SE 0.0235) ×1.5. |
| 3. Calling all-ins | Kept | +0.4471 | 0.1491 | All 18 score configurations improved; safety passed. |
| 4. Position | Kept | +0.7079 | 0.1811 | All 18 score configurations improved; safety passed. |
| 5. Post-flop | Kept | +0.7580 | 0.1801 | All 18 score configurations improved; safety passed. |
| 6. ICM pressure | Reverted | -0.0482 | 0.0900 | No significant primary improvement. |
| 7. End game | Reverted | -0.0980 | 0.0642 | Primary failed; clear losses in WEAK/doubling and MIXED/TOUGH ×1.5. |
| 8. Light opponent reads | Reverted | +3.6050 | 0.1951 | Scores passed; 0.2 ms wall-time safety gate failed. All read logic removed. |

Full eighteen-row measurements for each idea are in `results/idea_1.json` through `results/idea_8.json`. Exact candidate sources remain in `experiments/`; rejected logic is absent from v7.

## Final v7 versus frozen v6

Fresh seeds 200001–210000; 10,000 pairs per pool/blind cell. These seeds were not used for feature selection. All three payouts use the same trajectories. The policy setting remains TOP3; these are scoring-sensitivity results, not independently retuned policies.

| Pool | Blinds | Payout | v6 average | v7 average | Difference | Paired SE |
|---|---|---|---:|---:|---:|---:|
| WEAK | doubling | TOP3 | 22.9698 | 27.2130 | +4.2432 | 0.2241 |
| WEAK | doubling | FLAT | 21.4163 | 24.8890 | +3.4727 | 0.1658 |
| WEAK | doubling | LINEAR | 5.9722 | 6.3779 | +0.4057 | 0.0192 |
| WEAK | x1.5 | TOP3 | 23.8279 | 28.4181 | +4.5903 | 0.2113 |
| WEAK | x1.5 | FLAT | 22.0888 | 25.9376 | +3.8488 | 0.1574 |
| WEAK | x1.5 | LINEAR | 6.0454 | 6.4904 | +0.4449 | 0.0183 |
| MIXED | doubling | TOP3 | 21.9305 | 27.1512 | +5.2207 | 0.2519 |
| MIXED | doubling | FLAT | 19.9469 | 23.9531 | +4.0063 | 0.1878 |
| MIXED | doubling | LINEAR | 5.6979 | 6.1835 | +0.4857 | 0.0225 |
| MIXED | x1.5 | TOP3 | 21.0064 | 25.8050 | +4.7987 | 0.2112 |
| MIXED | x1.5 | FLAT | 19.6693 | 23.5805 | +3.9113 | 0.1650 |
| MIXED | x1.5 | LINEAR | 5.6906 | 6.1649 | +0.4744 | 0.0203 |
| TOUGH | doubling | TOP3 | 16.2421 | 23.0880 | +6.8459 | 0.2765 |
| TOUGH | doubling | FLAT | 14.9226 | 20.0040 | +5.0814 | 0.2139 |
| TOUGH | doubling | LINEAR | 4.8735 | 5.4482 | +0.5747 | 0.0281 |
| TOUGH | x1.5 | TOP3 | 15.2036 | 20.7862 | +5.5826 | 0.2112 |
| TOUGH | x1.5 | FLAT | 14.7380 | 19.0377 | +4.2998 | 0.1756 |
| TOUGH | x1.5 | LINEAR | 4.8986 | 5.3892 | +0.4906 | 0.0240 |

## Safety and timing

All 70 unit tests passed. `stress_test.py` passed 10,000 adversarial states with zero crashes, illegal actions, unsafe fallbacks, or >1 ms calls. The final fresh-seed tournament run also recorded zero hero exceptions and zero illegal actions.

Dedicated benchmark: **100,000 decisions**, **0.152958 ms worst wall time**, 2.500 μs median, 16.083 μs p99. Maximum thread CPU time was 0.107000 ms. Zero calls exceeded 0.2 ms; zero samples were excluded.

Inputs were prepared before measurement (1,032 cases, including full public-history payloads). GC stayed enabled; all simulation/equity workers had exited. macOS interactive thread QoS was used. Other desktop applications and OS activity were not stopped. This is a local observation; it cannot certify unknown hardware or arbitrary scheduling delays.

Earlier failures are preserved: idea 1 diagnostics reached 12.026 ms wall time during descheduling before its dedicated benchmark passed. The read candidate reached 15.400583 ms in its initial dedicated run; its last optimized run reached 5.636125 ms (maximum thread CPU 0.168041 ms). It was reverted instead of substituting CPU time for the wall-time gate.

| Accepted change | Worst dedicated wall time (100,000 decisions) |
|---|---:|
| Idea 1 | 0.182583 ms |
| Idea 3 | 0.050417 ms |
| Idea 4 | 0.054166 ms |
| Idea 5 | 0.063834 ms |
| Final v7 build | 0.152958 ms |

The final reorganization matched the accepted strategy on 100,000 decision inputs and 300 paired tournaments across all pools and blind schedules. It precomputes card features at import, embeds its evaluator and charts, and keeps the outer legal-action/exception guard.

## How v7 plays — ten points

- Measures effective stacks in big blinds, including chips already posted.
- Above 40 BB, uses small 2.25-BB opens and avoids costly weak preflop calls.
- At 15–40 BB, raises or folds and re-raises premium hands all-in.
- Below 15 BB, uses position-aware push/fold charts; below 6 BB those ranges widen sharply.
- Opens tightly early, wider on the button and small blind, and defends the big blind selectively against small raises.
- Prices all-in calls using offline equity against a range estimated from the shover’s stack.
- Adds more risk premium when losing would bust or cripple it, and discounts multiway equity.
- Classifies postflop hands using board texture, including shared-board hands and weak flushes.
- Value-bets strong hands, occasionally bets draws, and caps weaker-hand investment at one-third of the starting stack unless already committed.
- Validates every action, clamps raises, and safely checks or folds on errors; it starts each table fresh.

## Flat payouts: which settings change?

For scoring, use `--payout FLAT` in the simulator. The configured vector is `PAYOUTS["FLAT"] = (40, 30, 20, 10, 0, 0, 0, 0)` in `tournament_scoring.py`. A/B always reports FLAT as well as TOP3 and LINEAR.

No bot constant must change to reproduce the measured FLAT results. The payout-aware ICM idea was reverted, so the retained bot has no automatic payout switch. Its main risk-tuning constants are `BUST_RISK_PREMIUM=0.09`, `CRIPPLE_RISK_PREMIUM=0.05`, `COVERED_RISK_PREMIUM=0.015`, and `POST_CALL_MARGIN=0.03`. Change these only as a new paired experiment; different FLAT-specific values have not been validated.

## Identity baseline

Before editing the bot, v6 and identical my_bot were independently run on 10,000 pairs per cell. Every difference and SE was exactly zero.

| Pool | Blinds | TOP3 average | FLAT average | LINEAR average |
|---|---|---:|---:|---:|
| WEAK | doubling | 22.5393 | 21.1100 | 5.9311 |
| WEAK | x1.5 | 23.4351 | 21.7963 | 6.0014 |
| MIXED | doubling | 21.8988 | 19.9031 | 5.6822 |
| MIXED | x1.5 | 21.1767 | 19.8328 | 5.6968 |
| TOUGH | doubling | 16.5981 | 15.3306 | 4.9288 |
| TOUGH | x1.5 | 15.4824 | 14.9567 | 4.9337 |

## Reproduction and limitations

```sh
python3 ab_test.py --tables 10000 --seed 200001 --baseline versions.my_bot_v6 --candidate my_bot_v7 --output results/final_v7_vs_v6.json
python3 verify_final.py
python3 safety_check.py --label final
python3 report_results.py
```

Each comparison uses seeded opponent draws, seats, independent deck and opponent random streams, and fresh bot instances. Parallel simulation never measures decision timing. Remaining cap payouts use exact ICM, including same-hand elimination ties. SE is computed from paired point differences.

Offline equity uses 20,000 samples per hand/range, actual card-combination weights and blocker removal; worst-case Monte Carlo SE per cell is 0.00354. The retained push/fold chart is heuristic. The rejected endgame experiment used the [HoldemResources no-ante heads-up chart](https://www.holdemresources.net/hune); its three-handed adjustment was an approximation.

These pools model plausible one-hour opponents, including weak and broken bots; results do not prove superiority against every unseen strategy. Final v7 does not depend on the optional action-history field. For another poker variant, replace the card validation, hand features, strength functions and lookup data in part 2; the tournament logic is separated in part 3.

Frozen v6 SHA-256: `22f413df5eca80ed3706aeb664633ea591857ac9bf9f999832a02f42910fed85`.
Final v7 SHA-256: `4dfa620207534d0f61a8ec6e36e71ec8cb2144747121841ada6d5ed592718cfc`.
