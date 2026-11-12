"""Fast tier-based strategy using only the simulator's public state.

Raises specify the total contribution on this street. Under 12 BB, use
preflop push/fold; postflop always requires a made hand for a value bet.
Premium hands open to 4 BB; strong hands open to 3 BB. Reraises target
three times the current street bet. Big preflop calls exceed 3 BB.
Overpairs, top pair with J+ kicker, and better hands bet the visible pot
(in addition to any call). Weak pairs call at most a quarter of that pot.
Board-only made hands are checked or folded.
When folded to in the cutoff or button (not a blind), steal with any pair,
any ace, or KT/KJ/KQ. Steal opens are 3 BB (4 BB for premiums), or a shove
below 12 BB. No opponent history is stored or processed.
With 2-3 players remaining, a separate loose-aggressive mode opens wider,
pressures short effective stacks, and mixes postflop value bets and bluffs.
"""

import random

from poker_eval import evaluate as _showdown_score

POST_VERY_STRONG_EQUITY = 0.90
POST_STRONG_EQUITY = 0.72
POST_TWO_PAIR_EQUITY = 0.78
POST_MEDIUM_EQUITY = 0.37
POST_TOP_PAIR_EQUITY = 0.52
POST_NOTHING_EQUITY = 0.06
POST_MULTIWAY_PENALTY = 0.22
DRAW_FLOP_OUT_VALUE = 0.035
DRAW_TURN_OUT_VALUE = 0.022
MAX_DRAW_EQUITY = 0.48
POST_CALL_MARGIN = 0.03
POST_VERY_STRONG_BET = 0.75
POST_STRONG_BET = 0.60
POST_DRAW_BET = 0.25
POST_DRAW_BET_FREQUENCY = 0.35
POST_MAX_WEAK_INVESTMENT = 1 / 3
POST_COMMITTED_FRACTION = 0.50
POST_GOOD_KICKER = 11
STRAIGHT_DRAW_MASKS = tuple(31 << start for start in range(1, 11))


POSITION_EARLY_PAIRS = "88 99 TT JJ QQ KK AA"
POSITION_EARLY_BROADWAY = "AJs AQs AKs AQo AKo KQs"
POSITION_CUTOFF_EXTRA = "22 33 44 55 66 77 A2s A3s A4s A5s A6s A7s A8s A9s ATs ATo AJo K9s KTs KJs KTo KJo KQo Q9s QTs QJs QJo J9s JTs T9s 98s 87s 76s"
POSITION_BUTTON_EXTRA = "A2o A3o A4o A5o A6o A7o A8o A9o K2s K3s K4s K5s K6s K7s K8s K8o K9o Q8s QTo J8s JTo T8s T9o 97s 86s 75s 65s 54s"
POSITION_SMALL_BLIND_EXTRA = "K5o K6o K7o Q7s Q8o Q9o J7s J9o T7s T8o 98o 96s 87o 85s 76o 64s 53s"
BB_DEFEND_CALL_BB = 1.5
BB_DEFEND_STACK_FRACTION = 0.08
_EARLY_OPEN = frozenset((POSITION_EARLY_PAIRS + " " + POSITION_EARLY_BROADWAY).split())
_CUTOFF_OPEN = _EARLY_OPEN | frozenset(POSITION_CUTOFF_EXTRA.split())
_BUTTON_OPEN = _CUTOFF_OPEN | frozenset(POSITION_BUTTON_EXTRA.split())
_SMALL_BLIND_OPEN = _BUTTON_OPEN | frozenset(POSITION_SMALL_BLIND_EXTRA.split())
POSITION_OPEN = {"early": _EARLY_OPEN, "cutoff": _CUTOFF_OPEN,
                 "button": _BUTTON_OPEN, "small_blind": _SMALL_BLIND_OPEN,
                 "big_blind": _BUTTON_OPEN}


from preflop_equity import EQUITY

