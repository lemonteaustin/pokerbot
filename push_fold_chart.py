"""Import-time approximate short-stack ranges, indexed by BB/position/behind.

Heuristic equilibrium-shaped ranges, not a solved multiway Nash equilibrium.
Each cell is a frozenset of the 169 starting-hand names. No generation occurs
at decision time. Percentages count the actual 1,326 card combinations.
"""

RANKS = '23456789TJQKA'
POSITIONS = ('early', 'cutoff', 'button', 'small_blind', 'big_blind')
SHOVE_FRACTIONS = (0.95, 0.88, 0.78, 0.67, 0.58, 0.46, 0.42, 0.38,
                   0.34, 0.31, 0.29, 0.27, 0.25, 0.23, 0.21)
CALL_FRACTIONS = (0.60, 0.48, 0.38, 0.32, 0.28, 0.24, 0.21, 0.19,
                  0.17, 0.15, 0.14, 0.13, 0.12, 0.11, 0.10)
POSITION_BONUS = {'early': 0.0, 'cutoff': .03, 'button': .08,
                  'small_blind': .15, 'big_blind': .08}
BEHIND_PENALTY = .028
MIN_RANGE = .06
MAX_RANGE = 1.0


def _ordering():
    rows = []
    for a in range(2, 15):
        for b in range(2, a + 1):
            for suffix in (('',) if a == b else ('s', 'o')):
                # Pocket pairs are progressively mixed with broadway/ace hands.
                score = (32 + 2.5 * a if a == b else
                         2 * a + b + 3 * (suffix == 's') + 1.5 * (a - b == 1))
                hand = RANKS[a - 2] + RANKS[b - 2] + suffix
                rows.append((score, hand, 6 if a == b else 4 if suffix == 's' else 12))
    return sorted(rows, reverse=True)


RANKED_HANDS = _ordering()


def _range(fraction):
    target = max(MIN_RANGE, min(MAX_RANGE, fraction)) * 1326
    hands = []
    for _, hand, combinations in RANKED_HANDS:
        if target <= 0:
            break
        hands.append(hand)
        target -= combinations
    return frozenset(hands)


SHOVE = {(bb, position, behind): _range(SHOVE_FRACTIONS[bb - 1] +
          POSITION_BONUS[position] - max(0, behind - 1) * BEHIND_PENALTY)
         for bb in range(1, 16) for position in POSITIONS for behind in range(8)}
CALL = {(bb, behind): _range(CALL_FRACTIONS[bb - 1] - behind * BEHIND_PENALTY / 2)
        for bb in range(1, 16) for behind in range(8)}
