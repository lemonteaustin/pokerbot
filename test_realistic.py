"""Independent checks for scoring, exact showdown, and reproducible matches."""
import itertools
import random
import unittest

from simulator import Tournament, DECK, evaluate, evaluate_five
from tournament_scoring import Finishes, PAYOUTS, icm_probabilities, tournament_points
from versions.my_bot_v6 import MyBot


class RealisticTests(unittest.TestCase):
    def test_evaluator_matches_independent_five_card_enumeration(self):
        rng = random.Random(71)
        for n in (5, 6, 7):
            for _ in range(1000):
                cards = rng.sample(DECK, n)
                self.assertEqual(evaluate(cards), max(evaluate_five(c)
                                 for c in itertools.combinations(cards, 5)))

    def test_icm_two_players_exact(self):
        self.assertEqual(icm_probabilities([300, 100]), [[.75, .25], [.25, .75]])

    def test_icm_symmetry_and_conservation(self):
        for stacks in ([1] * 8, [1, 2, 3, 5, 8, 13, 21, 34], [1, 999]):
            matrix = icm_probabilities(stacks)
            for row in matrix:
                self.assertAlmostEqual(sum(row), 1)
            for column in zip(*matrix):
                self.assertAlmostEqual(sum(column), 1)
        for row in icm_probabilities([10] * 8):
            for p in row:
                self.assertAlmostEqual(p, .125)

    def test_cap_icm_does_not_pay_chip_rank(self):
        finishes = Finishes({'a': 1, 'b': 2, 'c': 3}, {'a': 300, 'b': 100})
        points = tournament_points(finishes)
        self.assertEqual(points, {'a': 45, 'b': 35, 'c': 20})

    def test_seeded_pools_and_trajectories(self):
        for pool in ('WEAK', 'MIXED', 'TOUGH'):
            a = Tournament(42, hero_class=MyBot, pool=pool, measure_timing=False)
            b = Tournament(42, hero_class=MyBot, pool=pool, measure_timing=False)
            self.assertEqual(a.opponent_types, b.opponent_types)
            ra, rb = a.run(), b.run()
            self.assertEqual(ra.probabilities(), rb.probabilities())
            self.assertFalse(a.errors)
            self.assertFalse(a.illegal)
            for payouts in PAYOUTS:
                self.assertAlmostEqual(sum(tournament_points(ra, payouts).values()), sum(PAYOUTS[payouts]))

    def test_short_all_in_raise_is_legal(self):
        t = Tournament(1, measure_timing=False)
        p = t.players[0]
        class Shove:
            def get_action(self, state):
                return {'action': 'raise', 'amount': state['max_raise_to']}
        p.bot, p.stack, p.hole = Shove(), 30, (('A', 's'), ('A', 'h'))
        t.small_blind, t.big_blind = 10, 20
        action, _ = t.action(p, (), 30, 20, 20, 30)
        self.assertEqual(action, ('raise', 30))
        self.assertFalse(t.illegal)

    def test_short_raise_does_not_reopen_prior_full_raiser(self):
        t = Tournament(3, measure_timing=False)
        a, b, c = t.players[:3]
        seen = []
        for p in t.players:
            p.folded = p not in (a, b, c)
            p.hole = (('A', 's'), ('K', 'h'))
        a.stack, b.stack, c.stack = 1000, 130, 1000
        t.small_blind, t.big_blind = 10, 20
        t.positions = {p.name: 'early' for p in (a, b, c)}

        class Script:
            def __init__(self, name, first):
                self.name, self.first = name, first
            def get_action(self, s):
                seen.append((self.name, s['legal_actions']))
                if self.first:
                    amount, self.first = self.first, None
                    return {'action': 'raise', 'amount': amount}
                return 'call' if 'call' in s['legal_actions'] else 'check'

        a.bot, b.bot, c.bot = Script(a.name, 100), Script(b.name, 130), Script(c.name, None)
        t.betting_round([], 0, [a.name, b.name, c.name], 20, 20)
        self.assertEqual([name for name, _ in seen], [a.name, b.name, c.name, a.name])
        self.assertNotIn('raise', seen[-1][1])
        self.assertEqual([p.street_contribution for p in (a, b, c)], [130, 130, 130])


if __name__ == '__main__':
    unittest.main()