SHOVER_VERY_SHORT_BB = 4
SHOVER_SHORT_BB = 8
SHOVER_MEDIUM_BB = 15
BUST_RISK_FRACTION = 0.80
CRIPPLE_RISK_FRACTION = 0.40
BUST_RISK_PREMIUM = 0.09
CRIPPLE_RISK_PREMIUM = 0.05
COVERED_RISK_PREMIUM = 0.015
MULTIWAY_EQUITY_EXPONENT = 0.85


from push_fold_chart import SHOVE, CALL

DEEP_STACK_BB = 40
PUSH_FOLD_BB = 15
DEEP_OPEN_BB = 2.25
MID_OPEN_BB = 2.5
RERAISE_MULTIPLIER = 3
BIG_RAISE_BB = 3
PREMIUM_PAIR_MIN = 11
STRONG_PAIR_MIN = 8
STRONG_ACE_KICKER = 11
STEAL_KING_KICKER = 10



_VALUES = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}
_SUITS = {suit: index for index, suit in enumerate("cdhs")}


def _category(cards):
    """Same categories as v3, using fixed-size counts and rank bit masks."""
    counts = [0] * 15
    suits = [0] * 4
    suit_masks = [0] * 4
    mask = 0
    pairs = triples = 0
    quads = False
    for card in cards:
        rank = _VALUES[card[0]]
        suit = _SUITS[card[1]]
        bit = 1 << rank
        mask |= bit
        counts[rank] += 1
        count = counts[rank]
        if count == 2:
            pairs += 1
        elif count == 3:
            triples += 1
        elif count == 4:
            quads = True
        suits[suit] += 1
        suit_masks[suit] |= bit

    flush = False
    for suit in range(4):
        if suits[suit] >= 5:
            flush = True
            suited_mask = suit_masks[suit]
            suited_mask |= (suited_mask >> 13) & 2  # Ace can also be low.
            if (suited_mask & (suited_mask >> 1) & (suited_mask >> 2)
                    & (suited_mask >> 3) & (suited_mask >> 4)):
                return 8
    if quads:
        return 7
    if triples and pairs >= 2:
        return 6
    if flush:
        return 5
    mask |= (mask >> 13) & 2
    if mask & (mask >> 1) & (mask >> 2) & (mask >> 3) & (mask >> 4):
        return 4
    if triples:
        return 3
    return 2 if pairs >= 2 else 1 if pairs else 0


def _hand_strength(state):
    """Variant-specific: class 4/3/2/1/0 = very strong/strong/medium/draw/air."""
    cards, board = state["hole_cards"], state["board"]
    combined = tuple(cards) + tuple(board)
    score = _showdown_score(combined)
    category = score[0]
    board_category = _category(board)
    ranks = [_VALUES[c[0]] for c in cards]
    board_ranks = [_VALUES[c[0]] for c in board]
    top = max(board_ranks)
    pocket_pair = ranks[0] == ranks[1]
    top_pair = top in ranks and not pocket_pair
    overpair = pocket_pair and ranks[0] > top
    good_top = top_pair and min(ranks) >= POST_GOOD_KICKER
    if top_pair:
        kicker = ranks[1] if ranks[0] == top else ranks[0]
        good_top = kicker >= POST_GOOD_KICKER
    board_suits = [c[1] for c in board]
    four_flush = max(board_suits.count(s) for s in "cdhs") >= 4
    improved = (score > _showdown_score(board) if len(board) == 5 else
                category > board_category)
    real_two_pair = (category == 2 and board_category < 2 and not (
                    pocket_pair and len(set(board_ranks)) < len(board_ranks)))
    strong_pair = (overpair or good_top) and not four_flush
    if category == 5 and four_flush:
        suit = max("cdhs", key=board_suits.count)
        high_flush = max((_VALUES[c[0]] for c in cards if c[1] == suit), default=0)
        if high_flush < POST_GOOD_KICKER:
            return 2, POST_TOP_PAIR_EQUITY
    if improved and category >= 4 and not (four_flush and category == 4):
        return 4, POST_VERY_STRONG_EQUITY
    if improved and ((category == 3 and board_category < 3) or real_two_pair):
        return 3, POST_TWO_PAIR_EQUITY
    if strong_pair:
        return 3, POST_STRONG_EQUITY
    if (improved and category >= 1) or top_pair or overpair:
        return 2, POST_TOP_PAIR_EQUITY if top_pair or overpair else POST_MEDIUM_EQUITY
    if len(board) < 5:
        suits = [c[1] for c in combined]
        flush_draw = any(suits.count(c[1]) == 4 for c in cards)
        mask = board_mask = hole_mask = 0
        for r in board_ranks:
            board_mask |= 1 << r
        for r in ranks:
            hole_mask |= 1 << r
        mask = board_mask | hole_mask
        mask |= (mask >> 13) & 2
        hole_mask |= (hole_mask >> 13) & 2
        board_mask |= (board_mask >> 13) & 2
        missing = 0
        for window in STRAIGHT_DRAW_MASKS:
            if ((mask & window).bit_count() == 4 and
                    window & hole_mask & ~board_mask):
                missing |= window & ~mask
        outs = (9 if flush_draw else 0) + 4 * missing.bit_count()
        if flush_draw and missing:
            outs -= 2
        if outs:
            value = DRAW_FLOP_OUT_VALUE if len(board) == 3 else DRAW_TURN_OUT_VALUE
            return 1, min(MAX_DRAW_EQUITY, outs * value)
    return 0, POST_NOTHING_EQUITY



