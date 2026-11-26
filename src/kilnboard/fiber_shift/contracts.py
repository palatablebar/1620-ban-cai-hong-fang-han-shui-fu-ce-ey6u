from dataclasses import dataclass
from enum import StrEnum


class Readiness(StrEnum):
    READY = 'ready'
    REVIEW = 'review'
    BLOCK = 'blocked'


@dataclass(frozen=True, slots=True)
class DriftBand:
    feature: str
    psi: float
    reference: tuple[int,...]
    live: tuple[int,...]
    unseen_outside: int

    def rows(self) -> dict:
        return {'feature': self.feature, 'psi': self.psi, 'reference': list(self.reference),
                'live': list(self.live), 'outside_seen_axis': self.unseen_outside}


@dataclass(frozen=True, slots=True)
class MarketShift:
    rows: int
    unknown_regions: dict[str,int]
    missing_fields: dict[str,int]
    by_region: dict[str,dict]
    flags: dict[str,int]
    bands: tuple[DriftBand,...]
    readiness: Readiness
    reasons: tuple[str,...]

    def view(self) -> dict:
        return {'live_count': self.rows,'unknown_regions': self.unknown_regions,'missing_fields': self.missing_fields,
                'affected_regions': self.by_region,'flags': self.flags, 'bands':[band.rows() for band in self.bands],
                'status': self.readiness, 'reasons': list(self.reasons)}
