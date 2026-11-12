#!/usr/bin/env python3
"""Mechanically separate a tested candidate; print source for review/apply_patch.

No files are modified. Action-equivalence tests must pass before using output.
"""
import ast
from pathlib import Path
import re
import sys
import textwrap


def build(path):
    source = Path(path).read_text()
    tree = ast.parse(source)
    segment = lambda node: ast.get_source_segment(source, node)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MyBot')
    lines = source.splitlines()
    methods = {n.name: textwrap.dedent('\n'.join(lines[n.lineno - 1:n.end_lineno]))
               for n in cls.body if isinstance(n, ast.FunctionDef)}
    imports, variant_imports, constants, variant_constants, hand_functions = [], [], [], [], []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            target = variant_imports if isinstance(node, ast.ImportFrom) and node.module in (
                'poker_eval', 'preflop_equity', 'push_fold_chart', 'hu_nash') else imports
            target.append(segment(node))
        elif isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            is_variant = any(name.startswith(('POSITION_', '_EARLY_', '_CUTOFF_',
                             '_BUTTON_', '_SMALL_BLIND_', '_VALUES', '_SUITS')) for name in names)
            (variant_constants if is_variant else constants).append(segment(node))
        elif isinstance(node, ast.FunctionDef):
            hand_functions.append(segment(node))

    # Embed the variant helpers so submission needs only v7 and its equity dict.
    variant_imports = [line for line in variant_imports if not line.startswith(
        ('from push_fold_chart ', 'from poker_eval '))]
    chart_source = Path('push_fold_chart.py').read_text()
    chart_tree = ast.parse(chart_source)
    chart_functions, chart_tables = [], []
    for node in chart_tree.body:
        text = ast.get_source_segment(chart_source, node)
        if isinstance(node, ast.FunctionDef):
            chart_functions.append(text)
        elif isinstance(node, ast.Assign):
            name = node.targets[0].id
            if name in ('RANKED_HANDS', 'SHOVE', 'CALL'):
                chart_tables.append(text)
            elif name in ('RANKS', 'POSITIONS'):
                variant_constants.append(text)
            else:
                constants.append(text)
    constants.extend(['CHART_PAIR_BASE = 32', 'CHART_PAIR_WEIGHT = 2.5',
                      'CHART_HIGH_WEIGHT = 2', 'CHART_SUITED_BONUS = 3',
                      'CHART_CONNECTED_BONUS = 1.5', 'CHART_CALL_BEHIND_DIVISOR = 2'])
    chart_text = '\n\n'.join(chart_functions + chart_tables)
    for old, new in (('32 + 2.5 * a', 'CHART_PAIR_BASE + CHART_PAIR_WEIGHT * a'),
                     ('2 * a + b + 3 *', 'CHART_HIGH_WEIGHT * a + b + CHART_SUITED_BONUS *'),
                     ('1.5 * (a - b == 1)', 'CHART_CONNECTED_BONUS * (a - b == 1)'),
                     ('BEHIND_PENALTY / 2', 'BEHIND_PENALTY / CHART_CALL_BEHIND_DIVISOR')):
        chart_text = chart_text.replace(old, new)
    evaluator = Path('poker_eval.py').read_text()
    score_functions = []
    for node in ast.parse(evaluator).body:
        if isinstance(node, ast.FunctionDef):
            text = ast.get_source_segment(evaluator, node)
            for old, new in (('evaluate_ids', '_score_ids'), ('evaluate', '_showdown_score'),
                             ('straight', '_score_straight'), ('VALUES', '_VALUES'), ('SUITS', '_SUITS')):
                text = re.sub(r'\b' + old + r'\b', new, text)
            score_functions.append(text)
    hand_functions = score_functions + hand_functions

    safe = methods.pop('get_action').replace('def get_action(self, state):', 'def safe_action(bot, state):')
    safe = safe.replace('self._bounded_state(state)', '_bounded_state(state)')
    safe = safe.replace('self._choose_action(state)', 'bot._choose_action(state)')
    safe = safe.replace('len(advertised) > 8', 'len(advertised) > MAX_LEGAL_ACTIONS')
    safe = '''def safe_action(bot, state):
    """Bound work, prefer check/fold on errors, and enforce legal raises."""
    fallback = "fold"
    try:
        if type(state) is not dict:
            return fallback
        legal = state.get("legal_actions")
        if type(legal) not in (tuple, list, set, frozenset) or len(legal) > MAX_LEGAL_ACTIONS:
            return fallback
        check, fold, call = "check" in legal, "fold" in legal, "call" in legal
        minimum, maximum = state.get("min_raise_to"), state.get("max_raise_to")
        raise_ok = ("raise" in legal and type(minimum) is int and type(maximum) is int
                    and 0 < minimum <= maximum)
        if check:
            fallback = "check"
        elif fold:
            fallback = "fold"
        elif call:
            fallback = "call"
        elif raise_ok:
            fallback = {"action": "raise", "amount": minimum}
        else:
            return fallback
        if not _bounded_state(state):
            return fallback
        action = bot._choose_action(state)
        if type(action) is str:
            if ((action == "check" and check) or (action == "fold" and fold)
                    or (action == "call" and call)):
                return action
        elif type(action) is dict and raise_ok and action.get("action") == "raise":
            amount = action.get("amount")
            if type(amount) is int and minimum <= amount <= maximum:
                return action
        return fallback
    except Exception:
        return fallback
'''
    bounded = methods.pop('_bounded_state')
    start = bounded.index('    cards, board =')
    end = bounded.index('    stacks = state.get', start)
    validate_cards = 'def _valid_cards(state):\n' + bounded[start:end] + '    return True\n'
    validate_cards = validate_cards.replace('card[0] not in _VALUES or card[1] not in _SUITS',
                                            'card not in _VALID_CARDS')
    bounded = bounded[:start] + '    if not _valid_cards(state):\n        return False\n' + bounded[end:]
    # Newly used public collections receive the same work bounds as stacks.
    extra = '''    for field in ("total_contributions", "starting_stacks"):
        values = state.get(field, {})
        if type(values) is not dict or len(values) > 8:
            return False
        for value in values.values():
            if type(value) is not int or value < 0 or value.bit_length() > 256:
                return False
'''
    if '_observe' in methods:
        extra += '''    history = state.get("action_history", ())
    if type(history) not in (tuple, list) or len(history) > READ_MAX_HISTORY:
        return False
    for event in history:
        if type(event) not in (tuple, list) or len(event) != 5:
            return False
        hand, seat, action, shoved, raised = event
        if (type(hand) is not int or hand < 0 or hand.bit_length() > 31
                or type(seat) is not str or len(seat) > 64
                or type(action) is not str or action not in ("fold", "check", "call", "raise")
                or type(shoved) is not bool or type(raised) is not bool):
            return False
'''
    at = bounded.rfind('    return True')
    bounded = bounded[:at] + extra + bounded[at:]
    bounded = bounded.replace('<= 8', '<= MAX_PLAYERS').replace('> 8', '> MAX_PLAYERS')
    bounded = bounded.replace('> 256', '> MAX_INTEGER_BITS').replace('> 64', '> MAX_ID_LENGTH')
    methods.pop('_short_handed', None)  # Unreachable since the postflop change.
    choose = methods['_choose_action']
    at = choose.index('        return self._postflop(state)')
    choose = choose[:at] + '        return self._postflop(state)\n'
    choose = choose.replace('    try:\n', '', 1)
    lines = choose.splitlines()
    choose = '\n'.join(line[4:] if line.startswith('        ') else line for line in lines)
    methods['_choose_action'] = choose

    preflop = methods['_stack_preflop']
    start = preflop.index('    cards = state["hole_cards"]')
    end = preflop.index('    stacks = state["stacks"]', start)
    preflop = preflop[:start] + '''    features = _preflop_features(state["hole_cards"])
    hand, premium, strong = features.key, features.premium, features.strong
''' + preflop[end:]
    preflop = preflop.replace('(pair or high == 14 or (high == 13 and low >= STEAL_KING_KICKER))',
                              'features.steal')
    preflop = preflop.replace('(pair or high >= 12 or (suited and high - low <= 2))',
                              'features.defend')
    methods['_stack_preflop'] = preflop
    if '_observe' in methods:
        methods['__init__'] += '\n    self._last_history = None'
        methods['_observe'] = methods['_observe'].replace(
            '    old_hand, old_count = self._read_hand, self._read_count',
            '    if history == self._last_history:\n        return\n'
            '    self._last_history = tuple(history)\n'
            '    old_hand, old_count = self._read_hand, self._read_count')
    key_block = re.compile(r'    cards = state\["hole_cards"\]\n'
                           r'    high, low = sorted\(cards,.*?else "o"\)\n', re.S)
    for name, text in list(methods.items()):
        if name != '_stack_preflop':
            text = key_block.sub('    features = _preflop_features(state["hole_cards"])\n'
                                 '    hand = features.key\n', text)
        methods[name] = text.replace('EQUITY[hand]', 'features.equity')
        methods[name] = methods[name].replace('opponents <= 2', 'opponents <= POST_DRAW_MAX_OPPONENTS')
        methods[name] = methods[name].replace('number > 200', 'number > MAX_HANDS')
        methods[name] = methods[name].replace('(stats[3] + 1) / (stats[2] + 2)',
            '(stats[3] + READ_FOLD_PRIOR_FOLDS) / (stats[2] + READ_FOLD_PRIOR_TRIALS)')

    features = '''PreflopFeatures = namedtuple("PreflopFeatures", "key premium strong steal defend equity")


def _build_preflop_features(cards):
    high, low = sorted((_VALUES[c[0]] for c in cards), reverse=True)
    suited = cards[0][1] == cards[1][1]
    pair = high == low
    hand = ("23456789TJQKA"[high - 2] + "23456789TJQKA"[low - 2] +
            ("" if pair else "s" if suited else "o"))
    premium = (pair and high >= PREMIUM_PAIR_MIN) or (high, low) == (14, 13)
    strong = premium or (pair and high >= STRONG_PAIR_MIN) or (
        high == 14 and low >= STRONG_ACE_KICKER) or (high, low) == (13, 12)
    steal = pair or high == 14 or (high == 13 and low >= STEAL_KING_KICKER)
    defend = pair or high >= 12 or (suited and high - low <= 2)
    return PreflopFeatures(hand, premium, strong, steal, defend, EQUITY[hand])


_CARD_NAMES = tuple(rank + suit for rank in _VALUES for suit in _SUITS)
_VALID_CARDS = frozenset(_CARD_NAMES)
_PREFLOP_FEATURES = {(a, b): _build_preflop_features((a, b))
                     for a in _CARD_NAMES for b in _CARD_NAMES}


def _preflop_features(cards):
    return _PREFLOP_FEATURES[cards[0], cards[1]]
'''
    header = '''"""Tournament bot v7: statistically retained changes, standard library only.

Tune numeric policy constants below. Variant-specific cards, rankings and
range data are confined to part 2. No simulation or I/O occurs in decisions.
"""'''
    parts = [header, '\n'.join(dict.fromkeys(imports)) + '\nfrom collections import namedtuple',
             '# Tunable policy constants (blind depths are in BB).',
             'MAX_PLAYERS = 8\nMAX_HANDS = 200\nMAX_LEGAL_ACTIONS = 8\n'
             'MAX_INTEGER_BITS = 256\nMAX_ID_LENGTH = 64\nPOST_DRAW_MAX_OPPONENTS = 2' +
             ('\nREAD_FOLD_PRIOR_FOLDS = 1\nREAD_FOLD_PRIOR_TRIALS = 2' if '_observe' in methods else ''),
             '\n'.join(constants),
             '# Part 1: safe_action wrapper and bounded public-state validation.', safe, bounded,
             '# Part 2: variant-specific hand strength and import-time lookup data.',
             '\n'.join(dict.fromkeys(variant_imports)), '\n'.join(variant_constants),
             validate_cards, *hand_functions, chart_text, features,
             '# Part 3: tournament logic (stack depth, position, risk and betting).']
    method_order = ['__init__', '_choose_action', '_stack_preflop', '_all_in_call', '_postflop']
    body = ['class MyBot:', '    def get_action(self, state):\n        return safe_action(self, state)']
    for name in method_order + [n for n in methods if n not in method_order]:
        body.append(textwrap.indent(methods[name], '    '))
    parts.append('\n\n'.join(body))
    result = '\n\n\n'.join(parts) + '\n'
    ast.parse(result)
    return result


if __name__ == '__main__':
    print(build(sys.argv[1] if len(sys.argv) > 1 else 'my_bot.py'), end='')
