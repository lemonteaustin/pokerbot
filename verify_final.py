#!/usr/bin/env python3
"""Check final packaging and equivalence to the last accepted strategy."""
import hashlib
import json
from pathlib import Path
import random

from experiments.idea_5 import MyBot as Accepted
from my_bot_v7 import MyBot as Final
from simulator import Tournament
from stress_test import build_case


def main():
    assert Path('my_bot.py').read_bytes() == Path('my_bot_v7.py').read_bytes()
    v6 = hashlib.sha256(Path('my_bot_v6.py').read_bytes()).hexdigest()
    assert v6 == '22f413df5eca80ed3706aeb664633ea591857ac9bf9f999832a02f42910fed85'
    rng = random.Random(571992)
    old, new = Accepted(), Final()
    for i in range(100000):
        _, state = build_case(rng, i)
        a, b = old.get_action(state), new.get_action(state)
        if a != b:
            raise AssertionError((i, state, a, b))
    count = 0
    for pool in ('WEAK', 'MIXED', 'TOUGH'):
        for blinds in ('doubling', 'x1.5'):
            for seed in range(300001, 300051):
                a = Tournament(seed, hero_class=Accepted, pool=pool,
                               blind_schedule=blinds, measure_timing=False).run().probabilities()
                b = Tournament(seed, hero_class=Final, pool=pool,
                               blind_schedule=blinds, measure_timing=False).run().probabilities()
                if a != b:
                    raise AssertionError((pool, blinds, seed, a, b))
                count += 1
    report = dict(passed=True, identical_action_comparisons=100000,
                  identical_table_pairs=count, v6_sha256=v6,
                  v7_sha256=hashlib.sha256(Path('my_bot_v7.py').read_bytes()).hexdigest(),
                  live_matches_v7=True, decision_timing_measured=False)
    Path('results/final_equivalence.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
