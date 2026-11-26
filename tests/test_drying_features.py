from dataclasses import replace
from math import isfinite
import pytest

from kilnboard.drying_features.contracts import SignalFlag
from kilnboard.drying_features.indicators import derive
from kilnboard.drying_features.scaling import fit_axis
from kilnboard.drying_features.service import fit,prepare,prepare_all,profile_evidence
from kilnboard.settings import FIELDS,SIGNAL_NAMES


# TRAP-32
def test_constant_axis():
    uniform = fit_axis('稳定读数',[1e10]*26)
    assert uniform.constant and uniform.scale==1
    assert uniform.z(1e10)==0


def test_large_offset_variance():
    large = fit_axis('背景噪声',[1e10+step*.003 for step in range(20)])
    assert 0.001 < large.scale < .09
    assert not large.constant


def test_known_dimension_and_finiteness(prepared):
    outputs = derive(prepared.profile.input_medians)
    assert len(outputs)==len(SIGNAL_NAMES)
    assert all(map(isfinite,outputs))
    report = profile_evidence(prepared.profile)
    assert report['signature']==prepared.profile.signature
    assert [item['signal'] for item in report['axes']]==list(SIGNAL_NAMES)


def test_missing_critical_input_not_scored(prepared):
    original = prepared.vintage.live[0]
    revision = replace(original,raw=(None,*original.raw[1:]))
    view = prepare(prepared.profile,revision)
    assert view.raw[0]==prepared.profile.input_medians[0]
    assert view.missing[0]==FIELDS[0].key
    assert not view.can_score()


def test_unknown_region_evidence(prepared):
    original = prepared.vintage.live[0]
    row = replace(original,region='无历史点位')
    view = prepare(prepared.profile,row)
    assert SignalFlag.UNSEEN in view.flags
    assert not view.can_score()
    assert 'unseen_region' in view.evidence()['flags']


def test_train_only_uses_historical_rows(prepared):
    with pytest.raises(ValueError,match='历史输入'):
        fit((*prepared.vintage.train.evaluated,prepared.vintage.live[0]))


def test_prepare_is_order_invariant(prepared):
    result = prepare_all(prepared.profile,prepared.vintage.live[:5])
    reverse = prepare_all(prepared.profile,reversed(prepared.vintage.live[:5]))
    assert result==tuple(reversed(reverse))


def test_missing_column_fails_baseline_fit(prepared):
    bad = tuple(replace(row,raw=(None,*row.raw[1:])) for row in prepared.vintage.train.evaluated)
    with pytest.raises(ValueError,match=FIELDS[0].title):
        fit(bad)
