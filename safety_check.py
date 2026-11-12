#!/usr/bin/env python3
"""Serial regression/stress/timing checks after tournament workers have exited."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', default='my_bot')
    parser.add_argument('--label', default='final')
    args = parser.parse_args()
    commands = [
        [sys.executable, '-m', 'unittest', '-q'],
        [sys.executable, 'stress_test.py', '--bot-module', args.module],
        [sys.executable, 'timing_test.py', '--module', args.module,
         '--decisions', '100000', '--label', args.label],
    ]
    results = []
    for command in commands:
        started = time.monotonic()
        p = subprocess.run(command, capture_output=True, text=True)
        output = p.stdout + p.stderr
        print(output, end='', flush=True)
        results.append(dict(command=command, returncode=p.returncode,
                            seconds=time.monotonic() - started, output=output))
    report = dict(module=args.module, platform=platform.platform(),
                  python=sys.version, parallel_decision_timing=False,
                  passed=all(r['returncode'] == 0 for r in results), checks=results)
    target = Path('results') / f'safety_{args.label}.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