class MyBot:
    def __init__(self):
        # Private reproducible stream; never changes the deck RNG.
        self._rng = random.Random(0)

    def get_action(self, state):
        """Guard the strategy and enforce the advertised action contract.

        Empty/missing legal actions or impossible raise-only bounds have no
        legal answer: return 'fold' as a safe sentinel. Otherwise prefer
        check, fold, call, then the minimum legal raise when recovering.
        """
        fallback = "fold"
        try:
            if type(state) is not dict:
                return fallback
            advertised = state.get("legal_actions")
            if type(advertised) not in (tuple, list, set, frozenset):
                return fallback
            if len(advertised) > 8:
                return fallback
            choices = tuple(name for name in ("check", "fold", "call", "raise")
                            if name in advertised)
            minimum, maximum = state.get("min_raise_to"), state.get("max_raise_to")
            can_raise = ("raise" in choices and type(minimum) is int
                         and type(maximum) is int and 0 < minimum <= maximum)
            choices = tuple(name for name in choices if name != "raise" or can_raise)
            if not choices:
                return fallback
            fallback = (choices[0] if choices[0] != "raise" else
                        {"action": "raise", "amount": minimum})
            if not self._bounded_state(state):
                return fallback
            action = self._choose_action(state)
            if type(action) is str and action in choices and action != "raise":
                return action
            if type(action) is dict and can_raise and action.get("action") == "raise":
                amount = action.get("amount")
                if type(amount) is int and minimum <= amount <= maximum:
                    return action
            return fallback
        except Exception:
            return fallback

    @staticmethod
    def _bounded_state(state):
        """Reject malformed/unbounded work before touching strategy loops."""
        cards, board = state.get("hole_cards"), state.get("board")
        if type(cards) not in (tuple, list) or len(cards) != 2:
            return False
        if type(board) not in (tuple, list) or len(board) not in (0, 3, 4, 5):
            return False
        for card in (*cards, *board):
            if (type(card) is not str or len(card) != 2
                    or card[0] not in _VALUES or card[1] not in _SUITS):
                return False
        stacks = state.get("stacks")
        if type(stacks) is not dict or not 1 <= len(stacks) <= 8 or "my_bot" not in stacks:
            return False
        for name, amount in stacks.items():
            if type(name) is not str or len(name) > 64:
                return False
            if type(amount) is not int or amount < 0 or amount.bit_length() > 256:
                return False
        blinds = state.get("blinds")
        if type(blinds) is not dict:
            return False
        bb = blinds.get("big")
        if type(bb) is not int or bb <= 0 or bb.bit_length() > 256:
            return False
        for field in ("pot", "amount_to_call"):
            amount = state.get(field)
            if type(amount) is not int or amount < 0 or amount.bit_length() > 256:
                return False
        for field in ("min_raise_to", "max_raise_to"):
            amount = state.get(field)
            if type(amount) is not int or amount < 0 or amount.bit_length() > 256:
                return False
        count = state.get("players_remaining")
        if count is not None and (type(count) is not int or not 1 <= count <= 8):
            return False
        contributions = state.get("street_contributions", {})
        if type(contributions) is not dict or len(contributions) > 8:
            return False
        for amount in contributions.values():
            if type(amount) is not int or amount < 0 or amount.bit_length() > 256:
                return False
        active = state.get("active_players")
        if active is not None:
            if type(active) not in (tuple, list) or len(active) > 8:
                return False
            if any(type(name) is not str or name not in stacks for name in active):
                return False
        return True

    def _postflop(self, state):
        level, equity = _hand_strength(state)
        legal = state["legal_actions"]
        safe = "check" if "check" in legal else "fold"
        stack = state["stacks"]["my_bot"]
        cost = min(stack, state["amount_to_call"])
        pot = state["pot"]
        active = state.get("active_players", ())
        opponents = max(1, sum(n != "my_bot" for n in active))
        equity **= 1 + POST_MULTIWAY_PENALTY * (opponents - 1)
        invested = state.get("total_contributions", state.get("street_contributions", {})).get("my_bot", 0)
        starting = stack + invested
        committed = invested >= POST_COMMITTED_FRACTION * starting
        weak_budget = max(0, int(starting * POST_MAX_WEAK_INVESTMENT) - invested)
        if cost:
            if level < 3 and not committed and cost > weak_budget:
                return safe
            totals = state.get("total_contributions", {})
            cap = invested + cost
            eligible_pot = sum(min(c, cap) for c in totals.values()) if totals else pot
            if equity < cost / (eligible_pot + cost) + POST_CALL_MARGIN:
                return safe
            if level < 3 or "raise" not in legal:
                return "call" if "call" in legal else safe
        if "raise" not in legal:
            return safe
        if level >= 3:
            fraction = POST_VERY_STRONG_BET if level == 4 else POST_STRONG_BET
        elif (level == 1 and not cost and opponents <= 2 and
              self._rng.random() < POST_DRAW_BET_FREQUENCY):
            fraction = POST_DRAW_BET
        else:
            return safe
        street = state["max_raise_to"] - stack
        target = max(state["min_raise_to"], street + cost + int(pot * fraction))
        target = min(state["max_raise_to"], target)
        if level < 3 and not committed and target - street > weak_budget:
            return safe
        return {"action": "raise", "amount": target}

    def _all_in_call(self, state):
        """Price only chips we can win; distinguish calling from open-shoving."""
        stack = state["stacks"]["my_bot"]
        cost = min(stack, state["amount_to_call"])
        if not cost:
            return None
        contributions = state.get("street_contributions", {})
        active = state.get("active_players", tuple(state["stacks"]))
        raiser = state.get("last_raiser")
        if raiser not in state["stacks"] or raiser == "my_bot":
            raiser = max((n for n in active if n != "my_bot"),
                         key=lambda n: contributions.get(n, 0), default=None)
        if raiser is None:
            return None
        shover_stack = state["stacks"][raiser]
        if shover_stack and not state.get("opponent_all_in", False) and cost < stack:
            return None
        bb = state["blinds"]["big"]
        depth = (shover_stack + contributions.get(raiser, 0)) / bb
        index = (4 if depth <= SHOVER_VERY_SHORT_BB else
                 3 if depth <= SHOVER_SHORT_BB else
                 2 if depth <= SHOVER_MEDIUM_BB else 1)
        cards = state["hole_cards"]
        high, low = sorted(cards, key=lambda c: _VALUES[c[0]], reverse=True)
        hand = high[0] + low[0] + ("" if high[0] == low[0] else
                                  "s" if high[1] == low[1] else "o")
        equity = EQUITY[hand][index]
        callers = sum(n != "my_bot" and n != raiser and state["stacks"][n] == 0
                      and contributions.get(n, 0) > 0 for n in active)
        if callers:
            equity = equity ** (1 + MULTIWAY_EQUITY_EXPONENT * callers)
        fraction = cost / stack
        premium = (BUST_RISK_PREMIUM if fraction >= BUST_RISK_FRACTION else
                   CRIPPLE_RISK_PREMIUM if fraction >= CRIPPLE_RISK_FRACTION else
                   COVERED_RISK_PREMIUM)
        totals = state.get("total_contributions", contributions)
        cap = totals.get("my_bot", 0) + cost
        pot = sum(min(chips, cap) for chips in totals.values()) if totals else state["pot"]
        threshold = cost / (pot + cost) + premium
        safe = "check" if "check" in state["legal_actions"] else "fold"
        return "call" if equity >= threshold and "call" in state["legal_actions"] else safe

    def _stack_preflop(self, state):
        """Tournament sizing depends on effective chips, not only our stack."""
        legal = state["legal_actions"]
        safe = "check" if "check" in legal else "fold"
        cards = state["hole_cards"]
        high, low = sorted((_VALUES[c[0]] for c in cards), reverse=True)
        suited = cards[0][1] == cards[1][1]
        pair = high == low
        hand = ("23456789TJQKA"[high - 2] + "23456789TJQKA"[low - 2] +
                ("" if pair else "s" if suited else "o"))
        premium = (pair and high >= PREMIUM_PAIR_MIN) or (high, low) == (14, 13)
        strong = premium or (pair and high >= STRONG_PAIR_MIN) or (
            high == 14 and low >= STRONG_ACE_KICKER) or (high, low) == (13, 12)
        stacks = state["stacks"]
        total = state["max_raise_to"]
        stack = stacks["my_bot"]
        bb = state["blinds"]["big"]
        committed = total - stack
        contributions = state.get("street_contributions", {})
        active = state.get("active_players", tuple(stacks))
        opponent_total = max((stacks[n] + contributions.get(n, 0)
                              for n in active if n != "my_bot"), default=total)
        effective = min(total, opponent_total)
        depth = effective / bb
        cost = state["amount_to_call"]
        position = state.get("position", "early")
        if position not in ("early", "cutoff", "button", "small_blind", "big_blind"):
            position = "early"
        remaining = state.get("players_remaining", len(stacks))
        behind = state.get("players_left_to_act", max(0, remaining - 1))
        behind = max(0, min(7, behind))
        facing_raise = cost + committed > bb
        if depth < PUSH_FOLD_BB:
            bucket = max(1, min(PUSH_FOLD_BB, int(depth) + 1))
            allowed = CALL[bucket, behind] if facing_raise else SHOVE[bucket, position, behind]
            if hand not in allowed:
                return safe
            if "raise" in legal:
                return {"action": "raise", "amount": total}
            return "call" if "call" in legal else safe
        steal = (state.get("folded_to_me", False) and position in ("cutoff", "button")
                 and (pair or high == 14 or (high == 13 and low >= STEAL_KING_KICKER)))
        if not facing_raise and state.get("folded_to_me", False):
            if hand not in POSITION_OPEN[position]:
                return safe
            strong = True
        if (position == "big_blind" and facing_raise and not premium
                and cost <= BB_DEFEND_CALL_BB * bb
                and cost <= BB_DEFEND_STACK_FRACTION * stack
                and (pair or high >= 12 or (suited and high - low <= 2))
                and "call" in legal):
            return "call"
        if not strong and not steal:
            return safe
        if facing_raise:
            if cost > BIG_RAISE_BB * bb and not premium:
                return safe
            if premium and depth <= DEEP_STACK_BB:
                target = total
            elif depth > DEEP_STACK_BB and not premium:
                return "call" if "call" in legal else safe
            else:
                target = RERAISE_MULTIPLIER * (cost + committed)
        else:
            target = int((DEEP_OPEN_BB if depth > DEEP_STACK_BB else MID_OPEN_BB) * bb)
        if "raise" not in legal:
            return "call" if premium and "call" in legal else safe
        return {"action": "raise", "amount": max(state["min_raise_to"], min(total, target))}

    def _short_handed(self, state, high, low, suited, board, stack, bb):
        """Called only inside get_action's try/except guard."""
        legal = state["legal_actions"]
        safe = "check" if "check" in legal else "fold"
        call = "call" if "call" in legal else safe
        to_call = state["amount_to_call"]
        maximum = state["max_raise_to"]
        minimum = state["min_raise_to"]
        if type(minimum) is not int or type(maximum) is not int:
            return safe
        if minimum <= 0 or maximum < minimum:
            return safe
        committed = maximum - stack
        contributions = state.get("street_contributions", {})
        stacks = state["stacks"]
        active = state.get("active_players")
        if active is None:
            active = tuple(name for name, chips in stacks.items()
                           if chips > 0 or contributions.get(name, 0) > 0)
        opponents = [name for name in active if name != "my_bot"]
        if not opponents:
            return safe
        opponent_maximum = max(stacks[name] + contributions.get(name, 0)
                               for name in opponents)
        effective = min(maximum, opponent_maximum)
        covers = maximum >= opponent_maximum
        # All-in players cannot fold to pressure; include their hands when
        # deciding whether to bluff, even though their remaining stack is zero.
        all_can_fold = all(stacks[name] > 0 for name in opponents)
        any_can_fold = any(stacks[name] > 0 for name in opponents)
        pair = high == low

        if not board:
            wide = pair or high >= 12 or suited or high - low <= 2
            premium = (pair and high >= 10) or (high == 14 and low >= 12)
            short_call = (pair and high >= 7) or (high == 14 and low >= 10) or (
                high == 13 and low == 12
            )
            if to_call >= stack or not any_can_fold:
                return call if premium or (effective <= 12 * bb and short_call) else safe
            if not wide:
                return safe
            if to_call > 4 * bb and not premium:
                return call if effective <= 12 * bb and short_call else safe
            if "raise" not in legal:
                return call
            if maximum <= 12 * bb or (
                covers and all_can_fold and opponent_maximum <= 12 * bb
            ):
                target = maximum
            else:
                target = max((4 if premium else 3) * bb,
                             (3 if premium else 2) * (committed + to_call))
        else:
            cards = state["hole_cards"]
            combined = tuple(cards) + board
            category = _category(combined)
            made = category > _category(board)
            top = max(_VALUES[c[0]] for c in board)
            strong_pair = (pair and high > top) or (
                not pair and top in (high, low)
                and (low if high == top else high) >= 11
            )
            strong = made and (category >= 2 or strong_pair)
            pot = state["pot"]
            if strong:
                if "raise" not in legal or not any_can_fold:
                    return call
                # Put a covered opponent all-in when one pot-sized bet
                # already commits most or all of their effective stack.
                if covers and effective <= committed + to_call + pot:
                    target = maximum
                else:
                    target = committed + to_call + max(bb, pot)
            else:
                draw = False
                if len(board) < 5:
                    suits = [c[1] for c in combined]
                    draw = any(suits.count(c[1]) == 4 for c in cards)
                    if not draw:
                        ranks = {_VALUES[c[0]] for c in combined}
                        if 14 in ranks:
                            ranks.add(1)
                        draw = any(
                            sum(rank in ranks for rank in range(start, start + 5)) == 4
                            and any(start <= _VALUES[c[0]] < start + 5 for c in cards)
                            for start in range(1, 11)
                        )
                if to_call > 0:
                    # Pressure is not a reason to pay large bets with air.
                    return call if (made or draw) and to_call * 3 <= pot else safe
                if not any_can_fold or (not made and not all_can_fold):
                    return safe
                frequency = 0.8 if made else 0.6 if draw else 0.25
                if "raise" not in legal or self._rng.random() >= frequency:
                    return safe
                if covers and all_can_fold and (made or draw) and effective <= pot:
                    target = maximum
                else:
                    target = committed + max(bb, pot * 3 // 4)
        return {"action": "raise", "amount": max(minimum, min(target, maximum))}

    def _choose_action(self, state):
        """Return a legal action, or check/fold if state processing fails."""
        try:
            if not state["board"]:
                priced_call = self._all_in_call(state)
                if priced_call is not None:
                    return priced_call
                return self._stack_preflop(state)
            return self._postflop(state)
            legal = state["legal_actions"]
            safe = "check" if "check" in legal else "fold"
            cards = state["hole_cards"]
            if len(cards) != 2:
                return safe
            high, low = _VALUES[cards[0][0]], _VALUES[cards[1][0]]
            if low > high:
                high, low = low, high
            suited = cards[0][1] == cards[1][1]
            pair = high == low
            # Higher tiers take precedence over suited aces/connectors.
            if (pair and high >= 11) or (high, low) == (14, 13):
                tier = 3  # premium
            elif (pair and 8 <= high <= 10) or (high, low) in (
                (14, 12), (14, 11), (13, 12)
            ):
                tier = 2  # strong
            elif pair or (suited and (high == 14 or high - low == 1)):
                tier = 1  # playable
            else:
                tier = 0  # trash

            stack = state["stacks"]["my_bot"]
            big_blind = state["blinds"]["big"]
            if big_blind <= 0 or stack < 0:
                return safe
            board = tuple(state["board"])
            remaining = state.get("players_remaining")
            if remaining is None:
                # Legacy states may lack a count; include contributed chips
                # so a zero-behind all-in player is not mistaken for a bust.
                contributions = state.get("street_contributions", {})
                remaining = sum(chips > 0 or contributions.get(name, 0) > 0
                                for name, chips in state["stacks"].items())
            if 2 <= remaining <= 3:
                return self._short_handed(state, high, low, suited, board, stack, big_blind)
            to_call = state["amount_to_call"]
            call = "call" if "call" in legal else safe
            steal = (
                not board and state.get("folded_to_me", False)
                and state.get("position") in ("cutoff", "button")
                and (pair or high == 14 or (high == 13 and low >= 10))
            )
            if not board and stack < 12 * big_blind:
                if tier == 0 and not steal:
                    return "fold"
                if "raise" in legal:
                    target = state["max_raise_to"]
                elif "call" in legal and state["amount_to_call"] >= stack:
                    return "call"  # Calling commits the entire remaining stack.
                else:
                    return safe
            elif not board:
                # The current engine lacks opponent action/all-in metadata.
                # Accept an explicit flag if a future state supplies one;
                # otherwise recognize large calls and calls for our stack.
                big_raise = to_call > 3 * big_blind
                all_in = to_call >= stack or state.get("opponent_all_in", False)
                if to_call > 0 and (big_raise or all_in):
                    if tier != 3:
                        return safe
                if tier < 2 and not steal:
                    return safe
                if "raise" not in legal:
                    return call
                committed = state["max_raise_to"] - stack
                opening_size = (4 if tier == 3 else 3) * big_blind
                target = max(opening_size, 3 * (committed + to_call))
            else:
                category = _category(tuple(cards) + board)
                if category == 0 or category <= _category(board):
                    return safe
                pot = state["pot"]
                committed = state["max_raise_to"] - stack
                top = max(_VALUES[c[0]] for c in board)
                overpair = pair and high > top
                top_pair_good_kicker = (
                    not pair and top in (high, low)
                    and (low if high == top else high) >= 11
                )
                if category >= 2 or overpair or top_pair_good_kicker:
                    if "raise" not in legal:
                        return call
                    target = committed + to_call + max(1, pot)
                elif to_call > 0:
                    if to_call * 4 > pot:
                        return safe
                    return call
                else:
                    target = committed + max(1, pot // 2)

            if "raise" not in legal:
                return safe
            minimum, maximum = state["min_raise_to"], state["max_raise_to"]
            if type(minimum) is not int or type(maximum) is not int:
                return safe
            if minimum <= 0 or maximum < minimum:
                return safe
            return {"action": "raise", "amount": max(minimum, min(target, maximum))}
        except Exception:
            try:
                return "check" if "check" in state["legal_actions"] else "fold"
            except Exception:
                return "fold"
