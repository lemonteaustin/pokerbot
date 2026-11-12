"""Tournament bot v7: statistically retained changes, standard library only.

Tune numeric policy constants below. Variant-specific cards, rankings and
range data are confined to part 2. No simulation or I/O occurs in decisions.
"""


import random
from collections import namedtuple


# Tunable policy constants (blind depths are in BB).


MAX_PLAYERS = 8
MAX_HANDS = 200
MAX_LEGAL_ACTIONS = 8
MAX_INTEGER_BITS = 256
MAX_ID_LENGTH = 64
POST_DRAW_MAX_OPPONENTS = 2


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
BB_DEFEND_CALL_BB = 1.5
BB_DEFEND_STACK_FRACTION = 0.08
SHOVER_VERY_SHORT_BB = 4
SHOVER_SHORT_BB = 8
SHOVER_MEDIUM_BB = 15
BUST_RISK_FRACTION = 0.80
CRIPPLE_RISK_FRACTION = 0.40
BUST_RISK_PREMIUM = 0.09
CRIPPLE_RISK_PREMIUM = 0.05
COVERED_RISK_PREMIUM = 0.015
MULTIWAY_EQUITY_EXPONENT = 0.85
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
SHOVE_FRACTIONS = (0.95, 0.88, 0.78, 0.67, 0.58, 0.46, 0.42, 0.38,
                   0.34, 0.31, 0.29, 0.27, 0.25, 0.23, 0.21)
CALL_FRACTIONS = (0.60, 0.48, 0.38, 0.32, 0.28, 0.24, 0.21, 0.19,
                  0.17, 0.15, 0.14, 0.13, 0.12, 0.11, 0.10)
POSITION_BONUS = {'early': 0.0, 'cutoff': .03, 'button': .08,
                  'small_blind': .15, 'big_blind': .08}
BEHIND_PENALTY = .028
MIN_RANGE = .06
MAX_RANGE = 1.0
CHART_PAIR_BASE = 32
CHART_PAIR_WEIGHT = 2.5
CHART_HIGH_WEIGHT = 2
CHART_SUITED_BONUS = 3
CHART_CONNECTED_BONUS = 1.5
CHART_CALL_BEHIND_DIVISOR = 2


# Part 1: safe_action wrapper and bounded public-state validation.


def safe_action(bot, state):
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



def _bounded_state(state):
    """Reject malformed/unbounded work before touching strategy loops."""
    if not _valid_cards(state):
        return False
    stacks = state.get("stacks")
    if type(stacks) is not dict or not 1 <= len(stacks) <= MAX_PLAYERS or "my_bot" not in stacks:
        return False
    for name, amount in stacks.items():
        if type(name) is not str or len(name) > MAX_ID_LENGTH:
            return False
        if type(amount) is not int or amount < 0 or amount.bit_length() > MAX_INTEGER_BITS:
            return False
    blinds = state.get("blinds")
    if type(blinds) is not dict:
        return False
    bb = blinds.get("big")
    if type(bb) is not int or bb <= 0 or bb.bit_length() > MAX_INTEGER_BITS:
        return False
    for field in ("pot", "amount_to_call"):
        amount = state.get(field)
        if type(amount) is not int or amount < 0 or amount.bit_length() > MAX_INTEGER_BITS:
            return False
    for field in ("min_raise_to", "max_raise_to"):
        amount = state.get(field)
        if type(amount) is not int or amount < 0 or amount.bit_length() > MAX_INTEGER_BITS:
            return False
    count = state.get("players_remaining")
    if count is not None and (type(count) is not int or not 1 <= count <= MAX_PLAYERS):
        return False
    contributions = state.get("street_contributions", {})
    if type(contributions) is not dict or len(contributions) > MAX_PLAYERS:
        return False
    for amount in contributions.values():
        if type(amount) is not int or amount < 0 or amount.bit_length() > MAX_INTEGER_BITS:
            return False
    active = state.get("active_players")
    if active is not None:
        if type(active) not in (tuple, list) or len(active) > MAX_PLAYERS:
            return False
        if any(type(name) is not str or name not in stacks for name in active):
            return False
    for field in ("total_contributions", "starting_stacks"):
        values = state.get(field, {})
        if type(values) is not dict or len(values) > MAX_PLAYERS:
            return False
        for value in values.values():
            if type(value) is not int or value < 0 or value.bit_length() > MAX_INTEGER_BITS:
                return False
    return True


