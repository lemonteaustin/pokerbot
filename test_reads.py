"""Seat-local observation qualification, deduplication and exploitation."""
import unittest
from experiments.idea_8 import MyBot
from test_my_bot import state


class ReadTests(unittest.TestCase):
    def test_fifteen_hand_threshold_and_no_double_counting(self):
        bot = MyBot()
        s = state(stacks={'my_bot': 2000, 'a': 2000},
                  action_history=tuple((h, 'a', 'raise', True, False) for h in range(1, 15)))
        bot._observe(s)
        self.assertFalse(bot._is_maniac('a'))
        bot._observe(s)
        self.assertEqual(bot._reads['a'][0], 14)
        s['action_history'] += ((15, 'a', 'raise', True, False),)
        bot._observe(s)
        self.assertTrue(bot._is_maniac('a'))
        self.assertFalse(MyBot()._reads)

    def test_reads_expand_call_against_observed_maniac(self):
        s = state('As 9h', stacks={'my_bot': 400, 'a': 0, 'b': 2000},
                  active_players=('my_bot', 'a'), players_remaining=3,
                  max_raise_to=400, min_raise_to=400, amount_to_call=400,
                  legal_actions=('fold', 'call'), pot=420, last_raiser='a',
                  opponent_all_in=True, street_contributions={'my_bot': 0, 'a': 400, 'b': 20},
                  folded_to_me=False)
        self.assertEqual(MyBot().get_action(s), 'fold')
        s['action_history'] = tuple((h, 'a', 'raise', True, False) for h in range(1, 21))
        self.assertEqual(MyBot().get_action(s), 'call')

    def test_history_is_bounded(self):
        bot = MyBot()
        bot._observe(state(action_history=((1, 'a', 'raise', True, True),) * 10000))
        self.assertEqual(bot._reads, {})


if __name__ == '__main__':
    unittest.main()
