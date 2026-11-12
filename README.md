I built a tournament poker bot in a few days with no prior coding background, using AI coding tools. I translated poker strategy into Python, built a simulator, and tested improvements against a clear goal: more tournament points with reliable decisions in under one millisecond.

### Strategy in plain English

The bot plays cautiously with a deep stack and goes all-in or folds when short-stacked. It plays more hands near the button, weighs all-in calls against likely opponent hands, and keeps pots small without a strong hand. It uses only Python’s standard library.

### How I tested it

- **Realistic opponents:** weak, mixed, and tough pools of tight players, maniacs, callers, and broken bots.
- **A/B tests:** 10,000 paired tables per pool/blind schedule, with identical seeds and opponents; paired standard errors across three payouts and two blind schedules.
- **Reliability:** 70 passing tests; 10,000 stress cases without crashes or illegal actions. Worst observed time: **0.153 ms** across 100,000 decisions on the test machine.

### Results: v1 → v7

Average points per table against the mixed pool, with 50/30/20 payouts and doubling blinds:

| Version | Points |
|---|---:|
| v1–v5 | No comparable archived scores |
| v6 baseline | 21.93 |
| v7 final | **27.15** |

On fresh seeds: **+23.8%**, a **5.22-point** gain with **0.25-point** paired standard error. v7 improved across all 18 configurations in simulation.

### What I learned

I learned to define success before optimizing, separate improvement from luck, and verify AI-generated code. I kept four of eight strategy ideas; the others failed performance or timing checks.

[Final bot](my_bot_v7.py) · [Earlier versions](versions/) · [Full results and reproduction commands](REPORT.md)
