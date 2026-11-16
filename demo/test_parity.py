#!/usr/bin/env python3
"""500 valid decisions: Python v7 versus the actual inline JavaScript bundle.

Run from any directory: python3 demo/test_parity.py [--seed 7107]
Falls back to bot.js only while index.html is absent. Exit 0 requires >=95%
exact actions (including raise amounts), legal outputs, and exact scores.
Only the JSON report is generated; fixtures are deterministic from the seed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import random
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import my_bot_v7 as reference
from simulator import Tournament

COUNT = 500
DECK = tuple(r + s for r in '23456789TJQKA' for s in 'cdhs')
STREETS = {0: 'preflop', 3: 'flop', 4: 'turn', 5: 'river'}
DEPTHS = (1, 4, 8, 14, 15, 16, 40, 41, 100, 300)


def javascript(payload):
    result = subprocess.run(['node', str(HERE / 'parity_runner.js')],
                            input=json.dumps(payload), text=True, capture_output=True,
                            timeout=60, cwd=ROOT)
    try:
        response = json.loads(result.stdout)
    except ValueError as error:
        raise RuntimeError(f'Runner returned invalid JSON: {result.stdout[:500]} {result.stderr[:500]}') from error
    if result.returncode or response.get('error'):
        raise RuntimeError(response.get('error', result.stderr))
    return response


def rename_seat(state):
    """Put the acting seat in the bot's canonical my_bot slot, preserving rivals."""
    state = copy.deepcopy(state)
    hero = state['self_name']
    mapping = {name: ('my_bot' if name == hero else f'opponent_{i}')
               for i, name in enumerate(state['stacks'])}
    for field in ('stacks', 'street_contributions', 'total_contributions', 'starting_stacks'):
        state[field] = {mapping[k]: v for k, v in state[field].items()}
    state['active_players'] = [mapping[n] for n in state['active_players']]
    state['last_raiser'] = mapping.get(state['last_raiser'])
    state['self_name'] = 'my_bot'
    state['action_history'] = [(h, mapping[n], *rest) for h, n, *rest in state['action_history']]
    return state


