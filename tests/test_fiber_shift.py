from dataclasses import replace
from math import isclose
import pytest

from kilnboard.fiber_shift.contracts import Readiness
from kilnboard.fiber_shift.distribution import frequency,stability_index
from kilnboard.fiber_shift.service import drift,judge
from kilnboard.drying_features.service import prepare_all


def test_psi_supports_empty_bins_symmetrically():
    reference=(20,0,10,0,0)
    replacement=(1,0,9,1,19)
    reading = stability_index(reference,replacement)
    assert reading>1
    assert isclose(reading,stability_index(replacement,reference))
    assert stability_index(reference,reference)==0


def test_signal_bucket_end_belongs_to_next():
    values=frequency([-1,0,1,2],(-1,0,1))
    assert values==(0,1,1,2)
    assert sum(values)==4


# TRAP-44
def test_unseen_blocks_when_majority(prepared):
    vintage = prepared.vintage
    known = vintage.train.evaluated
    new = tuple(replace(item,region='全新服务区') for item in vintage.live)
    result = drift(prepare_all(prepared.profile,known),prepare_all(prepared.profile,new),prepared.replay)
    assert result.readiness==Readiness.BLOCK
    assert result.unknown_regions['全新服务区']==len(new)
    assert result.view()['affected_regions']['全新服务区']['manual']==len(new)


def test_drift_never_uses_unknown_cohort_to_refit(prepared):
    output = prepared.shift.view()
    assert output['unknown_regions'] and output['missing_fields']
    assert sum(row['incoming'] for row in output['affected_regions'].values())==output['live_count']
    for band in output['bands']:
        assert sum(band['live'])==output['live_count']-sum(output['unknown_regions'].values())


def test_backcheck_low_support_blocks_publication():
    assert judge(9,0,2,7,17)[0]==Readiness.BLOCK
    assert judge(9,0,2,10,6)[0]==Readiness.BLOCK
    assert judge(0,0,0,32,32)[0]==Readiness.BLOCK


def test_small_workload_does_not_raise_false_shift():
    phase,reasons=judge(3,0,5,12,18)
    assert phase==Readiness.REVIEW
    assert reasons==('当前窗口样本稀疏，分布指标仅供观测',)


def test_psi_rejects_wrong_input():
    with pytest.raises(ValueError):
        stability_index((5,10,1),(1,7))
    with pytest.raises(ValueError):
        stability_index((5,10,1),(1,-7,2))
