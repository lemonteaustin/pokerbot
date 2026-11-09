#!/usr/bin/env python3
"""Eight-player no-limit Hold'em sit-and-go simulator.

Only the Python standard library is used.  See my_bot.py for the strategy
that should be replaced by a participant.
"""

from __future__ import annotations

import argparse
import itertools
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from my_bot import MyBot
from opponent_bots import LooseAggressiveBot, SavedBotOpponent, TightAggressiveBot


RANKS = "23456789TJQKA"
SUITS = "cdhs"
DECK = [(rank, suit) for rank in RANKS for suit in SUITS]
ACTION_BUDGET_SECONDS = 0.001


def card_text(card):
    return card[0] + card[1]


def evaluate_five(cards):
    values = sorted((RANKS.index(c[0]) + 2 for c in cards), reverse=True)
    counts = defaultdict(int)
    for value in values:
        counts[value] += 1
    groups = sorted(((count, value) for value, count in counts.items()), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    unique = sorted(set(values), reverse=True)
    straight_high = 0
    if len(unique) == 5:
        if unique[0] - unique[4] == 4:
            straight_high = unique[0]
        elif unique == [14, 5, 4, 3, 2]:
            straight_high = 5
    if flush and straight_high:
        return (8, straight_high)
    if groups[0][0] == 4:
        return (7, groups[0][1], groups[1][1])
    if groups[0][0] == 3 and groups[1][0] == 2:
        return (6, groups[0][1], groups[1][1])
    if flush:
        return (5, *values)
    if straight_high:
        return (4, straight_high)
    if groups[0][0] == 3:
        kickers = sorted((v for v, n in counts.items() if n == 1), reverse=True)
        return (3, groups[0][1], *kickers)
    if groups[0][0] == 2 and groups[1][0] == 2:
        pairs = sorted((v for v, n in counts.items() if n == 2), reverse=True)
        kicker = next(v for v, n in counts.items() if n == 1)
        return (2, *pairs, kicker)
    if groups[0][0] == 2:
        pair = groups[0][1]
        kickers = sorted((v for v, n in counts.items() if n == 1), reverse=True)
        return (1, pair, *kickers)
    return (0, *values)


def evaluate(cards):
    return max(evaluate_five(combo) for combo in itertools.combinations(cards, 5))


class RandomBot:
    def __init__(self, rng):
        self.rng = rng

    def get_action(self, state):
        legal = state["legal_actions"]
        choice = self.rng.choice(legal)
        if choice == "raise":
            return {"action": "raise", "amount": state["min_raise_to"]}
        return choice


class AlwaysCallBot:
    def get_action(self, state):
        return "check" if "check" in state["legal_actions"] else "call"


class AlwaysRaiseBot:
    def get_action(self, state):
        if "raise" in state["legal_actions"]:
            return {"action": "raise", "amount": state["max_raise_to"]}
        return "check" if "check" in state["legal_actions"] else "call"


class AlwaysFoldBot:
    def get_action(self, state):
        return "fold"


@dataclass
class Player:
    name: str
    bot: Any
    stack: int = 2000
    hole: tuple = ()
    folded: bool = False
    all_in: bool = False
    street_contribution: int = 0
    total_contribution: int = 0


class Tournament:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.players = [
            Player("my_bot", MyBot()),
            Player("random", RandomBot(self.rng)),
            Player("always_call", AlwaysCallBot()),
            Player("always_raise", AlwaysRaiseBot()),
            Player("always_fold", AlwaysFoldBot()),
            Player("tight_aggressive", TightAggressiveBot()),
            Player("loose_aggressive", LooseAggressiveBot(random.Random(seed ^ 0x1A6))),
            Player("my_bot_v2", SavedBotOpponent()),
        ]
        # Seeded seat draw, independent of the deck and bot random streams.
        random.Random(seed ^ 0x5EA7).shuffle(self.players)
        self.button = 0
        self.hand_number = 0
        self.errors = defaultdict(int)
        self.slow = defaultdict(int)
        self.finishes = {}
        self.positions = {}
        self.preflop_unopened = True

    def living(self):
        return [p for p in self.players if p.stack > 0]

    def active(self):
        return [
            p for p in self.players
            if not p.folded and (p.stack > 0 or p.total_contribution > 0)
        ]

    def post(self, player, amount):
        paid = min(player.stack, amount)
        player.stack -= paid
        player.street_contribution += paid
        player.total_contribution += paid
        player.all_in = player.stack == 0
        return paid

    def action(self, player, board, pot, current_bet, min_raise, max_bet):
        to_call = max(0, current_bet - player.street_contribution)
        legal = ["fold"]
        if to_call == 0:
            legal.append("check")
        elif player.stack > 0:
            legal.append("call")
        if player.stack > to_call and max_bet > current_bet:
            legal.append("raise")
        state = {
            "hole_cards": tuple(card_text(c) for c in player.hole),
            "board": tuple(card_text(c) for c in board),
            "pot": pot,
            "stacks": {p.name: p.stack for p in self.players},
            "blinds": {"small": self.small_blind, "big": self.big_blind},
            "amount_to_call": to_call,
            "legal_actions": tuple(legal),
            "min_raise_to": min(current_bet + min_raise, max_bet),
            "max_raise_to": max_bet,
            "hand_number": self.hand_number,
            "position": self.positions.get(player.name),
            "folded_to_me": not board and self.preflop_unopened,
            # Count everyone dealt in, including folded and all-in players.
            # Eliminations are resolved only after this hand is settled.
            "players_remaining": len(self.positions),
            "active_players": tuple(p.name for p in self.active()),
            "street_contributions": {p.name: p.street_contribution for p in self.players},
        }
        started = time.perf_counter()
        try:
            response = player.bot.get_action(state)
            elapsed = time.perf_counter() - started
            if elapsed > ACTION_BUDGET_SECONDS:
                self.slow[player.name] += 1
                return "fold", elapsed
            if isinstance(response, dict):
                choice = response.get("action")
                amount = response.get("amount")
            elif isinstance(response, (tuple, list)):
                choice, amount = response[0], response[1] if len(response) > 1 else None
            else:
                choice, amount = response, None
            if choice not in legal:
                return "fold", elapsed
            if choice == "raise":
                try:
                    amount = int(amount)
                except (TypeError, ValueError):
                    return "fold", elapsed
                if amount < current_bet + min_raise or amount > max_bet:
                    return "fold", elapsed
                return ("raise", amount), elapsed
            return choice, elapsed
        except Exception:
            self.errors[player.name] += 1
            return "fold", time.perf_counter() - started

    def betting_round(self, board, pot, order, initial_bet=0, initial_min_raise=None):
        current_bet = initial_bet
        min_raise = initial_min_raise or self.big_blind
        if not initial_bet:
            for p in self.players:
                p.street_contribution = 0
        pending = {p.name for p in self.active() if not p.all_in}
        if initial_bet:
            # Blinds were posted before this call; preserve their contributions.
            current_bet = max(p.street_contribution for p in self.players)
        while pending and len(self.active()) > 1:
            able_to_bet = [p for p in self.active() if not p.all_in]
            if len(able_to_bet) == 1:
                lone = able_to_bet[0]
                if lone.street_contribution >= current_bet:
                    break  # No betting into opponents who are all all-in.
            name = next((n for n in order if n in pending), None)
            if name is None:
                break
            player = next(p for p in self.players if p.name == name)
            pot = sum(p.total_contribution for p in self.players)
            max_bet = player.street_contribution + player.stack
            result, _ = self.action(player, board, pot, current_bet, min_raise, max_bet)
            if not board and result != "fold":
                # A limp/check/raise prevents later players from stealing an
                # unopened pot, even if that player subsequently folds.
                self.preflop_unopened = False
            pending.remove(name)
            if isinstance(result, tuple):
                _, target = result
                old_bet = current_bet
                self.post(player, target - player.street_contribution)
                current_bet = max(current_bet, target)
                min_raise = max(self.big_blind, current_bet - old_bet)
                pending = {p.name for p in self.active() if not p.all_in and p.name != name}
            elif result == "fold":
                player.folded = True
            elif result == "call":
                self.post(player, current_bet - player.street_contribution)
            # check needs no bookkeeping; a short all-in call is legal.
        return sum(p.total_contribution for p in self.players)

    def award(self, pot, board):
        """Settle contribution layers, including dead money and refunds."""
        assert pot == sum(p.total_contribution for p in self.players)
        before = sum(p.stack for p in self.players)
        levels = sorted({p.total_contribution for p in self.players
                         if p.total_contribution > 0})
        # Odd chips go clockwise from the button, separately for each pot.
        clockwise = [self.players[(self.button + i) % len(self.players)]
                     for i in range(1, len(self.players) + 1)]
        scores = {}
        previous = 0
        for level in levels:
            contributors = [p for p in clockwise if p.total_contribution >= level]
            amount = (level - previous) * len(contributors)
            previous = level
            if len(contributors) == 1:
                # The unmatched part of a bet is returned, even after a fold.
                contributors[0].stack += amount
                continue
            eligible = [p for p in contributors if not p.folded]
            if not eligible:
                raise RuntimeError("Side pot has no eligible player")
            if len(eligible) == 1:
                winners = eligible
            else:
                for p in eligible:
                    if p.name not in scores:
                        scores[p.name] = evaluate(p.hole + tuple(board))
                best = max(scores[p.name] for p in eligible)
                winners = [p for p in eligible if scores[p.name] == best]
            share, remainder = divmod(amount, len(winners))
            for i, winner in enumerate(winners):
                winner.stack += share + (i < remainder)
        assert sum(p.stack for p in self.players) == before + pot

    def record_eliminations(self, starting_stacks):
        """Larger starting stacks finish higher within the same hand.

        Equal starting stacks share the average of their finishing places.
        """
        busted = defaultdict(list)
        for p in self.players:
            if p.name in starting_stacks and p.stack == 0:
                busted[starting_stacks[p.name]].append(p.name)
        place = len(starting_stacks)
        for stack in sorted(busted):
            names = busted[stack]
            rank = place - (len(names) - 1) / 2
            self.finishes.update({name: rank for name in names})
            place -= len(names)

    def play_hand(self):
        self.hand_number += 1
        self.small_blind = 10 * (2 ** ((self.hand_number - 1) // 25))
        self.big_blind = self.small_blind * 2
        deck = DECK[:]
        self.rng.shuffle(deck)
        for p in self.players:
            p.folded = p.stack == 0
            p.all_in = False
            p.total_contribution = 0
            p.street_contribution = 0
            p.hole = ()
        in_hand = self.living()
        self.preflop_unopened = True
        starting_stacks = {p.name: p.stack for p in in_hand}
        # Keep the button on a live seat, including externally set-up tables.
        while self.players[self.button].stack == 0:
            self.button = (self.button + 1) % len(self.players)
        for _ in range(2):
            for p in in_hand:
                p.hole += (deck.pop(),)
        board = []
        order = [(self.button + i) % len(self.players)
                 for i in range(1, len(self.players) + 1)
                 if self.players[(self.button + i) % len(self.players)].stack > 0]
        order_names = [self.players[i].name for i in order]
        if len(in_hand) == 2:
            # Heads-up: button posts small blind and acts first preflop.
            sb = self.players[self.button]
            bb = self.players[order[0]]
            preflop_order = [sb.name, bb.name]
        else:
            sb = self.players[order[0]]
            bb = self.players[order[1]]
            preflop_order = order_names[2:] + order_names[:2]
        self.positions = {p.name: "early" for p in in_hand}
        self.positions[sb.name] = "small_blind"
        self.positions[bb.name] = "big_blind"
        if len(in_hand) >= 3:
            self.positions[preflop_order[-3]] = "button"
        if len(in_hand) >= 4:
            self.positions[preflop_order[-4]] = "cutoff"
        self.post(sb, self.small_blind)
        self.post(bb, self.big_blind)
        self.betting_round(board, 0, preflop_order, self.big_blind, self.big_blind)
        if len(self.active()) > 1:
            for count in (3, 1, 1):
                if count == 3:
                    board.extend(deck.pop() for _ in range(3))
                else:
                    board.append(deck.pop())
                for p in self.players:
                    p.street_contribution = 0
                self.betting_round(board, 0, order_names, 0, self.big_blind)
                if len(self.active()) <= 1:
                    break
        self.award(sum(p.total_contribution for p in self.players), board)
        self.record_eliminations(starting_stacks)
        assert sum(p.stack for p in self.players) == sum(starting_stacks.values())
        assert all(p.stack >= 0 for p in self.players)
        self.button = (self.button + 1) % len(self.players)
        while self.players[self.button].stack == 0:
            self.button = (self.button + 1) % len(self.players)

    def run(self):
        while len(self.living()) > 1 and self.hand_number < 200:
            self.play_hand()
        # At the hand cap, rank survivors by chips; equal stacks share places.
        groups = defaultdict(list)
        for p in self.living():
            groups[p.stack].append(p.name)
        place = 1
        for stack in sorted(groups, reverse=True):
            names = groups[stack]
            rank = place + (len(names) - 1) / 2
            self.finishes.update({name: rank for name in names})
            place += len(names)
        return dict(self.finishes)


def tournament_points(finishes):
    """Split the 50/30/20 payouts across occupied places for tied finishes."""
    payouts = {1: 50, 2: 30, 3: 20}
    groups = defaultdict(list)
    for name, rank in finishes.items():
        groups[rank].append(name)
    points = {}
    for rank, names in groups.items():
        first_place = int(rank - (len(names) - 1) / 2)
        score = sum(payouts.get(place, 0)
                    for place in range(first_place, first_place + len(names))) / len(names)
        points.update({name: score for name in names})
    return points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    if args.tables <= 0:
        parser.error("--tables must be positive")
    places = defaultdict(list)
    points = defaultdict(float)
    firsts = defaultdict(int)
    shared_first_tables = 0
    errors = defaultdict(int)
    slow = defaultdict(int)
    for table in range(args.tables):
        tournament = Tournament(args.seed + table)
        result = tournament.run()
        awarded = tournament_points(result)
        best_rank = min(result.values())
        shared_first_tables += sum(rank == best_rank for rank in result.values()) > 1
        for name, place in result.items():
            places[name].append(place)
            points[name] += awarded[name]
            firsts[name] += place == best_rank
        for name, count in tournament.errors.items():
            errors[name] += count
        for name, count in tournament.slow.items():
            slow[name] += count
    print(f"Simulated {args.tables:,} tables (seed {args.seed})")
    print("Points: 1st=50, 2nd=30, 3rd=20; all other places=0")
    print(f"{'Bot':18s} {'Avg place':>10s} {'Total points':>13s} "
          f"{'Avg points':>11s} {'1st count':>10s} {'1st rate':>10s}")
    for name in sorted(places, key=lambda name: (-points[name], name)):
        print(f"{name:18s} {sum(places[name]) / args.tables:10.3f} "
              f"{points[name]:13.1f} {points[name] / args.tables:11.3f} "
              f"{firsts[name]:10d} {100 * firsts[name] / args.tables:9.2f}%")
    if shared_first_tables:
        print(f"Shared first place in {shared_first_tables} tables: each tied leader "
              "counts as a first-place finish; tied-place points are split.")
    if errors or slow:
        print("\nAuto-folds:")
        for name in sorted(set(errors) | set(slow)):
            print(f"  {name:18s} errors={errors[name]} slow>{ACTION_BUDGET_SECONDS * 1000:.0f}ms={slow[name]}")


if __name__ == "__main__":
    main()
