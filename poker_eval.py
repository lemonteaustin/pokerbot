"""Exact five-to-seven-card Hold'em evaluator; standard library only."""

VALUES = {r: i for i, r in enumerate('23456789TJQKA', 2)}
SUITS = {s: i for i, s in enumerate('cdhs')}
CARD = {r + s: (v, SUITS[s]) for r, v in VALUES.items() for s in SUITS}


def straight(mask):
    mask |= (mask >> 13) & 2
    runs = mask & (mask >> 1) & (mask >> 2) & (mask >> 3) & (mask >> 4)
    return runs.bit_length() + 3 if runs else 0


def evaluate_ids(cards):
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
        high = straight(flush)
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
    high = straight(mask)
    if high:
        return (4, high)
    if trips:
        return (3, trips[0], *[r for r in ranks if r != trips[0]][:2])
    if len(pairs) >= 2:
        return (2, *pairs[:2], next(r for r in ranks if r not in pairs[:2]))
    if pairs:
        return (1, pairs[0], *[r for r in ranks if r != pairs[0]][:3])
    return (0, *ranks[:5])


def evaluate(cards):
    return evaluate_ids(tuple((VALUES[c[0]], SUITS[c[1]]) for c in cards))
