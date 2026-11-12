"""Exact ICM finishing-place probabilities, including elimination ties."""

PAYOUTS = {'TOP3': (50, 30, 20, 0, 0, 0, 0, 0),
           'FLAT': (40, 30, 20, 10, 0, 0, 0, 0),
           'LINEAR': (8, 7, 6, 5, 4, 3, 2, 1)}
BLIND_GROWTH = {'doubling': 2.0, 'x1.5': 1.5}


def icm_probabilities(stacks):
    """P(place | chips): exact subset DP, O(n * 2**n), no Monte Carlo."""
    n = len(stacks)
    total = sum(stacks)
    result = [[0.0] * n for _ in stacks]
    weights = [0.0] * (1 << n)
    chips = [0] * (1 << n)
    weights[0] = 1.0
    for mask in range(1 << n):
        if mask:
            bit = mask & -mask
            chips[mask] = chips[mask ^ bit] + stacks[bit.bit_length() - 1]
        left = total - chips[mask]
        if not left:
            continue
        rank = mask.bit_count()
        for i, stack in enumerate(stacks):
            bit = 1 << i
            if not mask & bit:
                probability = weights[mask] * stack / left
                result[i][rank] += probability
                weights[mask | bit] += probability
    return result


class Finishes(dict):
    """Display ranks plus actual points-relevant place probabilities."""
    def __init__(self, ranks, survivors):
        super().__init__(ranks)
        self.survivors = survivors

    def probabilities(self):
        n = len(self)
        rows = {name: [0.0] * n for name in self}
        groups = {}
        for name, rank in self.items():
            if name not in self.survivors:
                groups.setdefault(rank, []).append(name)
        for rank, names in groups.items():
            start = int(rank - (len(names) - 1) / 2) - 1
            for name in names:
                rows[name][start:start + len(names)] = [1 / len(names)] * len(names)
        names = list(self.survivors)
        for name, row in zip(names, icm_probabilities(list(self.survivors.values()))):
            rows[name][:len(names)] = row
        return rows


def tournament_points(finishes, payouts=PAYOUTS['TOP3']):
    if isinstance(payouts, str):
        payouts = PAYOUTS[payouts]
    if not isinstance(finishes, Finishes):
        groups = {}
        for name, rank in finishes.items():
            groups.setdefault(rank, []).append(name)
        result = {}
        for rank, names in groups.items():
            first = int(rank - (len(names) - 1) / 2) - 1
            value = sum(payouts[first:first + len(names)]) / len(names)
            result.update({name: value for name in names})
        return result
    return {name: sum(p * award for p, award in zip(row, payouts))
            for name, row in finishes.probabilities().items()}
