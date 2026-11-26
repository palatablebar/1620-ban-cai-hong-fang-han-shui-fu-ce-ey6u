from dataclasses import dataclass
from enum import StrEnum

from ..stack_cards.contracts import Ticket


class SignalFlag(StrEnum):
    PARTIAL = 'partial_measurement'
    TOO_FEW = 'insufficient_measurements'
    UNSEEN = 'unseen_region'
    DISTANT = 'outside_training_support'


@dataclass(frozen=True, slots=True)
class Axis:
    name: str
    median: float
    scale: float
    low: float
    high: float
    constant: bool

    def z(self, value: float) -> float:
        return (value - self.median) / self.scale


@dataclass(frozen=True, slots=True)
class FittedSignals:
    input_medians: tuple[float, ...]
    axes: tuple[Axis, ...]
    regions: frozenset[str]
    support: int
    signature: str


@dataclass(frozen=True, slots=True)
class Prepared:
    record: Ticket
    raw: tuple[float, ...]
    unscaled: tuple[float, ...]
    values: tuple[float, ...]
    flags: tuple[SignalFlag, ...]
    missing: tuple[str, ...]
    maximum_distance: float

    def can_score(self) -> bool:
        return not any(flag in (SignalFlag.UNSEEN, SignalFlag.TOO_FEW, SignalFlag.DISTANT) for flag in self.flags)

    def evidence(self) -> dict:
        return dict(raw=list(self.raw), signals=list(self.unscaled), standardized=list(self.values),
                    flags=list(self.flags), missing=list(self.missing), maximum_distance=self.maximum_distance)
