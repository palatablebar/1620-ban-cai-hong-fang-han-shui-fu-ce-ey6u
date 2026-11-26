from hashlib import sha256
from json import dumps
from math import isfinite
from statistics import mean, median

from ..settings import ALGORITHM, MODEL_EPOCH, MODE, RAW_EXPLAIN_INDEX, SIGNAL_NAMES
from ..drying_features.contracts import FittedSignals, Prepared
from .contracts import FittedModel, LearningRow, Probe, Score
from .estimator import fit_estimator


def learn(examples: tuple[Prepared, ...]) -> tuple[LearningRow, ...]:
    if any(item.record.phase != 'history' for item in examples):
        raise ValueError('拟合入口收到当班单据')
    selected = [LearningRow(Probe.from_prepared(example), example.record.target,
                            example.record.complete, example.record.confirmed)
                for example in examples
                if example.can_score() and example.record.target is not None]
    return tuple(sorted(selected, key=lambda row: (row.probe.day, row.probe.key)))


def outcome_for(example: Prepared) -> float | None:
    row = example.record
    if not row.complete:
        return None
    if MODE == 'residual':
        return float(row.confirmed) if row.confirmed is not None else None
    return row.target


def baseline_for(examples: tuple[Prepared, ...]) -> float:
    outcomes = [outcome_for(row) for row in examples if row.can_score()]
    available = [value for value in outcomes if value is not None]
    if not available:
        raise ValueError('训练窗没有完整业务结果')
    return float(mean(available) if MODE in ('classification', 'anomaly', 'residual') else median(available))


def fit_model(examples: tuple[Prepared, ...], signals: FittedSignals) -> FittedModel:
    rows = learn(examples)
    if len(rows) < 10:
        raise ValueError('可用建模样本少于 10 条')
    source = {'epoch': MODEL_EPOCH, 'algorithm': ALGORITHM, 'signals': signals.signature,
              'samples': [(row.probe.key, row.probe.day, row.probe.region, row.probe.pool,
                           row.probe.standard, row.probe.raw, row.outcome, row.complete, row.confirmed) for row in rows]}
    signature = sha256(dumps(source, sort_keys=True).encode()).hexdigest()
    result = fit_estimator(rows)
    return FittedModel(result, baseline_for(examples), signature, len(rows), rows[-1].probe.day, signals.signature, signals.input_medians)


def estimate(model: FittedModel, item: Prepared) -> float:
    value = float(model.estimator.predict(Probe.from_prepared(item)))
    if not isfinite(value):
        raise ValueError(f'{item.record.key} 的拟合结果不是有限数值')
    return max(0.0, value)


def explain(model: FittedModel, item: Prepared, value: float | None = None) -> Score:
    probe = Probe.from_prepared(item)
    point = estimate(model, item) if value is None else value
    differences = [(name, round(point - model.estimator.predict(probe.with_reference(index, RAW_EXPLAIN_INDEX[index], model.input_medians)), 5))
                   for index, name in enumerate(SIGNAL_NAMES)]
    differences.sort(key=lambda entry: (-abs(entry[1]), entry[0]))
    return Score(round(point, 6), tuple(differences))


def describe(model: FittedModel) -> dict:
    return {'algorithm': ALGORITHM, 'epoch': MODEL_EPOCH, 'signature': model.signature,
            'train_rows': model.rows, 'last_train_day': model.last_seen,
            'feature_signature': model.feature_signature, 'baseline': model.baseline,
            'parameters': model.estimator.describe()}
