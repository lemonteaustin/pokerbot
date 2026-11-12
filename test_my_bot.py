"""Frozen legacy strategy regressions plus LIVE bot safety/engine checks.

Exact v3/v4/v6 strategy assertions remain pinned to frozen v6; deliberate
strategy experiments are checked statistically and by test_strategy.py.
"""

import random
import unittest
from unittest.mock import patch

from my_bot import MyBot as CurrentBot, _category
from versions.my_bot_v6 import MyBot
from versions.my_bot_v3 import MyBot as V3Bot, _category as v3_category
from versions.my_bot_v4 import MyBot as V4Bot
from simulator import Tournament, evaluate


DECK = tuple(rank + suit for rank in "23456789TJQKA" for suit in "cdhs")


def state(hand="As 2h", **changes):
    result = dict(
        hole_cards=tuple(hand.split()), board=(), pot=30,
        stacks={"my_bot":2000}, blinds={"big":20},
        amount_to_call=20, legal_actions=("fold", "call", "raise"),
        min_raise_to=40, max_raise_to=2000,
        position="button", folded_to_me=True,
    )
    result.update(changes)
    return result


class StealTests(unittest.TestCase):
    def test_steal_range_in_both_late_positions(self):
        for position in ("cutoff", "button"):
            for hand in ("2s 2h", "7s 7h", "As 2h", "As 9h", "Ks Th", "Ks Jh", "Ks Qh"):
                with self.subTest(position=position, hand=hand):
                    self.assertEqual(MyBot().get_action(state(hand, position=position)),
                                     {"action":"raise", "amount":60})

    def test_premiums_still_open_four_blinds(self):
        for hand in ("As Ah", "Js Jh", "As Kh"):
            self.assertEqual(MyBot().get_action(state(hand)),
                             {"action":"raise", "amount":80})

    def test_no_extra_range_when_not_folded_to_or_not_in_position(self):
        for hand in ("As 2h", "Ks Th", "2s 2h"):
            for position in ("early", "small_blind", "big_blind", None):
                self.assertEqual(MyBot().get_action(state(hand, position=position)), "fold")
            self.assertEqual(MyBot().get_action(state(hand, folded_to_me=False)), "fold")

    def test_no_stealing_without_position_metadata(self):
        s = state()
        del s["position"]
        del s["folded_to_me"]
        self.assertEqual(MyBot().get_action(s), "fold")

    def test_does_not_expand_to_weaker_kings_queens_or_connectors(self):
        for hand in ("Ks 9h", "Qs Jh", "8s 7s", "7s 2h"):
            self.assertEqual(MyBot().get_action(state(hand)), "fold")

    def test_short_stack_steals_shove_and_twelve_blinds_opens_normally(self):
        for hand in ("As 2h", "Ks Th"):
            self.assertEqual(MyBot().get_action(state(
                hand, stacks={"my_bot":200}, max_raise_to=200)),
                {"action":"raise", "amount":200})
            self.assertEqual(MyBot().get_action(state(
                hand, stacks={"my_bot":240}, max_raise_to=240)),
                {"action":"raise", "amount":60})

    def test_still_obeys_raise_bounds_and_legal_actions(self):
        self.assertEqual(MyBot().get_action(state(min_raise_to=100)),
                         {"action":"raise", "amount":100})
        self.assertEqual(MyBot().get_action(state(
            stacks={"my_bot":40}, max_raise_to=40)), {"action":"raise", "amount":40})
        result = MyBot().get_action(state(legal_actions=("fold", "call")))
        self.assertIn(result, ("fold", "call"))

    def test_history_has_no_effect_or_storage(self):
        bot = MyBot()
        s = state(folded_to_me=False, completed_hands=object())
        self.assertEqual(bot.get_action(s), "fold")
        self.assertFalse(hasattr(bot, "opponent_stats"))

    def test_exception_fallback(self):
        self.assertEqual(MyBot().get_action(None), "fold")
        self.assertEqual(MyBot().get_action({}), "fold")
        self.assertEqual(MyBot().get_action({"legal_actions":("check",)}), "check")
        self.assertEqual(MyBot().get_action(state(
            "Xs Xh", legal_actions=("fold", "check"))), "check")

    def test_all_hand_categories_and_ace_low_straights(self):
        examples = (
            ("As Ks Qs Js Ts", 8), ("As 2s 3s 4s 5s", 8),
            ("As Ah Ad Ac 2s", 7), ("As Ah Ad Ks Kh", 6),
            ("As 9s 7s 4s 2s", 5), ("As 2h 3c 4d 5s", 4),
            ("As Ah Ad", 3), ("As Ah Ks Kh", 2), ("As Ah 2s", 1),
            ("As Kh 2s", 0), ("As Ah Ad Ks Kh Kd 2c", 6),
        )
        for hand, expected in examples:
            self.assertEqual(_category(hand.split()), expected)

    def test_fast_categories_match_v3_and_independent_showdown_evaluator(self):
        rng = random.Random(12)
        for count in (3, 4, 5, 6, 7):
            for _ in range(500):
                hand = rng.sample(DECK, count)
                self.assertEqual(_category(hand), v3_category(hand))
                if count >= 5:
                    self.assertEqual(_category(hand), evaluate(hand)[0])

    def test_strategy_matches_v3_outside_steal_opportunities(self):
        rng = random.Random(99)
        current, old = MyBot(), V3Bot()
        for _ in range(3000):
            hand = rng.sample(DECK, 7)
            board_size = rng.choice((0, 3, 4, 5))
            stack = rng.choice((100, 239, 240, 1000, 2000))
            committed = rng.choice((0, 10, 20, 100))
            call = rng.choice((0, 20, 60, 200, 2000))
            legal = ["fold", "check" if call == 0 else "call"]
            if stack > call:
                legal.append("raise")
            s = state(
                " ".join(hand[:2]), board=tuple(hand[2:2 + board_size]),
                stacks={"my_bot":stack}, max_raise_to=stack + committed,
                min_raise_to=min(stack + committed, committed + call + 20),
                amount_to_call=call, pot=rng.choice((30, 100, 500, 2000)),
                folded_to_me=False, legal_actions=tuple(legal),
            )
            self.assertEqual(current.get_action(s), old.get_action(s), s)


