"""Regression checks for pots, finishing places, and live-seat rotation."""

import unittest
from unittest.mock import patch

from simulator import Tournament, tournament_points


def cards(text):
    return tuple(tuple(card) for card in text.split())


class TournamentTests(unittest.TestCase):
    def setUp(self):
        self.table = Tournament(1)

    def prepare_pot(self, amounts, folded=()):
        for p in self.table.players:
            p.stack = 0
            p.folded = True
            p.total_contribution = 0
        holes = ("As Ah", "Ks Kh", "Qs Qh", "Js Jh")
        for i, amount in enumerate(amounts):
            p = self.table.players[i]
            p.total_contribution = amount
            p.folded = i in folded
            p.hole = cards(holes[i])

    def settle(self, amounts, folded=(), board="2c 4d 6h 8s Tc"):
        self.prepare_pot(amounts, folded)
        self.table.award(sum(amounts), cards(board))
        return [p.stack for p in self.table.players[:len(amounts)]]

    def test_short_stack_cannot_win_side_pot(self):
        self.assertEqual(self.settle([100, 1000, 1000]), [300, 1800, 0])

    def test_multiple_side_pots_and_uncalled_refund(self):
        self.assertEqual(self.settle([100, 300, 600, 1000]), [400, 600, 600, 400])

    def test_folded_money_counts_but_folded_hand_cannot_win(self):
        self.assertEqual(self.settle([100, 1000, 1000], folded=(0,)), [0, 2100, 0])

    def test_tied_pot_odd_chip_goes_left_of_button(self):
        self.table.button = 0
        self.assertEqual(self.settle([5, 5, 5], folded=(2,),
                                     board="Tc Jc Qc Kc Ac"), [7, 8, 0])

    def test_uncontested_pot_needs_no_board_and_returns_uncalled_bet(self):
        self.assertEqual(self.settle([100, 200], folded=(1,), board=""), [200, 100])

    def test_same_hand_busts_use_starting_stack_not_seat(self):
        starting = {p.name: 2000 for p in self.table.players}
        bigger, smaller = self.table.players[:2]
        starting[bigger.name] = 1000
        starting[smaller.name] = 100
        bigger.stack = smaller.stack = 0
        self.table.record_eliminations(starting)
        self.assertEqual(self.table.finishes[bigger.name], 7)
        self.assertEqual(self.table.finishes[smaller.name], 8)
        # A later elimination ranks above both earlier eliminations.
        later_start = {p.name: p.stack for p in self.table.living()}
        later = self.table.players[2]
        later.stack = 0
        self.table.record_eliminations(later_start)
        self.assertEqual(self.table.finishes[later.name], 6)

    def test_equal_starting_stack_busts_share_places(self):
        starting = {p.name: p.stack for p in self.table.players}
        for p in self.table.players[:2]:
            p.stack = 0
        self.table.record_eliminations(starting)
        self.assertEqual(list(self.table.finishes.values()), [7.5, 7.5])

    def check_rotation(self, live_seats, button, expected_sb, expected_bb,
                       expected_preflop, expected_postflop, next_button):
        t = self.table
        for i, p in enumerate(t.players):
            p.stack = 2000 if i in live_seats else 0
        t.button = button
        recorded = []

        def betting(board, pot, order, *args):
            recorded.append((tuple(board), list(order),
                             [p.total_contribution for p in t.players]))
            return 0

        def refund(pot, board):
            for p in t.players:
                p.stack += p.total_contribution

        with patch.object(t, "betting_round", side_effect=betting), \
                patch.object(t, "award", side_effect=refund):
            t.play_hand()
        expected = [0] * 8
        expected[expected_sb] = 10
        expected[expected_bb] = 20
        self.assertEqual(recorded[0][2], expected)
        self.assertEqual(recorded[0][1], [t.players[i].name for i in expected_preflop])
        self.assertEqual(recorded[1][1], [t.players[i].name for i in expected_postflop])
        self.assertEqual(t.button, next_button)

    def test_blinds_and_button_skip_eliminated_seats(self):
        self.check_rotation({0, 3, 6}, 0, 3, 6, [0, 3, 6], [3, 6, 0], 3)

    def test_heads_up_button_posts_small_blind(self):
        self.check_rotation({2, 6}, 2, 2, 6, [2, 6], [6, 2], 6)

    def test_dead_button_moves_to_live_seat(self):
        self.check_rotation({2, 6}, 1, 2, 6, [2, 6], [6, 2], 6)

    def test_seat_shuffle_is_seeded_and_varies_between_tables(self):
        seats = lambda seed: tuple(p.name for p in Tournament(seed).players)
        self.assertEqual(seats(1), seats(1))
        self.assertGreater(len({seats(seed) for seed in range(10)}), 1)
        self.assertEqual(len(set(seats(1))), 8)

    def test_cap_ties_share_places(self):
        self.table.hand_number = 200
        self.assertEqual(set(self.table.run().values()), {4.5})

    def test_points_for_untied_finishes(self):
        finishes = {str(i): i for i in range(1, 9)}
        points = tournament_points(finishes)
        self.assertEqual([points[str(i)] for i in range(1, 9)],
                         [50, 30, 20, 0, 0, 0, 0, 0])

    def test_points_split_tied_paid_and_unpaid_places(self):
        points = tournament_points(dict(a=1, b=2, c=3.5, d=3.5,
                                         e=5, f=6, g=7, h=8))
        self.assertEqual(points['c'], 10)
        self.assertEqual(points['d'], 10)
        self.assertEqual(sum(points.values()), 100)

    def test_three_way_tie_for_first_splits_all_paid_places(self):
        points = tournament_points(dict(a=2, b=2, c=2, d=4, e=5, f=6, g=7, h=8))
        self.assertEqual(points['a'], 100 / 3)
        self.assertEqual(points['d'], 0)
        self.assertAlmostEqual(sum(points.values()), 100)

    def test_eight_way_tie_splits_all_points(self):
        points = tournament_points({str(i): 4.5 for i in range(8)})
        self.assertEqual(set(points.values()), {12.5})

    def test_full_tables_conserve_chips_and_rank_every_player(self):
        for seed in range(30):
            t = Tournament(seed)
            results = t.run()
            self.assertEqual(len(results), 8)
            self.assertEqual(sum(results.values()), 36)
            self.assertAlmostEqual(sum(tournament_points(results).values()), 100)
            self.assertEqual(sum(p.stack for p in t.players), 16000)
            self.assertTrue(all(p.stack >= 0 for p in t.players))
            self.assertLessEqual(t.hand_number, 200)


if __name__ == "__main__":
    unittest.main()
