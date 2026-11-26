from dataclasses import replace
from math import isfinite
import pytest

from kilnboard.moisture_tree.service import describe,estimate,explain,fit_model,learn
from kilnboard.drying_features.service import prepare_all
from kilnboard.settings import ALGORITHM,MODE,SIGNAL_NAMES


# TRAP-53
def test_point_invariance(prepared):
    current = tuple(item for item in prepare_all(prepared.profile,prepared.vintage.live) if item.can_score())
    focus = current[0]
    assert estimate(prepared.fitted,focus)==[estimate(prepared.fitted,row) for row in reversed(current)][-1]
    assert explain(prepared.fitted,focus)==explain(prepared.fitted,focus,estimate(prepared.fitted,focus))


# TRAP-54
def test_fitted_signature_tracks_source(prepared):
    training = prepare_all(prepared.profile,prepared.vintage.train.evaluated)
    row = training[0]
    new_target = (1.-row.record.target) if MODE in ('classification','anomaly') else row.record.target+.123
    altered = replace(row,record=replace(row.record,target=new_target))
    second = fit_model((altered,*training[1:]),prepared.profile)
    assert second.signature!=prepared.fitted.signature
    assert second.feature_signature==prepared.fitted.feature_signature


def test_fit_ignores_input_order(prepared):
    rows = prepare_all(prepared.profile,reversed(prepared.vintage.train.evaluated))
    second = fit_model(rows,prepared.profile)
    assert second.signature==prepared.fitted.signature
    assert describe(second)==describe(prepared.fitted)


def test_estimator_has_varying_evidence(prepared):
    rows = prepare_all(prepared.profile,prepared.vintage.holdout.evaluated)
    forecast = {round(estimate(prepared.fitted,row),3) for row in rows if row.can_score()}
    assert len(forecast)>=4
    assert all(map(isfinite,forecast))


def test_live_cannot_enter_fit(prepared):
    feed = prepare_all(prepared.profile,prepared.vintage.live[:1])
    with pytest.raises(ValueError,match='当班单据'):
        learn(feed)


def test_explanation_replays_reference_perturbation(prepared):
    signals = prepare_all(prepared.profile,prepared.vintage.live)
    focus = next(item for item in signals if item.can_score())
    record = explain(prepared.fitted,focus)
    assert record.value == round(estimate(prepared.fitted,focus),6)
    assert set(dict(record.contributions))==set(SIGNAL_NAMES)
    magnitudes = [abs(change) for _,change in record.contributions]
    assert magnitudes == sorted(magnitudes,reverse=True)


def test_estimator_identity_and_window(prepared):
    result = describe(prepared.fitted)
    assert result['algorithm']==ALGORITHM
    assert result['train_rows']>=10 and result['parameters']
    assert result['last_train_day']<prepared.vintage.train.upper
    assert len(result['signature'])==64
