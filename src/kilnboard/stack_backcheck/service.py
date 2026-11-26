from collections import defaultdict

from ..settings import MODE
from ..moisture_tree.contracts import FittedModel
from ..moisture_tree.service import estimate, outcome_for
from ..drying_features.contracts import Prepared
from .calibration import fit_adjustment
from .contracts import Validation, ValidationPoint
from .metrics import classification, regression


QUANTITIES = {'regression', 'time', 'rate'}


def valid_points(model: FittedModel, signals: tuple[Prepared, ...]) -> list[ValidationPoint]:
    results = []
    for signal in signals:
        if not signal.can_score():
            continue
        record = signal.record
        observed = outcome_for(signal)
        is_confirmed = observed is not None
        if MODE == 'time' and not is_confirmed:
            observed = record.target
        if observed is not None:
            results.append(ValidationPoint(record.key,record.region,record.day,estimate(model,signal),
                                           observed,is_confirmed))
    return results


def backcheck(model: FittedModel, calibration: tuple[Prepared, ...], holdout: tuple[Prepared, ...]) -> Validation:
    cal_points = valid_points(model, calibration)
    adjusted = fit_adjustment(cal_points, MODE in QUANTITIES, MODE == 'classification')
    hold_points = valid_points(model, holdout)

    def metrics(points: list[ValidationPoint]):
        if MODE in QUANTITIES:
            return regression(points,adjusted,model.baseline)
        return classification(points,adjusted,model.baseline,.5)

    cohorts: dict[str,list[ValidationPoint]] = defaultdict(list)
    for point in hold_points:
        cohorts[point.region].append(point)
    per_region = {region: metrics(points) for region, points in sorted(cohorts.items())}
    counts = (('calibration',len(calibration)-len(cal_points)),('holdout',len(holdout)-len(hold_points)))
    return Validation(adjusted,metrics(hold_points),per_region,counts,tuple(hold_points))
