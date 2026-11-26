from dataclasses import replace
import pytest

from kilnboard.cycle_anchors.contracts import Windows
from kilnboard.cycle_anchors.service import bracket,snapshot,split,temporal_report
from kilnboard.stack_cards.contracts import Hold


# TRAP-23
def test_at_cut_is_future(source):
    original = source.tickets[0]
    row = replace(original,received=66)
    report = snapshot((row,),66)
    assert not report.accepted
    assert report.not_yet_seen==1
    assert snapshot((row,),67).accepted==(row,)


# TRAP-42
def test_late_revision_cannot_revise_past(source):
    original = source.tickets[0]
    higher = replace(original,revision=2,received=100,target=original.target+6)
    report = split((*source.tickets,higher),Windows())
    trains = {row.key:row for row in report.train.evaluated}
    assert trains[original.key] == original
    selected = {row.key:row for row in report.snapshot.accepted}
    assert selected[original.key] == higher


# TRAP-14
def test_exact_resends_and_conflicts(source):
    original = source.tickets[0]
    repeated = replace(original,received=original.received+1)
    output = snapshot((original,repeated),126)
    assert output.duplicate_arrivals==1
    assert output.accepted==(original,)
    revised = replace(original,arrival=original.arrival+2)
    output = snapshot((revised, original, repeated),126)
    assert output.conflicts==(original.key,)
    assert output.duplicate_arrivals==1
    assert not output.accepted


def test_no_shared_training_and_validation(source):
    result = split(source.tickets,Windows())
    keys = [set(row.key for row in group) for group in
            (result.train.evaluated,result.calibration.evaluated,result.holdout.evaluated,result.live)]
    assert all(not left&right for i,left in enumerate(keys) for right in keys[i+1:])
    assert all(result.train.lower <= item.day < result.train.upper for item in result.train.evaluated)
    assert all(item.phase=='live' for item in result.live)


def test_pending_label_protected(source):
    original = source.tickets[0]
    late = replace(original,outcome_day=67)
    vintage = snapshot((late,),66)
    report = bracket(vintage,'训练',1,66,66)
    assert report.immature==(original.key,)
    assert not report.evaluated


def test_right_censoring_keeps_lower_bound(source):
    original = replace(source.tickets[0],complete=False)
    view = snapshot((original,),66)
    report = bracket(view,'训练',1,66,66,keep_censoring=True)
    assert report.censored==(original.key,)
    assert report.evaluated==(original,)
    ordinary = bracket(view,'训练',1,66,66,keep_censoring=False)
    assert not ordinary.evaluated


def test_window_order_and_receipt_counts(prepared,source):
    with pytest.raises(ValueError):
        Windows(train_end=85,calibration_end=80)
    ledger = temporal_report(prepared.vintage)
    assert ledger['conflicts'] and ledger['future_arrivals']>=2
    assert sum(ledger['current_by_region'].values())==len(prepared.vintage.live)


def test_reserved_examples_stay_out_of_fit(source):
    row = replace(source.tickets[0],hold=Hold.RESERVED)
    result = bracket(snapshot((row,),66),'训练',1,66,66)
    assert not result.evaluated
    assert result.locked==(row.key,)