class ShortHandedTests(unittest.TestCase):
    def short_state(self, hand="Qs 9h", **changes):
        s = state(hand, players_remaining=3, folded_to_me=False,
                  active_players=("my_bot", "a", "b"),
                  stacks={"my_bot":2000, "a":2000, "b":2000},
                  street_contributions={"my_bot":0, "a":0, "b":20})
        s.update(changes)
        return s

    def test_opens_wide_in_three_handed_and_heads_up(self):
        for count in (2, 3):
            for hand in ("Qs 9h", "Js 9h", "7s 6s", "Ks 2h"):
                s = self.short_state(hand, players_remaining=count)
                self.assertEqual(V4Bot().get_action(s), "fold")
                self.assertEqual(MyBot().get_action(s), {"action":"raise", "amount":60})

    def test_pressures_all_short_covered_opponents(self):
        s = self.short_state(stacks={"my_bot":2000, "a":100, "b":180})
        self.assertEqual(MyBot().get_action(s), {"action":"raise", "amount":2000})

    def test_does_not_shove_into_deep_opponent_because_other_is_short(self):
        s = self.short_state(stacks={"my_bot":2000, "a":100, "b":3000})
        self.assertEqual(MyBot().get_action(s), {"action":"raise", "amount":60})

    def test_folded_deep_stack_does_not_prevent_pressure(self):
        s = self.short_state(stacks={"my_bot":2000, "a":100, "b":3000},
                             active_players=("my_bot", "a"))
        self.assertEqual(MyBot().get_action(s), {"action":"raise", "amount":2000})

    def test_short_hero_shoves_wide_but_does_not_call_all_ins_with_air(self):
        s = self.short_state("7s 6s", stacks={"my_bot":200, "a":2000, "b":2000},
                             max_raise_to=200)
        self.assertEqual(MyBot().get_action(s), {"action":"raise", "amount":200})
        s.update(amount_to_call=200, legal_actions=("fold", "call"))
        self.assertEqual(MyBot().get_action(s), "fold")
        s["hole_cards"] = ("As", "Th")
        self.assertEqual(MyBot().get_action(s), "call")

    def test_large_raises_still_require_strength(self):
        self.assertEqual(MyBot().get_action(self.short_state(amount_to_call=200)), "fold")
        self.assertEqual(MyBot().get_action(self.short_state(
            "As Kh", amount_to_call=200)), {"action":"raise", "amount":600})

    def test_postflop_value_pressure(self):
        s = self.short_state("Qs Qh", board=("Tc", "7d", "2s"),
                             amount_to_call=0, legal_actions=("fold", "check", "raise"),
                             stacks={"my_bot":2000, "a":100, "b":180}, pot=300)
        self.assertEqual(MyBot().get_action(s), {"action":"raise", "amount":2000})

    def test_draws_and_occasional_air_bets(self):
        for hand, board in (("As 9s", ("2s", "7s", "Kh")),
                            ("Js 9h", ("2c", "7d", "Kh"))):
            bot = MyBot()
            bot._rng.seed(1)
            s = self.short_state(hand, board=board, amount_to_call=0,
                                 legal_actions=("fold", "check", "raise"), pot=100)
            self.assertEqual(bot.get_action(s), {"action":"raise", "amount":75})

    def test_does_not_bluff_all_in_opponents(self):
        bot = MyBot()
        bot._rng.seed(1)
        s = self.short_state("Js 9h", board=("2c", "7d", "Kh"), amount_to_call=0,
                             legal_actions=("fold", "check", "raise"),
                             stacks={"my_bot":2000, "a":0, "b":1000})
        self.assertEqual(bot.get_action(s), "check")

    def test_short_mode_exceptions_and_illegal_raise_bounds_fall_back(self):
        s = self.short_state(active_players=("my_bot", "missing"))
        self.assertEqual(MyBot().get_action(s), "fold")
        s = self.short_state(min_raise_to=3000)
        self.assertEqual(MyBot().get_action(s), "fold")

    def test_four_plus_players_matches_saved_v4(self):
        rng = random.Random(22)
        bot, saved = MyBot(), V4Bot()
        for _ in range(1500):
            hand = rng.sample(DECK, 7)
            board_size = rng.choice((0, 3, 4, 5))
            s = self.short_state(" ".join(hand[:2]),
                                 board=tuple(hand[2:2 + board_size]),
                                 players_remaining=rng.choice((4, 5, 6, 7, 8)),
                                 amount_to_call=rng.choice((20, 100, 2000)),
                                 folded_to_me=rng.choice((False, True)))
            self.assertEqual(bot.get_action(s), saved.get_action(s))


