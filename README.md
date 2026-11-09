# Pokerbot simulator

Run from this folder on a Mac with:

```bash
python3 simulator.py
```

That runs 3,000 eight-player sit-and-go tables. The exact command for a
different number of tables is, for example, `python3 simulator.py --tables 10`.

The report shows average finishing place, total and average points, and
first-place counts and percentages. Points are 50 for first, 30 for second,
20 for third, and zero otherwise. Tied players split the points for their
occupied places equally. Tied leaders each count as a first-place finish;
the report notes when this happens. The table seed defaults to 1; reproduce
the batch with `python3 simulator.py --tables 3000 --seed 1`. Timing-related
auto-folds can still cause differences between runs with the same seed.

`my_bot_v4.py` is the saved blind-stealing strategy; it is not an extra seat.

Replace `MyBot.get_action` in `my_bot.py`. The state includes hole cards,
board, pot, stacks, blinds, amount to call, legal actions, and raise bounds.
For a raise, return `{"action": "raise", "amount": target_total_on_street}`.
Exceptions, illegal actions, and decisions taking over 1 millisecond are
auto-folded and reported.

The eight seats are `my_bot`, random, always-call, always-raise, always-fold,
tight-aggressive, loose-aggressive, and `my_bot_v2`. The last three replace
the former extra random seats. Additional strategies live in `opponent_bots.py`:

- Tight-aggressive plays 88+, AJ+, and KQ, raises good hands aggressively,
  and avoids expensive weak calls.
- Loose-aggressive plays pairs, broadway-high hands, suited hands, and close
  connectors, raises frequently, and mixes in draws and bluffs postflop.
- `my_bot_v2` imports the saved strategy unchanged and adapts stack names so
  it uses its own chips. Editing `my_bot.py` does not change this opponent.

The new bots use the same 1 ms decision budget as all other seats. The loose
bot has a seeded random generator separate from deck shuffling.

Seats are shuffled independently for each table using the table seed. Blinds
and the button skip eliminated players; heads-up, the button is the small
blind and acts first preflop. All-in pots are split by contribution level,
folded chips remain in the pots, and unmatched bets are returned. Odd chips
from tied pots go clockwise from the button.

Players eliminated on the same hand are ranked by their stacks before that
hand's blinds: the bigger starting stack finishes higher. Equal starting
stacks share the average of their occupied places (for example, 7.5 for a tie
for seventh/eighth). After 200 hands, survivors are ranked by remaining chips,
with equal stacks likewise sharing places.

Run strategy and engine regression checks with
`python3 -m unittest -v test_my_bot test_simulator`.

`my_bot.py` uses the saved v3 strategy with blind stealing and faster hand
classification. Opponent-frequency tracking has been removed. The simulator
now supplies `hand_number`, `position`, and `folded_to_me`. Positions use the
players dealt into the current hand, skipping eliminated seats. A prior
limp, check, or raise prevents `folded_to_me`; it is always false postflop.

When folded to in cutoff or button, the bot raises with any pocket pair,
any ace, or KT/KJ/KQ, suited or offsuit. New steal opens are 3 BB; premiums
remain 4 BB. Below 12 BB, the expanded steal range uses the existing shove
sizing. Blind seats are excluded (heads-up therefore adds no steal range).
Without the position fields, the bot retains its original v3 decisions.

The decision path has no history scan, I/O, or hand-combination enumeration.
Its hand evaluator uses fixed-size counters and rank bit masks. The 1 ms
wall-clock cutoff still applies; OS scheduling can cause occasional timeouts
even when the strategy itself normally runs far faster than that limit.

With 2-3 players remaining, `my_bot.py` switches to loose-aggressive play:
it opens pairs, queen-high or better hands, suited hands, and close connectors;
pressures covered opponents with effective stacks of at most 12 BB; and adds
postflop draw bets and occasional bluffs. It calls existing large bets/all-ins
more selectively than it shoves unopened pots. Opponents who already went
all-in are not treated as targets that can fold. The mode uses a private seeded
random stream; saved v4 behavior is retained with 4+ players remaining.

For this mode the state supplies `players_remaining` (everyone dealt into
the hand, even after folding or going all-in), `active_players` (not folded),
and `street_contributions`. The player count changes after a hand is settled,
not when a stack temporarily reaches zero during betting.

## Stress test

`my_bot_v5.py` preserves the pre-hardening strategy. The live `my_bot.py`
adds bounded input validation and a final legal-action check around it.
Malformed boards or player collections cannot trigger unbounded scans.
Recovery prefers check, then fold, then call, then a minimum legal raise.
If no recognized feasible action exists (including empty legal actions or
an impossible raise-only range), it returns `fold` as a sentinel: no legal
response can exist for such an input.

Run `python3 stress_test.py` for 10,000 seeded cases covering 25 scenario
groups. It checks exceptions, advertised action membership, integer raise
bounds, and every decision's wall-clock duration against 1 ms. Inputs are
generated outside the timed region; garbage collection stays enabled. Slow
cases report whether a GC event occurred during the call. The process exits
nonzero for any crash, illegal response, unsafe sentinel, or timeout.

Cases with no feasible legal action are counted separately, not presented
as legal-action successes. A clean timing run establishes an observation,
not a hard guarantee against future OS or GC delays. To reproduce the saved
version's original failures: `python3 stress_test.py --bot-module my_bot_v5`.
