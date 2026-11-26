from bisect import bisect_right
from collections.abc import Iterable, Sequence
from math import log

from ..drying_features.contracts import Prepared
from .contracts import DriftBand

CUTS = (-2.,-1.,-.25,.25,1.,2.)


def frequency(values: Iterable[float], edges: Sequence[float] = CUTS) -> tuple[int,...]:
    bins = [0] * (len(edges)+1)
    for value in values:
        bins[bisect_right(edges,value)] += 1
    return tuple(bins)


def stability_index(reference: Sequence[int], current: Sequence[int], smoothing: float = .6) -> float:
    if len(reference) != len(current) or len(reference) == 0:
        raise ValueError('分布带须有一致的上下界')
    if smoothing <= 0 or any(size < 0 for size in (*reference,*current)):
        raise ValueError('频数和平滑设置无效')
    n = len(reference)
    baseline = sum(reference)+n*smoothing
    recent = sum(current)+n*smoothing
    contribution = 0.
    for before,after in zip(reference,current,strict=True):
        previous = (before+smoothing)/baseline
        next_value = (after+smoothing)/recent
        contribution += (next_value-previous)*log(next_value/previous)
    return contribution


def draw(name: str, index: int, train: tuple[Prepared,...], probes: tuple[Prepared,...]) -> DriftBand:
    current = [signal.values[index] for signal in probes]
    reference = frequency(signal.values[index] for signal in train)
    incoming = frequency(current)
    outside = sum(abs(value)>2. for value in current)
    return DriftBand(name,stability_index(reference,incoming),reference,incoming,outside)