# Part 2: variant-specific hand strength and import-time lookup data.


from preflop_equity import EQUITY


POSITION_EARLY_PAIRS = "88 99 TT JJ QQ KK AA"
POSITION_EARLY_BROADWAY = "AJs AQs AKs AQo AKo KQs"
POSITION_CUTOFF_EXTRA = "22 33 44 55 66 77 A2s A3s A4s A5s A6s A7s A8s A9s ATs ATo AJo K9s KTs KJs KTo KJo KQo Q9s QTs QJs QJo J9s JTs T9s 98s 87s 76s"
POSITION_BUTTON_EXTRA = "A2o A3o A4o A5o A6o A7o A8o A9o K2s K3s K4s K5s K6s K7s K8s K8o K9o Q8s QTo J8s JTo T8s T9o 97s 86s 75s 65s 54s"
POSITION_SMALL_BLIND_EXTRA = "K5o K6o K7o Q7s Q8o Q9o J7s J9o T7s T8o 98o 96s 87o 85s 76o 64s 53s"
_EARLY_OPEN = frozenset((POSITION_EARLY_PAIRS + " " + POSITION_EARLY_BROADWAY).split())
_CUTOFF_OPEN = _EARLY_OPEN | frozenset(POSITION_CUTOFF_EXTRA.split())
_BUTTON_OPEN = _CUTOFF_OPEN | frozenset(POSITION_BUTTON_EXTRA.split())
_SMALL_BLIND_OPEN = _BUTTON_OPEN | frozenset(POSITION_SMALL_BLIND_EXTRA.split())
POSITION_OPEN = {"early": _EARLY_OPEN, "cutoff": _CUTOFF_OPEN,
                 "button": _BUTTON_OPEN, "small_blind": _SMALL_BLIND_OPEN,
                 "big_blind": _BUTTON_OPEN}
_VALUES = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}
_SUITS = {suit: index for index, suit in enumerate("cdhs")}
RANKS = '23456789TJQKA'
POSITIONS = ('early', 'cutoff', 'button', 'small_blind', 'big_blind')


def _valid_cards(state):
    cards, board = state.get("hole_cards"), state.get("board")
    if type(cards) not in (tuple, list) or len(cards) != 2:
        return False
    if type(board) not in (tuple, list) or len(board) not in (0, 3, 4, 5):
        return False
    for card in (*cards, *board):
        if (type(card) is not str or len(card) != 2
                or card not in _VALID_CARDS):
            return False
    return True



def _score_straight(mask):
    mask |= (mask >> 13) & 2
    runs = mask & (mask >> 1) & (mask >> 2) & (mask >> 3) & (mask >> 4)
    return runs.bit_length() + 3 if runs else 0