def played_cases(seed):
    """Capture decisions from legally played 2/3/4/6/8-seat simulator hands."""
    rng = random.Random(seed)
    cases = []

    class Recorder:
        def get_action(self, state):
            cases.append(('python_engine', rename_seat(state)))
            legal, roll = state['legal_actions'], rng.random()
            if 'raise' in legal and roll < .16:
                low, high = state['min_raise_to'], state['max_raise_to']
                amount = high if roll < .025 else min(high, low + int(state['pot'] * rng.choice((0, .3, .7))))
                return {'action': 'raise', 'amount': amount}
            if 'check' in legal:
                return 'check'
            return 'fold' if roll > .94 else 'call'

    for trial in range(250):
        seats = (2, 3, 4, 6, 8)[trial % 5]
        table = Tournament(seed + trial, measure_timing=False)
        for i, player in enumerate(table.players):
            player.bot = Recorder()
            # Rotate depths independently of the seat count, with asymmetric stacks.
            depth = DEPTHS[(trial // 5 + i * 3) % len(DEPTHS)]
            player.stack = depth * 20 + rng.choice((0, 1, 9)) if i < seats else 0
        table.play_hand()
        if table.errors or table.illegal:
            raise AssertionError(f'Fixture play failed: {dict(table.errors)}, {dict(table.illegal)}')
    return cases


def targeted_cases():
    """Reachable postflop decisions with legal accounting; exercise draws/RNG."""
    hands = [
        ('flush_draw', ['As', 'Js'], ['2s', '7s', 'Kd']),
        ('open_straight_draw', ['9h', '8d'], ['7c', '6s', 'Kh']),
        ('combo_draw', ['9s', '8s'], ['7s', '6s', 'Kh']),
        ('turn_flush_draw', ['As', 'Js'], ['2s', '7s', 'Kd', '4c']),
        ('gutshot', ['9h', '8d'], ['6c', '5s', 'Kh']),
        ('straight_flush', ['As', 'Ks'], ['Qs', 'Js', 'Ts']),
        ('quads', ['Ah', 'Ad'], ['Ac', 'As', '2h', '3d', '4c']),
        ('full_house', ['Ah', 'Ad'], ['Ac', 'Ks', 'Kh', '3d']),
        ('flush', ['As', 'Js'], ['2s', '7s', 'Ks']),
        ('wheel', ['As', '2h'], ['3c', '4d', '5s']),
        ('trips', ['Ah', 'Ad'], ['Ac', '7s', '2h']),
        ('two_pair', ['Ah', 'Kd'], ['Ac', 'Ks', '2h']),
        ('top_pair', ['As', 'Kh'], ['Ac', '7d', '2s']),
        ('overpair_paired_board', ['Ah', 'Ad'], ['7c', '7s', '2h']),
        ('air', ['3h', '2d'], ['Ac', 'Ks', '9h']),
        ('board_straight', ['2h', '3d'], ['9c', 'Ts', 'Jh', 'Qd', 'Kc']),
        ('board_flush', ['2h', '3d'], ['As', 'Ks', '9s', '7s', '5s']),
        ('low_flush_four_suits', ['3s', '2d'], ['As', 'Ks', '9s', '7s', '5h']),
        ('two_trips', ['Ah', 'Ad'], ['Ac', 'Ks', 'Kh', 'Kd', '2c']),
        ('three_pairs', ['Ah', 'Kd'], ['Ac', 'Ks', '2h', '2c', '3s']),
    ]
    cases = []
    for i in range(100):
        # Fifty free draws ensure a meaningful continuous private-RNG test.
        kind, hole, board = hands[i % 5] if i < 50 else hands[5 + (i - 50) % 15]
        seats = 2 if i < 50 else (2, 3, 6)[i % 3]
        names = ['my_bot'] + [f'opponent_{j}' for j in range(seats - 1)]
        bb = (2, 20, 100)[i % 3]
        prior = bb * (2, 4, 9)[i % 3]  # Matched chips on earlier streets.
        stack = bb * (16, 40, 100, 300)[i % 4]
        cost = 0 if i < 50 else bb * (0, 1, 3, 15, 40)[i % 5]
        contributions = {n: 0 for n in names}
        contributions[names[-1]] = cost
        totals = {n: prior + contributions[n] for n in names}
        stacks = {n: stack for n in names}
        # Current bettor may have shoved; hero's call can also be a short all-in.
        if cost and i % 3 == 0:
            stacks[names[-1]] = 0
        legal = ['fold', 'call' if cost else 'check']
        if stack > cost and any(stacks[n] > 0 for n in names[1:]):
            legal.append('raise')
        state = dict(hole_cards=hole[:], board=board[:], stacks=stacks,
                     blinds={'small': bb // 2, 'big': bb}, pot=sum(totals.values()),
                     amount_to_call=cost, min_raise_to=min(stack, cost + max(bb, cost)),
                     max_raise_to=stack, legal_actions=legal, players_remaining=seats,
                     active_players=names, street_contributions=contributions,
                     total_contributions=totals,
                     starting_stacks={n: stacks[n] + totals[n] for n in names},
                     position='big_blind', players_left_to_act=seats - 2,
                     folded_to_me=False, hand_number=i + 1, self_name='my_bot',
                     last_raiser=names[-1] if cost else None,
                     opponent_all_in=bool(cost and stacks[names[-1]] == 0))
        cases.append((kind, state))
    return cases


def depth_bucket(state):
    stacks, paid = state['stacks'], state['street_contributions']
    effective = min(state['max_raise_to'], max(stacks[n] + paid.get(n, 0)
                    for n in state['active_players'] if n != 'my_bot')) / state['blinds']['big']
    return '<5bb' if effective < 5 else '<15bb' if effective < 15 else '15-40bb' if effective <= 40 else '>40bb'


def choose_played(cases, count, seed):
    rng = random.Random(seed ^ 0xCAFE)
    rng.shuffle(cases)
    groups = defaultdict(list)
    for case in cases:
        state = case[1]
        groups[(len(state['board']), depth_bucket(state), state['position'])].append(case)
    chosen = []
    while len(chosen) < count:
        if not groups:
            raise AssertionError('Insufficient played decisions')
        for key in list(groups):
            chosen.append(groups[key].pop())
            if not groups[key]:
                del groups[key]
            if len(chosen) == count:
                break
    return chosen


def validate(state):
    assert reference._bounded_state(state), 'Rejected by v7 bounded-state validation'
    cards = state['hole_cards'] + state['board']
    assert len(set(cards)) == len(cards), 'Duplicate cards'
    stacks, street = state['stacks'], state['street_contributions']
    totals = state['total_contributions']
    assert stacks['my_bot'] > 0 and 'my_bot' in state['active_players']
    assert len(state['active_players']) >= 2
    assert state['pot'] == sum(totals.values())
    assert all(totals[n] >= street[n] >= 0 for n in stacks)
    assert all(state['starting_stacks'][n] == stacks[n] + totals[n]
               for n in state['starting_stacks'])
    assert state['max_raise_to'] == stacks['my_bot'] + street['my_bot']
    assert state['amount_to_call'] == max(0, max(street.values()) - street['my_bot'])
    legal = state['legal_actions']
    assert ('check' in legal) == (state['amount_to_call'] == 0)
    assert ('call' in legal) == (state['amount_to_call'] > 0)
    assert 'fold' in legal
    if 'raise' in legal:
        assert stacks['my_bot'] > state['amount_to_call']
        assert 0 < state['min_raise_to'] <= state['max_raise_to']


def legal_action(action, state):
    if type(action) is str:
        return action != 'raise' and action in state['legal_actions']
    return (type(action) is dict and set(action) == {'action', 'amount'}
            and action['action'] == 'raise' and 'raise' in state['legal_actions']
            and type(action['amount']) is int
            and state['min_raise_to'] <= action['amount'] <= state['max_raise_to'])


class CountedRandom(random.Random):
    def __init__(self):
        super().__init__(0)
        self.calls = 0

    def random(self):
        self.calls += 1
        return super().random()


def run(seed):
    engine = javascript({'collect_engine': 50, 'seed': seed})
    engine_cases = [('javascript_engine', state) for state in engine['states']]
    cases = targeted_cases() + choose_played(played_cases(seed), 400 - len(engine_cases), seed) + engine_cases
    # JSON round-trip gives both implementations identical list/dictionary states.
    cases = json.loads(json.dumps(cases))
    random.Random(seed ^ 0xB07).shuffle(cases)
    states = [state for _, state in cases]
    assert len(states) == COUNT
    for i, state in enumerate(states):
        try:
            validate(state)
        except (AssertionError, KeyError, TypeError) as error:
            raise AssertionError(f'Invalid fixture #{i} ({cases[i][0]}): {error}; {state}') from error

    bot = reference.MyBot()  # Exactly one reference instance, in the same order as JS.
    bot._rng = CountedRandom()
    expected, random_calls = [], []
    for state in states:
        before = bot._rng.calls
        # Call strategy as an additional guard against swallowed exception/fallback passes.
        snapshot = bot._rng.getstate()
        chosen = bot._choose_action(copy.deepcopy(state))
        bot._rng.setstate(snapshot)
        bot._rng.calls = before
        action = bot.get_action(copy.deepcopy(state))
        assert action == chosen, 'Reference safe_action masked an invalid strategy result'
        expected.append(action)
        random_calls.append(bot._rng.calls - before)

    score_cases = [s['hole_cards'] + s['board'] for _, s in targeted_cases() if s['board']]
    rng = random.Random(seed ^ 0x5C0E)
    score_cases += [rng.sample(DECK, 5 + i % 3) for i in range(200)]
    actual = javascript({'states': states, 'score_cases': score_cases})
    assert engine['source']['code_sha256'] == actual['source']['code_sha256'], 'Artifact changed during test; rerun'
    assert len(actual['actions']) == COUNT
    coverage = {key: Counter() for key in ('sources', 'streets', 'positions', 'depths', 'players', 'costs', 'python_actions', 'javascript_actions', 'strengths')}
    flags, mismatches, illegal = Counter(), [], []
    for i, ((kind, state), py, js) in enumerate(zip(cases, expected, actual['actions'])):
        action = js['action']
        for side, value in (('python', py), ('javascript', action)):
            if not legal_action(value, state):
                illegal.append({'index': i, 'side': side, 'action': value})
            coverage[side + '_actions'][value.get('action', 'invalid') if isinstance(value, dict) else str(value)] += 1
        coverage['sources'][kind] += 1
        coverage['streets'][STREETS[len(state['board'])]] += 1
        coverage['positions'][state['position']] += 1
        coverage['depths'][depth_bucket(state)] += 1
        coverage['players'][str(state['players_remaining'])] += 1
        cost, stack = state['amount_to_call'], state['stacks']['my_bot']
        coverage['costs']['free' if not cost else 'all_in_call' if cost >= stack else 'priced_call'] += 1
        if state['board']:
            coverage['strengths'][str(reference._hand_strength(state)[0])] += 1
        flags['opponent_all_in'] += bool(state.get('opponent_all_in'))
        flags['short_raise_only'] += 'raise' in state['legal_actions'] and state['min_raise_to'] == state['max_raise_to']
        flags['random_draw_decisions'] += random_calls[i]
        flags['unopened'] += bool(state.get('folded_to_me'))
        if py != action or js.get('error'):
            mismatches.append({'index': i, 'kind': kind, 'python': py, 'javascript': action,
                               'reason': js.get('reason'), 'error': js.get('error'),
                               'random_calls_before': sum(random_calls[:i]), 'state': state})
    score_mismatches = []
    assert len(actual['scores']) == len(score_cases)
    for i, (cards, js) in enumerate(zip(score_cases, actual['scores'])):
        py = list(reference._showdown_score(cards))
        if js.get('score') != py or js.get('error'):
            score_mismatches.append({'index': i, 'cards': cards, 'python': py, 'javascript': js})
    assert all(coverage['streets'][street] >= 50 for street in STREETS.values()), 'Insufficient street coverage'
    assert all(coverage['positions'][p] for p in reference.POSITIONS), 'Missing position'
    assert len(coverage['depths']) == 4 and flags['random_draw_decisions'] >= 40
    matches = COUNT - len(mismatches)
    passed = matches / COUNT >= .95 and not illegal and not score_mismatches
    return dict(passed=passed, count=COUNT, valid_count=COUNT, matches=matches,
                match_rate=matches / COUNT, required_rate=.95, seed=seed,
                source=actual['source'], engine_source=engine['source'],
                engine_unavailable=engine.get('unavailable'),
                states_sha256=hashlib.sha256(json.dumps(states, sort_keys=True).encode()).hexdigest(),
                coverage={**coverage, 'flags': flags}, mismatch_count=len(mismatches),
                mismatches=mismatches[:12], omitted_mismatches=max(0, len(mismatches) - 12),
                illegal_count=len(illegal), illegal=illegal[:12],
                scores=dict(count=len(score_cases), mismatch_count=len(score_mismatches),
                            mismatches=score_mismatches[:12]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=7107)
    args = parser.parse_args()
    try:
        report = run(args.seed)
    except Exception as error:
        report = dict(passed=False, count=0, requested_count=COUNT, seed=args.seed,
                      error=f'{type(error).__name__}: {error}')
    destination = HERE / 'test_results' / 'parity.json'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report[k] for k in ('passed', 'count', 'matches', 'match_rate',
                    'mismatch_count', 'illegal_count', 'scores', 'error') if k in report}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
