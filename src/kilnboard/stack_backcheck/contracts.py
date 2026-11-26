from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ValidationPoint:
    key: str
    region: str
    day: int
    estimate: float
    observed: float
    confirmed: bool
    thickness: float = 0.0
    level: float = 0.0


@dataclass(frozen=True, slots=True)
class Block:
    end: float
    count: int
    positive: float

    @property
    def fraction(self) -> float:
        return self.positive / self.count


@dataclass(frozen=True, slots=True)
class Adjustment:
    name: str
    buckets: tuple[Block, ...]
    radius: float
    samples: int
    native_scale: bool

    def apply(self, value: float) -> float:
        if not self.buckets:
            return value
        previous = None
        for current in self.buckets:
            if value <= current.end:
                if previous is None or current.end <= previous.end:
                    return current.fraction
                weight = (value - previous.end) / (current.end - previous.end)
                return (1-weight)*previous.fraction + weight*current.fraction
            previous = current
        return self.buckets[-1].fraction

    def interval(self, prediction: float, radius: float | None = None) -> tuple[float, float]:
        span = self.radius if radius is None else radius
        threshold = prediction + span
        if not self.native_scale:
            threshold = min(1., threshold)
        return max(0., prediction - span), threshold


@dataclass(frozen=True, slots=True)
class ReleaseBand:
    scope: str          # 'plant' 或具体舱位名
    radius: float
    calibration: int    # 本舱校准窗成熟实测，供带宽估计
    replay: int         # 本舱回放成熟实测，供放宽复核
    released: int       # 回放中按此带可直接放行的条数
    retested: int       # 回放中按此带需要复测的条数
    escapes: int        # 放行后实测仍越含水上限的湿板条数
    relaxed: bool       # 是否比全厂口径更松（放行更多、复测更少）
    trusted: bool       # 是否有可信误差带，可用于放行判断

    def to_dict(self) -> dict:
        return {'scope': self.scope, 'radius': self.radius, 'calibration': self.calibration,
                'replay': self.replay, 'released': self.released, 'retested': self.retested,
                'escapes': self.escapes, 'relaxed': self.relaxed, 'trusted': self.trusted}

    @property
    def name(self) -> str:
        if self.scope.startswith('无本舱误差带'):
            return self.scope
        return f'本舱误差带·{self.scope}' if self.scope != 'plant' else '全厂误差带'


@dataclass(frozen=True, slots=True)
class Validation:
    adjustment: Adjustment
    holdout_metrics: dict
    regions: dict
    excluded: tuple[tuple[str, int], ...]
    points: tuple[ValidationPoint, ...]
    bands: dict[str, ReleaseBand] = field(default_factory=dict)

    def band_for(self, region: str) -> ReleaseBand:
        """返回该舱位可用的放行误差带。

        本舱校准实测足够时用本舱带（放宽须另有回放证实，见 bands）；
        本舱证据不足时不借用全厂带放行，而是标记为无可信带、转人工。
        """
        local = self.bands.get(region)
        if local is not None:
            return local
        plant = self.bands.get('plant')
        radius = plant.radius if plant is not None else self.adjustment.radius
        return ReleaseBand(f'无本舱误差带（{region}）', radius, 0, 0, 0, 0, 0, False, False)

    def report(self) -> dict:
        return {'adjustment': self.adjustment.name, 'calibration_count': self.adjustment.samples,
                'radius': self.adjustment.radius,
                'calibration_blocks': [{'through': b.end, 'risk': b.fraction, 'weight': b.count}
                                       for b in self.adjustment.buckets],
                'holdout': self.holdout_metrics, 'regions': self.regions,
                'bands': {scope: band.to_dict() for scope, band in sorted(self.bands.items())},
                'excluded': dict(self.excluded)}