def _score_ids(cards):
    counts = [0] * 15
    suits = [0] * 4
    masks = [0] * 4
    mask = 0
    for rank, suit in cards:
        counts[rank] += 1
        suits[suit] += 1
        masks[suit] |= 1 << rank
        mask |= 1 << rank
    flush = next((masks[s] for s in range(4) if suits[s] >= 5), 0)
    if flush:
        high = _score_straight(flush)
        if high:
            return (8, high)
    ranks = [r for r in range(14, 1, -1) if counts[r]]
    quads = [r for r in ranks if counts[r] == 4]
    if quads:
        q = quads[0]
        return (7, q, next(r for r in ranks if r != q))
    trips = [r for r in ranks if counts[r] >= 3]
    pairs = [r for r in ranks if counts[r] >= 2]
    if trips and len(pairs) > 1:
        return (6, trips[0], next(r for r in pairs if r != trips[0]))
    if flush:
        return (5, *[r for r in ranks if flush & (1 << r)][:5])
    high = _score_straight(mask)
    if high:
        return (4, high)
    if trips:
        return (3, trips[0], *[r for r in ranks if r != trips[0]][:2])
    if len(pairs) >= 2:
        return (2, *pairs[:2], next(r for r in ranks if r not in pairs[:2]))
    if pairs:
        return (1, pairs[0], *[r for r in ranks if r != pairs[0]][:3])
    return (0, *ranks[:5])


def _showdown_score(cards):
    return _score_ids(tuple((_VALUES[c[0]], _SUITS[c[1]]) for c in cards))


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


def _ordering():
    rows = []
    for a in range(2, 15):
        for b in range(2, a + 1):
            for suffix in (('',) if a == b else ('s', 'o')):
                # Pocket pairs are progressively mixed with broadway/ace hands.
                score = (CHART_PAIR_BASE + CHART_PAIR_WEIGHT * a if a == b else
                         CHART_HIGH_WEIGHT * a + b + CHART_SUITED_BONUS * (suffix == 's') + CHART_CONNECTED_BONUS * (a - b == 1))
                hand = RANKS[a - 2] + RANKS[b - 2] + suffix
                rows.append((score, hand, 6 if a == b else 4 if suffix == 's' else 12))
    return sorted(rows, reverse=True)

def _range(fraction):
    target = max(MIN_RANGE, min(MAX_RANGE, fraction)) * 1326
    hands = []
    for _, hand, combinations in RANKED_HANDS:
        if target <= 0:
            break
        hands.append(hand)
        target -= combinations
    return frozenset(hands)

RANKED_HANDS = _ordering()

SHOVE = {(bb, position, behind): _range(SHOVE_FRACTIONS[bb - 1] +
          POSITION_BONUS[position] - max(0, behind - 1) * BEHIND_PENALTY)
         for bb in range(1, 16) for position in POSITIONS for behind in range(8)}

CALL = {(bb, behind): _range(CALL_FRACTIONS[bb - 1] - behind * BEHIND_PENALTY / CHART_CALL_BEHIND_DIVISOR)
        for bb in range(1, 16) for behind in range(8)}


PreflopFeatures = namedtuple("PreflopFeatures", "key premium strong steal defend equity")


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



# Part 3: tournament logic (stack depth, position, risk and betting).


class MyBot:

    def get_action(self, state):
        return safe_action(self, state)

    def __init__(self):
        # Private reproducible stream; never changes the deck RNG.
        self._rng = random.Random(0)

    def _choose_action(self, state):
        """Return a legal action, or check/fold if state processing fails."""
        if not state["board"]:
            priced_call = self._all_in_call(state)
            if priced_call is not None:
                return priced_call
            return self._stack_preflop(state)
        return self._postflop(state)

    def _stack_preflop(self, state):
        """Tournament sizing depends on effective chips, not only our stack."""
        legal = state["legal_actions"]
        safe = "check" if "check" in legal else "fold"
        features = _preflop_features(state["hole_cards"])
        hand, premium, strong = features.key, features.premium, features.strong
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
                 and features.steal)
        if not facing_raise and state.get("folded_to_me", False):
            if hand not in POSITION_OPEN[position]:
                return safe
            strong = True
        if (position == "big_blind" and facing_raise and not premium
                and cost <= BB_DEFEND_CALL_BB * bb
                and cost <= BB_DEFEND_STACK_FRACTION * stack
                and features.defend
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
        features = _preflop_features(state["hole_cards"])
        hand = features.key
        equity = features.equity[index]
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
        elif (level == 1 and not cost and opponents <= POST_DRAW_MAX_OPPONENTS and
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
