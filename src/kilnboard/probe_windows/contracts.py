from dataclasses import dataclass
from enum import StrEnum

from ..drying_features.contracts import Prepared


class Disposition(StrEnum):
    BOOKED = 'booked'
    WAIT = 'wait'
    MANUAL = 'manual'
    NORMAL = 'normal'
    LOCKED = 'locked'


@dataclass(frozen=True, slots=True)
class Scenario:
    budget: int
    reserve: int = 0
    region: str | None = None
    start: int = 360
    stop: int = 1005

    def __post_init__(self) -> None:
        if (type(self.budget) is not int or type(self.reserve) is not int or
            not 0 <= self.reserve <= self.budget <= 10000):
            raise ValueError('预算与预留须为整数，且在 0 至 10000 之间')
        if type(self.start) is not int or type(self.stop) is not int or not 0 <= self.start < self.stop <= 1440:
            raise ValueError('服务窗口起止不合法')

    @property
    def spendable(self) -> int:
        return self.budget - self.reserve


@dataclass(frozen=True, slots=True)
class Draft:
    signal: Prepared
    state: Disposition
    units: int
    minimum: int
    step: int
    priority: float
    duration: int
    why: str
    resource: str


@dataclass(frozen=True, slots=True)
class Candidate:
    draft: Draft
    estimate: float | None
    range: tuple[float,float] | None
    explanations: tuple[tuple[str,float],...]


@dataclass(frozen=True, slots=True)
class Booking:
    candidate: Candidate
    state: Disposition
    assigned: int
    start: int | None
    end: int | None
    why: str

    @property
    def key(self):
        return self.candidate.draft.signal.record.key


@dataclass(frozen=True, slots=True)
class Schedule:
    rows: tuple[Booking,...]
    used: int
    left: int
    protected: int
    by_region: dict[str,int]
    by_resource: dict[str,int]

    def verify(self, scenario: Scenario) -> None:
        units = sum(row.assigned for row in self.rows)
        if units != self.used or self.used+self.left+self.protected != scenario.budget:
            raise RuntimeError('派工额度与预留不守恒')
        if self.used != sum(self.by_region.values()) or self.used != sum(self.by_resource.values()):
            raise RuntimeError('去向汇总与已分派不一致')
        if len({row.key for row in self.rows}) != len(self.rows):
            raise RuntimeError('作业单据重复')
        for row in self.rows:
            if row.assigned < 0 or row.assigned > row.candidate.draft.units:
                raise RuntimeError('单条派工超过申报')
            if row.assigned != 0 and (row.state != Disposition.BOOKED or row.start is None or row.end is None):
                raise RuntimeError('已占资源缺服务窗口')
