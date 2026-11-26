from math import ceil
from statistics import mean

from .contracts import Adjustment, Block, ValidationPoint


def conformal_radius(points: list[ValidationPoint], coverage: float = .82) -> float:
    values = sorted(abs(row.estimate-row.observed) for row in points if row.confirmed)
    if not values:
        return 0.0
    rank = min(len(values), max(1, ceil((len(values)+1) * coverage)))
    return values[rank-1]


def group_ties(points: list[ValidationPoint]) -> list[tuple[float, int, float]]:
    groups: dict[float, list[int]] = {}
    for point in points:
        previous = groups.setdefault(point.estimate, [0,0])
        previous[0] += 1
        previous[1] += int(point.observed)
    return [(edge, *totals) for edge, totals in sorted(groups.items())]


def pooled_blocks(points: list[ValidationPoint], probability_input: bool) -> tuple[Block, ...]:
    n = len(points)
    prior = (sum(point.observed for point in points)+1) / (n+2)
    desired = max(6, n//7)
    stop, count, positives = 0., 0, 0
    result: list[Block] = []

    def merge(block: Block):
        result.append(block)
        while len(result) > 1 and result[-2].fraction > result[-1].fraction:
            right, left = result.pop(), result.pop()
            result.append(Block(right.end, right.count + left.count, right.positive + left.positive))

    for end, weight, total in group_ties(points):
        stop = end
        count += weight
        positives += total
        if count >= desired:
            reference = min(.98, max(.02, end)) if probability_input else prior
            merge(Block(stop, count + 2, positives + .9*prior + 1.1*reference))
            count, positives = 0, 0
    if count:
        if count < desired//2 and result:
            previous = result.pop()
            merge(Block(stop, previous.count+count, previous.positive+positives))
        else:
            merge(Block(stop, count+2, positives+2*prior))
    return tuple(result)


def empirical_rank(points: list[ValidationPoint]) -> tuple[Block, ...]:
    ordered = sorted(point.estimate for point in points)
    total = len(ordered)
    if not ordered:
        return ()
    totals = {value: index for index,value in enumerate(ordered, start=1)}
    return tuple(Block(end, total+1, rank-.5) for end,rank in totals.items())


def fit_adjustment(points: list[ValidationPoint], native_scale: bool, probability_input: bool) -> Adjustment:
    matured = [row for row in points if row.confirmed]
    if native_scale:
        return Adjustment('分窗经验误差带', (), conformal_radius(matured), len(matured), True)
    if len(matured) >= 15 and 0 < sum(point.observed for point in matured) < len(matured):
        buckets = pooled_blocks(matured, probability_input)
        if len(buckets) >= 2:
            return Adjustment('留窗单调概率校准', buckets, 0.0, len(matured), False)
    if probability_input:
        return Adjustment('原始后验概率', (), 0.0, len(matured), False)
    return Adjustment('历史异常百分位', empirical_rank(matured), 0.0, len(matured), False)
