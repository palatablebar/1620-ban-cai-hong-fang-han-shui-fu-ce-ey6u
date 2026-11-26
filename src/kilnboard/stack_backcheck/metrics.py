from collections import defaultdict
from math import sqrt
from statistics import mean

from .contracts import Adjustment, ValidationPoint


def regression(points: list[ValidationPoint], adjustment: Adjustment, baseline: float) -> dict:
    known = [point for point in points if point.confirmed]
    if not known:
        return {'count': 0, 'status': '等待结果'}
    errors = [item.estimate-item.observed for item in known]
    hits = [abs(error) <= adjustment.radius for error in errors]
    censor_lower = [item for item in points if not item.confirmed]
    return {'count': len(known), 'mae': mean(map(abs,errors)), 'rmse': sqrt(mean(e**2 for e in errors)),
            'coverage': mean(hits), 'signed_bias': mean(errors),
            'baseline_mae': mean(abs(item.observed-baseline) for item in known),
            'right_censored': len(censor_lower),
            'too_short_for_observed_censor': sum(item.estimate+adjustment.radius < item.observed for item in censor_lower)}


def confusion(points: list[tuple[float, float]], threshold: float) -> dict[str,int]:
    counts = dict(tp=0, fp=0, tn=0, fn=0)
    for estimate, observed in points:
        selected = estimate >= threshold
        if observed:
            counts['tp' if selected else 'fn'] += 1
        else:
            counts['fp' if selected else 'tn'] += 1
    return counts


def average_precision(points: list[tuple[float,float]]) -> float | None:
    positives = sum(observed for _, observed in points)
    if not positives:
        return None
    grouped = defaultdict(list)
    for score, observed in points:
        grouped[score].append(observed)
    seen = matches = area = 0.0
    for value in sorted(grouped, reverse=True):
        actual = grouped[value]
        new_positives = sum(actual)
        seen += len(actual)
        matches += new_positives
        area += (matches/seen) * new_positives / positives
    return area


def classification(points: list[ValidationPoint], adjustment: Adjustment, baseline: float, decision_gate: float) -> dict:
    pairs = [(adjustment.apply(row.estimate), row.observed) for row in points if row.confirmed]
    if not pairs:
        return {'count': 0, 'status': '等待结果'}
    comparison = confusion(pairs, decision_gate)
    strata = defaultdict(list)
    for guess, actual in pairs:
        strata[min(4,max(0,int(guess*5)))].append((guess,actual))
    calibration_error = 0.0
    reliability = []
    for index, samples in sorted(strata.items()):
        mean_guess = mean(x for x,_ in samples)
        observed_fraction = mean(y for _,y in samples)
        calibration_error += len(samples)*abs(mean_guess-observed_fraction)/len(pairs)
        reliability.append({'bucket': index, 'n': len(samples), 'average_score': mean_guess, 'observed': observed_fraction})
    positives = int(sum(y for _,y in pairs))
    return {'count': len(pairs), 'positives': positives, 'average_precision': average_precision(pairs),
            'balanced_threshold': decision_gate, 'false_negative': comparison['fn'], 'false_positive': comparison['fp'],
            'confusion': comparison, 'brier': mean((x-y)**2 for x,y in pairs),
            'baseline_brier': mean((baseline-y)**2 for _,y in pairs),
            'calibration_error': calibration_error, 'reliability': reliability,
            'status': '可复核' if 0 < positives < len(pairs) else '单一类别'}
