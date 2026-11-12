# v7 experiment protocol

Frozen v6 SHA-256: `22f413df5eca80ed3706aeb664633ea591857ac9bf9f999832a02f42910fed85`.
The initial `my_bot.py` has the identical hash. v6 is never edited.

- Selection seeds: 100001–110000, 10,000 tables in each pool/blind cell.
- Each cell is scored under TOP3, FLAT, and LINEAR from the same games.
- Policy payout configuration stays TOP3 for cross-payout rescoring. The CLI
  supports a separate `--policy-payout` for explicitly payout-adapted runs.
- Seven opponents are sampled with replacement, with independent random streams,
  per-table memory, anonymous seats, and a seeded seat draw.
- Candidate passes only with MIXED/TOP3/doubling gain > 2 paired standard errors
  and no other cell loss > 2 paired standard errors. No tuning after a failed idea.
- Every idea receives the full sample even if a partial result looks unfavorable.
- Timing is disabled during all simulation runs. Safety and the 100,000-decision
  0.2 ms timing check run only after all compute workers exit.
- Short-stack ranges are heuristic approximations, not solved multiway Nash.
- The final retained strategy is also compared with v6 on fresh seeds, avoiding
  presentation of the adaptively selected training set as independent evidence.

## Implementation notes

The engine now accepts short all-in raises, preserves the full-raise reopening
rule, uses the full BB bring-in when the big blind is short, and resumes action
clockwise after a raise. Exact showdown evaluation is checked against independent
five-card enumeration. ICM is exact subset dynamic programming.

The equity generator samples 20,000 runouts per hand/range (worst-case cell SE
0.00354). It ranks ranges by a random-equity pilot and weights actual card
combinations, including partial boundary classes and hero-card removal.

Baseline identity test: 10,000 independent A/B pairs per pool/blind cell, all
18 payout rows exactly zero difference and zero paired standard error.
Both versions had zero hero exceptions and illegal actions. The full baseline
table is in `results/baseline_identity.json` (545.8 seconds wall-clock).

Baseline and sequential results are saved in `results/`; the generated final
report is `REPORT.md`. Every one of the eight ideas completed 10,000 tables in
each pool/blind cell and all eighteen payout comparisons.

Idea 1 retained: primary gain +3.1552 (SE 0.2210), improvements in all 18
configurations. All 60 tests passed; 10,000-case stress had zero failures.
Dedicated 100,000-decision wall-time maximum: 0.182583 ms (GC enabled, no
simulation workers, interactive macOS thread QoS, no excluded calls). Earlier
stress timing diagnostics showed OS descheduling (12.026 ms wall vs 0.129 ms
CPU on that call); all failed measurements remain saved and must be disclosed.

Final retained set: ideas 1, 3, 4, 5. Ideas 2, 6, 7 failed the score gate.
Idea 8 passed scoring but failed the wall-clock gate, including attempts at
behavior-preserving optimization, and was fully reverted. Decisions and result
paths are recorded in `results/decisions.json`.

The final code separates the legal-action wrapper, variant-specific hand
functions/data, and tournament logic. Hand features are precomputed at import;
the only local runtime dependency is the generated preflop equity dictionary.
It matched the accepted strategy in 100,000 action comparisons and 300 full
paired tournaments. Final dedicated timing: 0.152958 ms maximum across 100,000
calls, GC enabled, zero excluded samples, zero crashes or illegal actions.