class SafetyContractTests(unittest.TestCase):
    def test_missing_data_uses_the_available_action(self):
        for action in ("check", "fold", "call"):
            self.assertEqual(CurrentBot().get_action({"legal_actions":(action,)}), action)
        self.assertEqual(CurrentBot().get_action({"legal_actions":("raise",),
                         "min_raise_to":40, "max_raise_to":100}),
                         {"action":"raise", "amount":40})

    def test_no_feasible_action_has_explicit_fold_sentinel(self):
        for s in (None, {}, {"legal_actions":()}, {"legal_actions":("dance",)},
                  {"legal_actions":("raise",), "min_raise_to":100, "max_raise_to":40}):
            self.assertEqual(CurrentBot().get_action(s), "fold")

    def test_strategy_cannot_emit_invalid_raise(self):
        bot = CurrentBot()
        for amount in (-1, 0, 39, 2001, True, 1.5, float("nan"), None):
            with patch.object(bot, "_choose_action", return_value={"action":"raise", "amount":amount}):
                self.assertEqual(bot.get_action(state()), "fold")
        with patch.object(bot, "_choose_action", return_value={"action":"raise", "amount":10**9}):
            self.assertEqual(bot.get_action(state(legal_actions=("raise",))),
                             {"action":"raise", "amount":40})

    def test_oversized_inputs_never_enter_strategy(self):
        bot = CurrentBot()
        with patch.object(bot, "_choose_action", side_effect=AssertionError("must not evaluate")) as choose:
            self.assertEqual(bot.get_action(state(board=("As",) * 10000)), "fold")
            self.assertEqual(bot.get_action(state(stacks={str(i):2000 for i in range(10000)})), "fold")
            choose.assert_not_called()

    def test_strategy_exception_preserves_legal_fallback(self):
        bot = CurrentBot()
        with patch.object(bot, "_choose_action", side_effect=ValueError("bad input")):
            self.assertEqual(bot.get_action(state(legal_actions=("check",))), "check")
            self.assertEqual(bot.get_action(state(legal_actions=("call",))), "call")


