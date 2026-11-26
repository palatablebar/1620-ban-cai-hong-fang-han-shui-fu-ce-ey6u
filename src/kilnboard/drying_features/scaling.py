from collections.abc import Sequence
from math import isfinite
from statistics import median

from .contracts import Axis


def quantile(values: Sequence[float], probability: float) -> float:
    if not values or not 0 <= probability <= 1:
        raise ValueError('分位需要数据支持和合法概率')
    ordered = sorted(values)
    index = probability * (len(ordered) - 1)
    lower = int(index)
    upper = min(len(ordered) - 1, lower + 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def fit_axis(name: str, values: Sequence[float]) -> Axis:
    if not values or not all(isfinite(number) for number in values):
        raise ValueError(f'{name} 缺可用建模值')
    location = median(values)
    q25, q75 = quantile(values, .25), quantile(values, .75)
    spread = (q75 - q25) / 1.349
    if spread < 1e-7:
        spread = 1.4826 * median(abs(item - location) for item in values)
    if spread < 1e-7:
        spread = (max(values) - min(values)) / 6.0
    constant = spread < 1e-7
    return Axis(name, location, 1.0 if constant else spread, quantile(values, .01), quantile(values, .99), constant)


def recover(raw: tuple[float | None, ...], medians: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(baseline if value is None else value for value, baseline in zip(raw, medians, strict=True))


def clipped(value: float, floor: float = -12.0, ceiling: float = 12.0) -> float:
    return max(floor, min(ceiling, value))


def support_distance(value: float, standardized: float, axis: Axis) -> float:
    if axis.constant:
        return 0.0 if abs(value - axis.median) < 1e-7 else 13.0
    edge_distance = max(axis.low - value, 0.0, value - axis.high) / axis.scale
    return max(abs(standardized), edge_distance * 1.35)
