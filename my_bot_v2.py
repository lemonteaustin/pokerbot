"""Fast tier-based strategy using only the simulator's public state.

Raises specify the total contribution on this street. Under 12 BB, use
preflop push/fold; postflop always requires a made hand for a value bet.
Big means a call over 3 BB preflop or over half the visible pot postflop.
Good kicker means J+. Board-only made hands are checked or folded.
"""


_VALUES = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}


def _category(cards):
    """Made-hand category in O(cards + 13), without combination searches."""
    counts = [0] * 15
    suits = {}
    for card in cards:
        rank = _VALUES[card[0]]
        counts[rank] += 1
        suits.setdefault(card[1], set()).add(rank)

    def straight(ranks):
        run = 0
        for rank in range(1, 15):
            if (14 if rank == 1 else rank) in ranks:
                run += 1
                if run >= 5:
                    return True
            else:
                run = 0
        return False

    flush = next((ranks for ranks in suits.values() if len(ranks) >= 5), None)
    if flush is not None and straight(flush):
        return 8
    if 4 in counts:
        return 7
    triples = sum(count >= 3 for count in counts)
    pairs = sum(count >= 2 for count in counts)
    if triples and pairs >= 2:
        return 6
    if flush is not None:
        return 5
    if straight({rank for rank, count in enumerate(counts) if count}):
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
            high, low = sorted((_VALUES[c[0]] for c in cards), reverse=True)
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
            if not board and stack < 12 * big_blind:
                if tier == 0:
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
                    return call if tier == 3 else safe
                if tier == 3:
                    target = 3 * big_blind
                elif tier == 2:
                    return "call" if "call" in legal else safe
                else:
                    return safe
            else:
                category = _category(tuple(cards) + board)
                if category == 0 or category <= _category(board):
                    return safe
                pot = state["pot"]
                committed = state["max_raise_to"] - stack
                if category >= 2:
                    if "raise" not in legal:
                        return call
                    target = committed + max(1, pot)
                elif to_call > 0:
                    top = max(_VALUES[c[0]] for c in board)
                    top_pair_good_kicker = (
                        not pair and top in (high, low)
                        and (low if high == top else high) >= 11
                    )
                    if to_call * 2 > pot and not top_pair_good_kicker:
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