class PositionStateTests(unittest.TestCase):
    def play(self, live=None, first_action="fold"):
        t = Tournament(1, measure_timing=False)
        seen = {}
        if live is not None:
            for i, p in enumerate(t.players):
                p.stack = 2000 if i in live else 0
        # At a full table with button seat 0, seat 3 acts first preflop.
        first_name = t.players[3].name

        class Spy:
            def __init__(self, name):
                self.name = name

            def get_action(self, s):
                seen.setdefault(self.name, []).append(s)
                if self.name == first_name and first_action == "call":
                    return "check" if "check" in s["legal_actions"] else "call"
                if self.name == first_name and first_action == "raise":
                    return {"action":"raise", "amount":s["min_raise_to"]}
                return "fold"

        for p in t.players:
            p.bot = Spy(p.name)
        t.play_hand()
        return t, seen

    def test_actual_folded_to_cutoff_and_button(self):
        t, seen = self.play()
        for seat, position in ((7, "cutoff"), (0, "button"),
                               (1, "small_blind")):
            s = seen[t.players[seat].name][0]
            self.assertEqual(s["position"], position)
            self.assertTrue(s["folded_to_me"])

    def test_limp_or_raise_blocks_steal(self):
        for action in ("call", "raise"):
            t, seen = self.play(first_action=action)
            for seat in (7, 0):
                self.assertFalse(seen[t.players[seat].name][0]["folded_to_me"])

    def test_positions_skip_eliminated_seats(self):
        t, seen = self.play(live={0, 3, 6, 7})
        self.assertEqual(t.positions[t.players[7].name], "cutoff")
        self.assertEqual(t.positions[t.players[0].name], "button")
        self.assertEqual(t.positions[t.players[3].name], "small_blind")
        self.assertEqual(t.positions[t.players[6].name], "big_blind")

    def test_short_handed_does_not_label_blinds_as_steal_positions(self):
        t, _ = self.play(live={0, 3, 6})
        self.assertNotIn("cutoff", t.positions.values())
        self.assertEqual(t.positions[t.players[0].name], "button")
        t, _ = self.play(live={0, 6})
        self.assertEqual(set(t.positions.values()), {"small_blind", "big_blind"})

    def test_metadata_resets_each_hand_and_never_claims_postflop_steal(self):
        t = Tournament(1, measure_timing=False)
        states = []

        class Caller:
            def get_action(self, s):
                states.append(s)
                return "check" if "check" in s["legal_actions"] else "call"

        for p in t.players:
            p.bot = Caller()
        for _ in range(2):
            start = len(states)
            t.play_hand()
            self.assertTrue(states[start]["folded_to_me"])
        self.assertTrue(any(s["board"] for s in states))
        self.assertTrue(all(not s["folded_to_me"] for s in states if s["board"]))

    def test_all_in_players_still_count_as_remaining(self):
        t = Tournament(1, measure_timing=False)
        states = []

        class ShoveOrCall:
            def get_action(self, s):
                states.append(s)
                if "raise" in s["legal_actions"]:
                    return {"action":"raise", "amount":s["max_raise_to"]}
                return "call" if "call" in s["legal_actions"] else "check"

        for p in t.players:
            p.bot = ShoveOrCall()
        t.play_hand()
        self.assertTrue(any(sum(chips > 0 for chips in s["stacks"].values()) <= 3
                            for s in states))
        self.assertTrue(all(s["players_remaining"] == 8 for s in states))


if __name__ == "__main__":
    unittest.main()
