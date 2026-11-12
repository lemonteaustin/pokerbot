"""Behavioral tests for the archived postflop candidate and price safeguards."""
import unittest

from experiments.idea_5 import MyBot, _hand_strength
from test_my_bot import state


class StrengthTests(unittest.TestCase):
    def test_shared_board_nuts_are_not_private_strength(self):
        s = state('2c 3h', board=('As', 'Ks', 'Qs', 'Js', 'Ts'))
        self.assertEqual(_hand_strength(s)[0], 0)

    def test_low_flush_on_four_flush_board_is_not_a_stack_off_hand(self):
        s = state('3s 5h', board=('As', '9s', '7s', '4s', '2d'))
        self.assertEqual(_hand_strength(s)[0], 2)

    def test_pair_and_draw_classes(self):
        for hand, board, expected in (
            ('As Kh', ('Kc', '7d', '2h'), 3),
            ('Js Jh', ('Qc', '7d', '2h'), 2),
            ('As 5s', ('Ks', '9s', '2h'), 1),
            ('5s 3h', ('2c', '4d', 'Kh'), 1),
            ('7s 7h', ('7c', '4d', 'Kh'), 3),
        ):
            self.assertEqual(_hand_strength(state(hand, board=board))[0], expected)

    def test_medium_hand_respects_total_investment_limit(self):
        s = state('Js Jh', board=('Qc', '7d', '2h'),
                  stacks={'my_bot': 600, 'a': 1000}, max_raise_to=600,
                  pot=1000, total_contributions={'my_bot': 400, 'a': 600},
                  amount_to_call=20, min_raise_to=40,
                  active_players=('my_bot', 'a'))
        self.assertEqual(MyBot().get_action(s), 'fold')
        s.update(stacks={'my_bot': 400, 'a': 1000}, max_raise_to=400,
                 total_contributions={'my_bot': 600, 'a': 600})
        self.assertEqual(MyBot().get_action(s), 'call')


if __name__ == '__main__':
    unittest.main()
