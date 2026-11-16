"""Refresh bot.js's embedded v7 data, offline, using only the standard library.

Run: python3 -B demo/generate_bot_data.py [--check]
The JavaScript strategy outside the marked data block is left untouched.
"""

import argparse
import json
from pathlib import Path
import random
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import my_bot_v7 as source

START = "  // BEGIN GENERATED PYTHON DATA\n"
END = "  // END GENERATED PYTHON DATA"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    excluded = {"EQUITY", "RANKED_HANDS", "POSITION_OPEN", "SHOVE", "CALL"}
    constants = {
        name: value for name, value in vars(source).items()
        if name.isupper() and not name.startswith("_") and name not in excluded
    }
    data = {
        "constants": constants,
        "equity": source.EQUITY,
        "rankedHands": source.RANKED_HANDS,
        "positionOpen": {key: sorted(value) for key, value in source.POSITION_OPEN.items()},
        "randomState": random.Random(0).getstate()[1],
    }
    # Python's float repr round-trips to the identical IEEE-754 number in JS.
    encoded = json.dumps(data, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    block = START + "  const DATA = " + encoded + ";\n" + END
    path = Path(__file__).with_name("bot.js")
    original = path.read_text()
    before, remainder = original.split(START, 1)
    _, after = remainder.split(END, 1)
    updated = before + block + after
    if args.check:
        if updated != original:
            raise SystemExit("bot.js data is stale; run demo/generate_bot_data.py")
        print("Embedded equity, policy, rankings, and Python RNG state match my_bot_v7.py.")
    else:
        path.write_text(updated)
        print(f"Updated {path}: {len(source.EQUITY)} equity rows and 624 MT19937 words.")


if __name__ == "__main__":
    main()
