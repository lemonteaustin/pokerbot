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
"""


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


class MyBot:
    def get_action(self, state):
        """Return a legal action, or check/fold if state processing fails."""
        try:
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
