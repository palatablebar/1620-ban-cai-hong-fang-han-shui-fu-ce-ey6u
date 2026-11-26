from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class Hold(StrEnum):
    CLEAR = 'clear'
    CHAIN = 'chain'
    RESERVED = 'reserved'


@dataclass(frozen=True, slots=True)
class Field:
    key: str
    title: str
    unit: str
    low: float
    high: float
    integer: bool = False

    def allowed(self, value: float) -> bool:
        margin = (self.high - self.low) * .18
        minimum = max(self.low * .45, self.low - margin) if self.low >= 0.0 else self.low - margin
        return minimum <= value <= self.high + margin


@dataclass(frozen=True, slots=True)
class Ticket:
    key: str
    region: str
    pool: str
    day: int
    received: int
    revision: int
    arrival: int
    window: int
    hold: Hold
    raw: tuple[float | None, ...]
    target: float | None
    outcome_day: int | None
    confirmed: bool | None
    complete: bool
    phase: Literal['history', 'live']

    def metadata(self) -> dict[str, str | int]:
        return dict(key=self.key, region=self.region, pool=self.pool, day=self.day,
                    revision=self.revision, arrival=self.arrival, window=self.window)

    def fingerprint(self) -> tuple:
        return (self.key, self.region, self.pool, self.day, self.revision, self.arrival,
                self.window, self.hold, self.raw, self.target, self.outcome_day, self.confirmed,
                self.complete, self.phase)


@dataclass(frozen=True, slots=True)
class Rejection:
    line: int
    key: str
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class ImportReport:
    tickets: tuple[Ticket, ...]
    rejected: tuple[Rejection, ...]
    data_lines: int
    dataset_hash: str

    def counts(self) -> dict[str, int]:
        return {'rows': self.data_lines, 'parsed': len(self.tickets), 'isolated': len(self.rejected)}


class FormatError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
