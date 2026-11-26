from dataclasses import dataclass, replace
from typing import Protocol

from ..drying_features.contracts import Prepared


@dataclass(frozen=True, slots=True)
class Probe:
    standard: tuple[float, ...]
    raw: tuple[float, ...]
    region: str
    pool: str
    day: int
    key: str

    @classmethod
    def from_prepared(cls, signal: Prepared):
        source = signal.record
        return cls(signal.values, signal.raw, source.region, source.pool, source.day, source.key)

    def with_reference(self, index: int, raw_index: int | None, medians: tuple[float, ...]):
        raw = self.raw
        if raw_index is not None:
            raw = (*raw[:raw_index], medians[raw_index], *raw[raw_index + 1:])
        return replace(self, raw=raw, standard=(*self.standard[:index], 0.0, *self.standard[index + 1:]))


@dataclass(frozen=True, slots=True)
class LearningRow:
    probe: Probe
    outcome: float
    complete: bool
    confirmed: bool | None


class Estimator(Protocol):
    def predict(self, probe: Probe) -> float: ...
    def describe(self) -> dict: ...


@dataclass(frozen=True, slots=True)
class FittedModel:
    estimator: Estimator
    baseline: float
    signature: str
    rows: int
    last_seen: int
    feature_signature: str
    input_medians: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Score:
    value: float
    contributions: tuple[tuple[str, float], ...]

    def summary(self) -> list[dict[str, float | str]]:
        return [{'feature': feature, 'delta': delta} for feature, delta in self.contributions]
