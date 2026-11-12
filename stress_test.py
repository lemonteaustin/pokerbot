"""Reproducible adversarial bot checks; standard library only.

Run: python3 stress_test.py
An absent/empty/invalid legal-action list, or an impossible raise-only
range, has no legal response. Those inputs must return the safe 'fold'
sentinel and are reported separately, never counted as legal-action passes.
"""

import argparse
import gc
import importlib
import random
import statistics
import time
from collections import Counter


DECK = tuple(rank + suit for rank in "23456789TJQKA" for suit in "cdhs")
KINDS = (
    "heads_up", "three_handed", "full_table", "all_in", "tiny_stacks",
    "huge_stacks", "empty_state", "missing_fields", "wrong_types",
    "zero_legal_actions", "check_only", "call_only", "raise_only",
    "inverted_raise_range", "noninteger_raise_bounds", "clamp_small_raise",
    "clamp_large_raise", "missing_raise_bounds", "bad_cards",
    "oversized_board", "oversized_stacks", "unknown_actions",
    "negative_numbers", "boundary_stacks", "fold_only",
)


def build_case(rng, index):
    kind = KINDS[index % len(KINDS)]
    count = rng.choice((2, 3, 4, 8))
    names = ("my_bot",) + tuple("opponent_" + str(i) for i in range(count - 1))
    cards = rng.sample(DECK, 7)
    stack = rng.choice((1, 10, 20, 239, 240, 2000, 16000))
    committed = rng.choice((0, 10, 20))
    call = rng.choice((0, 20, 100, stack))
    maximum = stack + committed
    s = dict(
        hole_cards=tuple(cards[:2]), board=tuple(cards[2:2 + rng.choice((0, 3, 4, 5))]),
        stacks={name:stack if name == "my_bot" else rng.choice((1, 200, 2000))
                for name in names},
        blinds={"small":10, "big":20}, pot=rng.choice((0, 30, 500, 16000)),
        amount_to_call=call, max_raise_to=maximum,
        min_raise_to=min(maximum, committed + call + 20),
        players_remaining=count, active_players=names,
        street_contributions={name:committed if name == "my_bot" else 0 for name in names},
        position=rng.choice(("button", "cutoff", "early", "small_blind", "big_blind")),
        folded_to_me=rng.choice((True, False)), hand_number=rng.randrange(1, 201),
    )
    legal = ["fold", "check" if call == 0 else "call"]
    if stack > call:
        legal.append("raise")
    s["legal_actions"] = tuple(legal)
    if kind in ("heads_up", "three_handed", "full_table"):
        count = {"heads_up":2, "three_handed":3, "full_table":8}[kind]
        names = ("my_bot",) + tuple("opponent_" + str(i) for i in range(count - 1))
        s.update(players_remaining=count, active_players=names,
                 stacks={name:stack if name == "my_bot" else 2000 for name in names},
                 street_contributions={name:committed if name == "my_bot" else 0 for name in names})
    elif kind == "all_in":
        s.update(players_remaining=2, active_players=("my_bot", "opponent_0"),
                 stacks={"my_bot":stack, "opponent_0":0},
                 street_contributions={"my_bot":committed, "opponent_0":maximum},
                 amount_to_call=stack, legal_actions=("fold", "call"))
    elif kind in ("tiny_stacks", "huge_stacks", "boundary_stacks"):
        chips = (rng.choice((0, 1, 2)) if kind == "tiny_stacks" else
                 10 ** rng.choice((12, 18, 30)) if kind == "huge_stacks" else
                 rng.choice((239, 240, 241)))
        s["stacks"]["my_bot"] = chips
        s.update(max_raise_to=chips + committed, min_raise_to=min(40, chips + committed))
    elif kind == "empty_state":
        s = rng.choice((None, {}, [], "", 0))
    elif kind == "missing_fields":
        for key in rng.sample(list(s), rng.randrange(1, 8)):
            del s[key]
    elif kind == "wrong_types":
        s[rng.choice(("hole_cards", "board", "stacks", "blinds", "pot",
                      "amount_to_call", "players_remaining", "active_players"))] = rng.choice(
                          (None, "bad", [], {}, True, float("nan")))
    elif kind == "zero_legal_actions":
        s["legal_actions"] = rng.choice(((), [], None))
    elif kind in ("check_only", "call_only", "raise_only", "fold_only"):
        action = kind.split("_")[0]
        s["legal_actions"] = (action,)
        if action == "check":
            s["amount_to_call"] = 0
        elif action == "call":
            s["amount_to_call"] = max(1, s["amount_to_call"])
        elif action == "raise":
            s.update(min_raise_to=1, max_raise_to=max(1, maximum))
    elif kind == "inverted_raise_range":
        s.update(min_raise_to=maximum + 1, max_raise_to=maximum,
                 legal_actions=rng.choice((("raise",), ("fold", "raise"))))
    elif kind == "noninteger_raise_bounds":
        s[rng.choice(("min_raise_to", "max_raise_to"))] = rng.choice(
            (None, "100", 1.5, True, float("inf"), float("nan")))
        s["legal_actions"] = ("fold", "raise")
    elif kind in ("clamp_small_raise", "clamp_large_raise"):
        s.update(hole_cards=("As", "Ah"), board=(), players_remaining=8,
                 stacks={"my_bot":2000}, amount_to_call=20, legal_actions=("raise",))
        s.update(min_raise_to=1000, max_raise_to=2000) if kind == "clamp_small_raise" else s.update(
            min_raise_to=40, max_raise_to=50)
    elif kind == "missing_raise_bounds":
        s.pop(rng.choice(("min_raise_to", "max_raise_to")))
        s["legal_actions"] = rng.choice((("raise",), ("fold", "raise")))
    elif kind == "bad_cards":
        s["hole_cards"] = rng.choice(((), ("As",), ("Xs", "Ah"), ("A", "K"), (None, None)))
    elif kind == "oversized_board":
        s["board"] = ("As", "Kh") * 5000
    elif kind == "oversized_stacks":
        s["stacks"] = {str(i):2000 for i in range(10000)}
        s["stacks"]["my_bot"] = 2000
        s.pop("players_remaining")
    elif kind == "unknown_actions":
        s["legal_actions"] = rng.choice((("dance",), ("dance", "check"), "check", {}))
    elif kind == "negative_numbers":
        s[rng.choice(("pot", "amount_to_call", "min_raise_to", "max_raise_to"))] = -100
    return kind, s


