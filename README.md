# Pokerbot tournament lab

Final bot: `my_bot_v7.py` plus `preflop_equity.py`. The live `my_bot.py` is the
same source. See [REPORT.md](REPORT.md) for all experiment decisions, the final
eighteen-row comparison, timing measurements, and flat-payout settings.

Retained improvements: stack depth, priced all-in calls, position, and postflop
classification. Opponent reads improved scores but failed the strict wall-time
validation and were removed. Rejected experiments remain reproducible in
`experiments/`. v6 remains unchanged.

Python standard library only. Eight anonymous seats, 2,000 chips each, 10/20
initial blinds, a new blind level every 25 hands, and a 200-hand cap. Eliminations
earn finishing-place points; survivors at the cap share remaining payouts by
exact ICM.

## Commands

```sh
python3 simulator.py --tables 3000 --pool MIXED --blinds doubling --payout TOP3
python3 ab_test.py --tables 10000 --baseline my_bot_v6 --candidate my_bot --workers 8
python3 generate_preflop_equity.py --samples 20000 --workers 8
python3 -m unittest -q
python3 stress_test.py
# Run only after all simulation/equity workers exit:
python3 stress_test.py --states 100000 --limit-ms 0.2
python3 timing_test.py --module my_bot_v7 --label final
python3 verify_final.py
```

Blinds accept `doubling` or `x1.5`. Fractional levels round the small blind to
the nearest integer; the big blind is twice that amount.

| Payout | First through eighth |
|---|---|
| TOP3 | 50 / 30 / 20 / 0 / 0 / 0 / 0 / 0 |
| FLAT | 40 / 30 / 20 / 10 / 0 / 0 / 0 / 0 |
| LINEAR | 8 / 7 / 6 / 5 / 4 / 3 / 2 / 1 |

Seven opponents are sampled with replacement and seats are shuffled. WEAK favors
folders, random players, maniacs and calling stations. MIXED samples all twelve
strategies evenly. TOUGH samples tight-aggressive, positional tight-aggressive,
push/fold, nit, loose-aggressive and frozen-v6. Legacy opponents are preserved.
Push/fold ranges are approximations, not a solved multiway Nash equilibrium.
Every bot gets a fresh instance each table.

## Paired experiments

The A/B command runs matching seeds, seats and opponent draws for all six
pool/blind combinations. All three payouts rescore those same trajectories,
producing eighteen result rows. Bot payout configuration stays TOP3 by default;
`--policy-payout FLAT` explicitly tests a payout-adapted policy separately.

The standard error is the sample standard deviation of the **paired table point
differences**, divided by the square root of the number of pairs. Deck and
opponent random streams are independent. Decision timers are disabled in all
A/B workers so process contention cannot cause timeout folds.

Outcomes are cached by source/dependency hashes and seeds. Byte-identical
archived winners can reuse their own previously completed trajectories; the
initial v6/live identity check independently executes both modules.
`my_bot_v6.py` is immutable. See `EXPERIMENT_LOG.md` for the selection protocol
and `results/` for detailed measurements.

## Bot interface and engine

Implement `MyBot.get_action(state)`. Return `fold`, `check`, `call`, or
`{"action": "raise", "amount": target_total_on_this_street}`.

Public state includes cards, board, pot, stacks, blinds, call amount, legal
actions and bounds; position, remaining/active players, players left to act,
street/total contributions, starting stacks, last raiser, hand number, payout
vector, and bounded public preflop action history. Opponent identities and
private cards are never exposed. Legacy opponent self-names are adapted.

The engine handles side pots, uncalled refunds, short all-in raises and raise
reopening, live-seat rotation and heads-up button order. Same-hand busts rank
by starting stacks; equal stacks split occupied places. Cap points use exact
ICM subset dynamic programming. CLI displayed cap ranks use chip ranks only
for descriptive purposes.

Ordinary serial simulations enforce the 1 ms wall-clock cutoff; exceptions,
illegal responses and timeouts fold. Timing is tested separately from the
parallel statistical experiments.

## Equity and safety

The offline generator writes `preflop_equity.py`: 169 starting hands against
random, top 10%, 20%, 35% and 50% ranges. Ranges use actual card-combination
weights, partial boundary classes and blocker removal. Ties count as half a
win. Bot decisions look up saved values and never sample runouts.

Stress checks cover malformed and ordinary inputs, action membership and
integer raise bounds. Impossible legal-action sets require a safe fold sentinel
and are counted separately. Timing reports observed wall time, including
interruptions and GC; measurements cannot guarantee performance on unknown
hardware.

The dedicated timing benchmark prepares its cases before timing, keeps GC
enabled, uses interactive thread QoS on macOS, and reports every call without
discarding outliers. Engine regression tests disable decision timers; only the
separate serial safety/timing commands evaluate latency.
