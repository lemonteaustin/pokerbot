"""Additional opponents; all decisions use public state and standard Python."""

from versions.my_bot_v2 import MyBot as SavedMyBot, _category
from versions.my_bot_v6 import MyBot as FrozenV6


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


def hand_score(cards):
    """Cheap ordinal starting-hand ranking, not an equity estimate."""
    a, b = sorted((VALUES[c[0]] for c in cards), reverse=True)
    return (40 + a * 3 if a == b else a * 2 + b +
            4 * (cards[0][1] == cards[1][1]) + 2 * (a - b == 1))


class NitBot:
    def get_action(self, state):
        a, b = sorted((VALUES[c[0]] for c in state['hole_cards']), reverse=True)
        safe = 'check' if 'check' in state['legal_actions'] else 'fold'
        if not ((a == b and a >= 11) or (a, b) == (14, 13)):
            return safe
        if not state['board']:
            return raise_to(state, max(3 * state['blinds']['big'],
                                      3 * state['amount_to_call']))
        if _category(state['hole_cards'] + state['board']) >= 2:
            return raise_to(state, state['max_raise_to'])
        return 'call' if 'call' in state['legal_actions'] else safe


class PushFoldBot:
    """Approximate equilibrium-shaped ranges; not a solved Nash strategy."""
    def get_action(self, state):
        safe = 'check' if 'check' in state['legal_actions'] else 'fold'
        if state['board']:
            return 'call' if 'call' in state['legal_actions'] else safe
        bb = state['blinds']['big']
        depth = state['max_raise_to'] / bb
        score = hand_score(state['hole_cards'])
        behind = state.get('players_left_to_act', 4)
        if state['amount_to_call'] > bb:
            cutoff = 38 if depth < 4 else 43 if depth < 8 else 47 if depth < 15 else 67
        else:
            cutoff = (23 if depth < 4 else 30 if depth < 8 else
                      35 if depth < 15 else 43 if depth < 25 else 67)
            cutoff += min(6, behind) * 1.5
        return raise_to(state, state['max_raise_to']) if score >= cutoff else safe


class CallingStationBot:
    def get_action(self, state):
        safe = 'check' if 'check' in state['legal_actions'] else 'fold'
        if not state['amount_to_call']:
            return safe
        cards, board = state['hole_cards'], state['board']
        if not board:
            good = hand_score(cards) >= 29
            cheap = state['amount_to_call'] <= 4 * state['blinds']['big']
            return 'call' if cheap or good else safe
        made = _category(cards + board) > _category(board)
        cheap = state['amount_to_call'] <= state['pot'] / 3
        return 'call' if made or cheap else safe


class PositionalTAGBot:
    def get_action(self, state):
        safe = 'check' if 'check' in state['legal_actions'] else 'fold'
        bb, call = state['blinds']['big'], state['amount_to_call']
        cards, board = state['hole_cards'], state['board']
        score = hand_score(cards)
        committed = state['street_contributions'].get('my_bot', 0)
        if not board:
            late = state['position'] in ('cutoff', 'button', 'small_blind')
            threshold = 36 if late and state['folded_to_me'] else 43
            if call > 3 * bb:
                threshold = 47 if call < 10 * bb else 67
            if score < threshold:
                return safe
            depth = state['max_raise_to'] / bb
            target = state['max_raise_to'] if depth <= 14 else max(
                int(2.5 * bb), 3 * (committed + call))
            return raise_to(state, target)
        category = _category(cards + board)
        made = category > _category(board)
        top = max(VALUES[c[0]] for c in board)
        ranks = [VALUES[c[0]] for c in cards]
        strong = made and (category >= 2 or top in ranks or ranks[0] == ranks[1] > top)
        if strong:
            return raise_to(state, committed + call + max(bb, state['pot'] * 2 // 3))
        return 'call' if made and call and call * 4 <= state['pot'] else safe


class SeatAdapter:
    """Give legacy bots their expected self-name, with anonymous opponents."""
    def __init__(self, bot, seat, alias='my_bot'):
        self.bot, self.seat, self.alias = bot, seat, alias

    def get_action(self, state):
        def rename(name):
            return self.alias if name == self.seat else 'hero_seat' if name == 'my_bot' else name
        adapted = dict(state)
        for field in ('stacks', 'street_contributions', 'total_contributions', 'starting_stacks'):
            if field in state:
                adapted[field] = {rename(k): v for k, v in state[field].items()}
        adapted['active_players'] = tuple(rename(n) for n in state['active_players'])
        adapted['self_name'] = self.alias
        if state.get('last_raiser'):
            adapted['last_raiser'] = rename(state['last_raiser'])
        return self.bot.get_action(adapted)


POOLS = {
    'WEAK': ('always_fold', 'always_fold', 'random', 'random', 'always_raise',
             'always_raise', 'calling_station', 'calling_station', 'loose_aggressive',
             'positional_tag'),
    'MIXED': ('random', 'always_call', 'always_raise', 'always_fold', 'tight_aggressive',
              'loose_aggressive', 'v2', 'nit', 'push_fold', 'calling_station', 'positional_tag', 'v6'),
    'TOUGH': ('tight_aggressive', 'positional_tag', 'push_fold', 'nit', 'loose_aggressive', 'v6'),
}
