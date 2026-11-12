#!/usr/bin/env python3
"""Dedicated serial wall-clock benchmark with inputs prepared before timing.

Every call, including the first, is counted. GC remains enabled. macOS optionally
uses interactive QoS for this benchmark thread to reduce unrelated UI-induced
descheduling; no other applications are stopped or changed. No samples excluded.
"""
import argparse
import ctypes
import gc
import importlib
import json
from pathlib import Path
import platform
import random
import statistics
import time

from stress_test import build_case, legal_choices, DECK as DECK_FOR_HISTORY


def run(module, count, label):
    qos = 'default'
    if platform.system() == 'Darwin':
        libc = ctypes.CDLL(None)
        result = libc.pthread_set_qos_class_self_np(0x21, 0)
        qos = f'macOS interactive QoS, result={result}'
    bot = importlib.import_module(module).MyBot()
    rng = random.Random(53423)
    cases = [build_case(rng, i) for i in range(1000)]
    # Exercise full bounded histories and qualified reads as well as empty ones.
    for i in range(32):
        _, state = build_case(rng, 2)
        names = tuple(n for n in state['stacks'] if n != 'my_bot')[:5]
        history = [(h, name, 'fold' if j % 2 else 'raise', j % 2 == 0, True)
                   for h in range(82, 101) for j, name in enumerate(names)]
        history.append((100, 'my_bot', 'fold', False, True))
        state.update(action_history=tuple(history[-96:]), hand_number=100,
                     board=(), hole_cards=rng.sample(DECK_FOR_HISTORY, 2))
        cases.append(('qualified_reads', state))
    oracles = [legal_choices(state) for _, state in cases]
    gc.collect()
    samples, cpu_samples = [], []
    errors = illegal = 0
    for i in range(count):
        _, state = cases[i % len(cases)]
        cpu_start = time.thread_time_ns()
        started = time.perf_counter_ns()
        try:
            action = bot.get_action(state)
        except Exception:
            errors += 1
            action = None
        elapsed = time.perf_counter_ns() - started
        cpu_elapsed = time.thread_time_ns() - cpu_start
        samples.append(elapsed)
        cpu_samples.append(cpu_elapsed)
        legal = oracles[i % len(cases)]
        if not legal:
            valid = action == 'fold'
        elif isinstance(action, dict):
            amount = action.get('amount')
            valid = (action.get('action') == 'raise' and 'raise' in legal and
                     type(amount) is int and state['min_raise_to'] <= amount <= state['max_raise_to'])
        else:
            valid = isinstance(action, str) and action in legal and action != 'raise'
        illegal += not valid
    report = dict(module=module, decisions=count, prepared_cases=len(cases), qos=qos,
                  gc_enabled=gc.isenabled(), parallel=False, excluded_samples=0,
                  crashes=errors, illegal=illegal, maximum_ms=max(samples) / 1e6,
                  maximum_cpu_ms=max(cpu_samples) / 1e6,
                  median_us=statistics.median(samples) / 1000,
                  p99_us=sorted(samples)[int(.99 * (count - 1))] / 1000,
                  over_0_2_ms=sum(x >= 200000 for x in samples),
                  over_1_ms=sum(x >= 1000000 for x in samples))
    report['passed'] = not (errors or illegal or report['over_0_2_ms'])
    print(json.dumps(report, indent=2), flush=True)
    path = Path('results') / f'timing_{label}.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', default='my_bot')
    parser.add_argument('--decisions', type=int, default=100000)
    parser.add_argument('--label', default='final')
    args = parser.parse_args()
    raise SystemExit(0 if run(args.module, args.decisions, args.label) else 1)
