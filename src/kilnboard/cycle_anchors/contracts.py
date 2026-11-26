from dataclasses import dataclass
from typing import Iterable

from ..stack_cards.contracts import Ticket


@dataclass(frozen=True, slots=True)
class Windows:
    train_end: int = 66
    calibration_end: int = 93
    holdout_end: int = 117
    asof: int = 126

    def __post_init__(self) -> None:
        if not (20 <= self.train_end < self.calibration_end < self.holdout_end <= self.asof):
            raise ValueError('训练、校准、回放和决策时点的顺序无效')
        if self.asof - self.holdout_end > 50:
            raise ValueError('决策日与回放截止超出档期')

    def bounds(self) -> dict[str, int]:
        return dict(train_end=self.train_end, calibration_end=self.calibration_end,
                    holdout_end=self.holdout_end, asof=self.asof)


@dataclass(frozen=True, slots=True)
class Snapshot:
    accepted: tuple[Ticket, ...]
    conflicts: tuple[str, ...]
    duplicate_arrivals: int
    not_yet_seen: int
    superseded: int

    def for_phase(self, phase: str) -> Iterable[Ticket]:
        return (ticket for ticket in self.accepted if ticket.phase == phase)


@dataclass(frozen=True, slots=True)
class Cohort:
    name: str
    lower: int
    upper: int
    known_until: int
    evaluated: tuple[Ticket, ...]
    immature: tuple[str, ...]
    censored: tuple[str, ...]
    locked: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.lower >= self.upper or self.known_until < self.upper:
            raise ValueError('回放区间无效')

    def counts(self) -> dict[str, int | str]:
        return dict(window=self.name, first_day=self.lower, exclusive_end=self.upper,
                    labels_before=self.known_until, included=len(self.evaluated),
                    pending_label=len(self.immature), right_censored=len(self.censored), handoff=len(self.locked))


@dataclass(frozen=True, slots=True)
class Vintage:
    train: Cohort
    calibration: Cohort
    holdout: Cohort
    live: tuple[Ticket, ...]
    snapshot: Snapshot
