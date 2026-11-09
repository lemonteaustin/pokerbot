"""Additional opponents; all decisions use public state and standard Python."""

from my_bot_v2 import MyBot as SavedMyBot, _category


VALUES = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}


def raise_to(state, target):
    if "raise" in state["legal_actions"]:
        return {"action": "raise", "amount": max(
            state["min_raise_to"], min(target, state["max_raise_to"])
        )}
    return "check" if "check" in state["legal_actions"] else "call"


class SavedBotOpponent:
    """Run the frozen strategy with its expected self-name and own stack."""

    def __init__(self):
        self.bot = SavedMyBot()

    def get_action(self, state):
        adapted = dict(state)
        stacks = dict(state["stacks"])
        # Swap names to preserve every stack without overwriting an opponent.
        stacks["my_bot"], stacks["my_bot_v2"] = (
            stacks["my_bot_v2"], stacks["my_bot"]
        )
        adapted["stacks"] = stacks
        return self.bot.get_action(adapted)


class TightAggressiveBot:
    """Play 88+, AJ+, KQ; raise strong holdings and avoid costly weak calls."""

    def get_action(self, state):
        cards = state["hole_cards"]
        high, low = sorted((VALUES[c[0]] for c in cards), reverse=True)
        board = state["board"]
        to_call = state["amount_to_call"]
        bb = state["blinds"]["big"]
        stack = state["stacks"]["tight_aggressive"]
        safe = "check" if "check" in state["legal_actions"] else "fold"
        committed = state["max_raise_to"] - stack
        premium = (high == low and high >= 11) or (high, low) == (14, 13)
        if not board:
            good = (high == low and high >= 8) or (
                high == 14 and low >= 11
            ) or (high, low) == (13, 12)
            if not good or (to_call > 4 * bb and not premium):
                return safe
            target = state["max_raise_to"] if stack < 12 * bb else max(
                4 * bb, 3 * (committed + to_call)
            )
            return raise_to(state, target)

        category = _category(tuple(cards) + tuple(board))
        if category <= _category(board):
            return safe
        top = max(VALUES[c[0]] for c in board)
        strong_pair = (high == low and high >= top) or (
            high != low and top in (high, low)
            and (low if high == top else high) >= 11
        )
        if category >= 2 or strong_pair:
            return raise_to(state, committed + to_call + max(bb, state["pot"]))
        if to_call and to_call * 4 <= state["pot"]:
            return "call"
        return safe


class LooseAggressiveBot:
    """Wide range, frequent raises, draws and occasional postflop bluffs."""

    def __init__(self, rng):
        self.rng = rng

    def get_action(self, state):
        cards = state["hole_cards"]
        high, low = sorted((VALUES[c[0]] for c in cards), reverse=True)
        suited = cards[0][1] == cards[1][1]
        board = state["board"]
        to_call = state["amount_to_call"]
        bb = state["blinds"]["big"]
        stack = state["stacks"]["loose_aggressive"]
        committed = state["max_raise_to"] - stack
        safe = "check" if "check" in state["legal_actions"] else "fold"
        if not board:
            playable = high == low or high >= 12 or suited or high - low <= 2
            if not playable:
                return safe
            premium = (high == low and high >= 10) or (high == 14 and low >= 12)
            if to_call > 8 * bb and not premium:
                return safe
            if premium or self.rng.random() < 0.75:
                target = state["max_raise_to"] if stack < 12 * bb else max(
                    3 * bb, 2 * (committed + to_call)
                )
                return raise_to(state, target)
            return "call" if "call" in state["legal_actions"] else safe

        combined = tuple(cards) + tuple(board)
        category = _category(combined)
        made = category > _category(board)
        suits = [card[1] for card in combined]
        flush_draw = len(board) < 5 and any(
            suits.count(card[1]) == 4 for card in cards
        )
        ranks = {VALUES[card[0]] for card in combined}
        if 14 in ranks:
            ranks.add(1)
        straight_draw = len(board) < 5 and any(
            sum(rank in ranks for rank in range(start, start + 5)) == 4
            for start in range(1, 11)
        )
        draw = flush_draw or straight_draw
        pot = state["pot"]
        if to_call > pot // 2 and not (made and category >= 2):
            return safe
        if (made and category >= 2) or self.rng.random() < (
            0.75 if made else 0.55 if draw else 0.25
        ):
            return raise_to(state, committed + to_call + max(bb, pot * 3 // 4))
        if (made or draw) and to_call and to_call * 3 <= pot:
            return "call"
        return safe
