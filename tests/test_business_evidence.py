from copy import deepcopy
from dataclasses import replace
from math import isclose

import pytest

from kilnboard.cycle_anchors.contracts import Windows
from kilnboard.cycle_anchors.visibility import exposure
from kilnboard.fiber_shift.coverage import confidence,missing_alignment,wilson
from kilnboard.probe_windows.contracts import Scenario
from kilnboard.stack_disposition.briefing import reading,summarize,tally
from kilnboard.drying_features.audit import compare_support
from kilnboard.comparison import inspect_tradeoff
from kilnboard.process import preview
from kilnboard.settings import DEFAULT_BUDGET,FIELDS


def test_full_exposure_explains_disjoint_visibility(source,prepared):
    report=exposure(source.tickets,prepared.vintage,Windows())
    areas=report['by_region'].values()
    assert sum(zone['later'] for zone in areas)==prepared.vintage.snapshot.not_yet_seen
    assert sum(zone['in_window']+zone['historical_pending']+zone['current'] for zone in areas)==len(prepared.vintage.snapshot.accepted)


def test_upper_and_lower_readings_cross_on_different_sides():
    assert reading('too_high','上限',9,'个',8,'high')['exceeded']
    assert reading('too_low','下限',7,'个',8,'low')['exceeded']
    assert not reading('boundary','边界',8,'个',8,'high')['exceeded']
    with pytest.raises(ValueError):
        reading('invalid','坏值',float('nan'),'个',8,'high')


def test_missing_signal_remains_unverified_in_business_export(source_bytes):
    baseline=preview(source_bytes,Scenario(DEFAULT_BUDGET)).payload
    available=next(item for item in baseline['decisions'] if all(reading is not None for reading in item['raw'].values()))
    tampered=deepcopy(available)
    tampered['raw'][FIELDS[0].key]=None
    amended=summarize(tampered)
    assert available['business_evidence']['checks']
    assert amended['work'] is None and amended['exposure'] is None and not amended['checks']


def test_regional_impact_batch_adds_up(source_bytes):
    package=preview(source_bytes,Scenario(DEFAULT_BUDGET)).payload
    evidence=tally(package['decisions'])
    regions=evidence['regions'].values()
    assert evidence['source_missing']==sum(row['missing'] for row in regions)
    assert evidence['outside_count']==sum(row['outside'] for row in regions)
    assert isclose(evidence['work'],sum(x['work'] for x in regions),abs_tol=.001)


def test_wilson_empty_and_single_sided_interval():
    assert wilson(0,0) is None
    low,high=wilson(0,20)
    assert low==0 and 0<high<.2
    with pytest.raises(ValueError):
        wilson(5,4)


def test_coverage_shows_unfamiliar_region_has_no_historical_support(source_bytes,prepared):
    view=preview(source_bytes,Scenario(DEFAULT_BUDGET)).payload
    checked=confidence(view['decisions'],prepared.replay.points)
    unknown=next(row for row in checked['regional_coverage'] if row['region']=='试点点位-未建档')
    assert unknown['cases']['manual']>0
    assert unknown['raw_holdout_deviation'] is None and unknown['label_support'] is None


def test_signal_pattern_should_tie_to_reported_missing(prepared):
    known=tuple(candidate.draft.signal for candidate in prepared.candidates)
    signals=compare_support(known,prepared.profile)
    assert signals['total']==len(known)
    assert not missing_alignment(signals,prepared.shift.view())
    for band in signals['supports']:
        assert band['lower']+band['upper']<=band['eligible']
        assert band['current_deciles']==sorted(band['current_deciles'])


def test_resource_tradeoff_preserves_model_and_totals(source_bytes):
    initial=Scenario(DEFAULT_BUDGET)
    revised=Scenario(0)
    plan=inspect_tradeoff(source_bytes,initial,revised)
    assert plan['base']!=plan['candidate']
    assert plan['booked_delta']<0
    assert sum(row['booking_delta'] for row in plan['changes'])==plan['booked_delta']
    assert sum(plan['transitions'].values())==len(plan['changes'])


def test_same_scenario_comparison_is_idempotent(source_bytes):
    baseline=Scenario(DEFAULT_BUDGET)
    result=inspect_tradeoff(source_bytes,baseline,baseline)
    assert result['base']==result['candidate']
    assert result['booked_delta']==result['budget_delta']==result['exposure_delta']==0
    assert result['changes']==[]