def legal_choices(state):
    """Independent output-contract oracle; never calls the bot's helpers."""
    if not isinstance(state, dict):
        return set()
    advertised = state.get("legal_actions")
    if not isinstance(advertised, (list, tuple, set, frozenset)):
        return set()
    choices = {name for name in ("fold", "check", "call", "raise") if name in advertised}
    if "raise" in choices:
        low, high = state.get("min_raise_to"), state.get("max_raise_to")
        if type(low) is not int or type(high) is not int or low <= 0 or high < low:
            choices.remove("raise")
    return choices


def run(module="my_bot", count=10000, seed=1, limit_ms=1.0):
    bot = importlib.import_module(module).MyBot()
    rng = random.Random(seed)
    failures = Counter()
    coverage = Counter()
    samples = []
    times = []
    cpu_times = []
    slow_samples = []
    gc_events = []
    def record_gc(phase, info):
        gc_events.append((time.perf_counter_ns(), phase, info["generation"]))
    gc.callbacks.append(record_gc)
    impossible = 0
    for index in range(count):
        kind, state = build_case(rng, index)
        choices = legal_choices(state)
        coverage[kind] += 1
        impossible += not choices
        started = time.perf_counter_ns()
        cpu_started = time.thread_time_ns()
        try:
            response = bot.get_action(state)
        except Exception as error:
            elapsed = time.perf_counter_ns() - started
            failures["crashes"] += 1
            response = None
            if len(samples) < 8:
                samples.append((index, kind, type(error).__name__))
        else:
            elapsed = time.perf_counter_ns() - started
        cpu_elapsed = time.thread_time_ns() - cpu_started
        cpu_times.append(cpu_elapsed)
        times.append(elapsed)
        if elapsed > limit_ms * 1_000_000:
            failures["over_limit"] += 1
            if len(slow_samples) < 8:
                during_gc = any(started <= timestamp <= started + elapsed
                                for timestamp, _, _ in gc_events)
                slow_samples.append((index, kind, elapsed / 1e6, during_gc, cpu_elapsed / 1e6))
        if not choices:
            valid = response == "fold"
            problem = "unsafe_no_action_fallback"
        elif isinstance(response, dict):
            amount = response.get("amount")
            valid = (response.get("action") == "raise" and "raise" in choices
                     and type(amount) is int
                     and state["min_raise_to"] <= amount <= state["max_raise_to"])
            problem = "illegal_actions"
        else:
            valid = isinstance(response, str) and response in choices and response != "raise"
            problem = "illegal_actions"
        if not valid:
            failures[problem] += 1
            if len(samples) < 8:
                samples.append((index, kind, repr(response)))
    gc.callbacks.remove(record_gc)
    print(f"{module}: {count:,} states, seed {seed}, {len(coverage)} scenario groups")
    print(f"Legal-action checks: {count - impossible:,}; no-feasible-action fallback checks: {impossible:,}")
    print(f"Crashes: {failures['crashes']}; illegal actions: {failures['illegal_actions']}; "
          f"unsafe fallbacks: {failures['unsafe_no_action_fallback']}; over {limit_ms:g} ms: {failures['over_limit']}")
    print(f"Median: {statistics.median(times) / 1000:.3f} us; "
          f"p99: {sorted(times)[int(.99 * (len(times) - 1))] / 1000:.3f} us; "
          f"maximum: {max(times) / 1e6:.3f} ms")
    print(f'Maximum thread CPU time: {max(cpu_times) / 1e6:.3f} ms')
    for index, kind, detail in samples:
        print(f"  Failure #{index} [{kind}]: {detail}")
    for index, kind, elapsed, during_gc, cpu_ms in slow_samples:
        print(f"  Slow #{index} [{kind}]: {elapsed:.3f} ms; CPU {cpu_ms:.3f} ms; GC during call: {during_gc}")
    print("Timing is measured wall-clock time, not a guarantee for future calls.")
    return not any(failures.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bot-module", default="my_bot")
    parser.add_argument("--states", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument('--limit-ms', type=float, default=1.0)
    args = parser.parse_args()
    if args.states <= 0:
        parser.error("--states must be positive")
    raise SystemExit(0 if run(args.bot_module, args.states, args.seed, args.limit_ms) else 1)
