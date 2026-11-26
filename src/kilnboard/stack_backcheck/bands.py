"""按舱位估计放行误差带，并复核放宽是否安全。

越小越紧：误差带越窄，上界越低，越多板子会被直接放行（少排复测）。
所以"比全厂口径放宽"意味着半径更小。只有本舱回放实测足够、且按
更窄的带放行后没有多放湿板，才允许这样放宽；否则退回全厂半径。
"""
from ..settings import BAND_COVERAGE, BAND_MIN_CALIBRATION, BAND_MIN_REPLAY, RELEASE_FRACTION, STACK_LEVEL_GATE, moisture_ceiling
from .calibration import conformal_radius
from .contracts import ReleaseBand, ValidationPoint


def releases(point: ValidationPoint, radius: float) -> bool:
    """按给定误差带，回放中的这一条是否会被直接放行（不排复测）。"""
    upper = point.estimate + radius * RELEASE_FRACTION
    return upper <= moisture_ceiling(point.thickness) and point.level < STACK_LEVEL_GATE


def escapes(points: list[ValidationPoint], radius: float) -> int:
    """放行后实测仍越含水上限的湿板条数。"""
    return sum(1 for point in points if releases(point, radius) and point.observed > moisture_ceiling(point.thickness))


def _band(scope: str, radius: float, calibration: list[ValidationPoint],
          replay: list[ValidationPoint], relaxed: bool, trusted: bool) -> ReleaseBand:
    released = sum(releases(point, radius) for point in replay)
    return ReleaseBand(scope, radius, len(calibration), len(replay),
                       released, len(replay) - released, escapes(replay, radius), relaxed, trusted)


def release_bands(plant_radius: float, calibration: list[ValidationPoint],
                  replay: list[ValidationPoint]) -> dict[str, ReleaseBand]:
    """按舱位估计放行误差带。

    校准只用校准窗里已到档的实测，回放只用决策时点前已到档的回放实测，
    避免未来标签泄漏。只有本舱回放实测足够、且放宽后没有多放湿板，
    才允许比全厂口径更松；本舱校准实测不足则不产生可信误差带。
    """
    matured_calibration = [point for point in calibration if point.confirmed]
    matured_replay = [point for point in replay if point.confirmed]
    plant = _band('plant', plant_radius, matured_calibration, matured_replay, False,
                  len(matured_calibration) >= BAND_MIN_CALIBRATION)
    bands: dict[str, ReleaseBand] = {'plant': plant}
    regions = sorted({point.region for point in matured_calibration} | {point.region for point in matured_replay})
    for region in regions:
        local_calibration = [point for point in matured_calibration if point.region == region]
        local_replay = [point for point in matured_replay if point.region == region]
        if len(local_calibration) < BAND_MIN_CALIBRATION:
            continue  # 本舱校准实测不足，既不产生可信带也不外推
        radius = conformal_radius(local_calibration, BAND_COVERAGE)
        relaxed = radius < plant_radius
        if relaxed and not (len(local_replay) >= BAND_MIN_REPLAY
                            and sum(releases(point, radius) for point in local_replay)
                                > sum(releases(point, plant_radius) for point in local_replay)
                            and escapes(local_replay, radius) <= escapes(local_replay, plant_radius)):
            radius, relaxed = plant_radius, False  # 少排复测未获回放证实，退回全厂口径
        bands[region] = _band(region, radius, local_calibration, local_replay, relaxed, True)
    return bands
