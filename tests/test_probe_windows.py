from dataclasses import replace
import pytest

from kilnboard.stack_cards.contracts import Hold
from kilnboard.probe_windows.calendar import WindowBook
from kilnboard.probe_windows.contracts import Candidate,Disposition,Draft,Scenario
from kilnboard.probe_windows.service import allocate,draft
from kilnboard.settings import DEFAULT_BUDGET,PLACEMENT_MODE


# TRAP-19
def test_locked_cannot_book(prepared):
    first=prepared.candidates[0].draft.signal
    blocked=replace(first,record=replace(first.record,hold=Hold.RESERVED))
    plan=draft(blocked,1_000_000.,500.)
    assert plan.state==Disposition.LOCKED and plan.units==0
    result=allocate((Candidate(plan,None,None,()),),Scenario(10))
    assert result.used==0 and result.rows[0].state==Disposition.LOCKED


def test_quota_zero_releases_nothing(prepared):
    limited = allocate(prepared.candidates,Scenario(0))
    ordinary = allocate(prepared.candidates,Scenario(DEFAULT_BUDGET))
    assert limited.used==0 and limited.left==0
    assert ordinary.used>0
    assert {row.key for row in limited.rows}=={row.key for row in ordinary.rows}


def test_regional_consumption_conserves_reserve(prepared):
    region=next(iter(prepared.profile.regions))
    run=allocate(prepared.candidates,Scenario(DEFAULT_BUDGET,reserve=1,region=region))
    assert run.used+run.left+run.protected==DEFAULT_BUDGET
    assert all(row.candidate.draft.signal.record.region==region for row in run.rows)
    assert sum(run.by_region.values())==run.used
    assert sum(run.by_resource.values())==run.used


def test_half_open_calendar_and_protected_gap(prepared):
    signal=prepared.candidates[0].draft.signal
    result=Draft(replace(signal,record=replace(signal.record,arrival=400,window=60)),
                 Disposition.BOOKED,2,2,1,99,15,'回归','slot')
    ledger=WindowBook()
    scenario=Scenario(50,start=380,stop=500)
    assert ledger.seek(result,scenario,'early_run')==(400,415)
    ledger.commit(result,'early_run',400,415)
    assert ledger.seek(result,scenario,'early_run')==(415,430)
    assert ledger.seek(result,scenario,'segment_gap')==(425,440)


def test_duplicate_tickets_are_not_double_booked(prepared):
    active=prepared.candidates[0]
    with pytest.raises(ValueError,match='重复'):
        allocate((active,active),Scenario(DEFAULT_BUDGET))


def test_packing_determinism(prepared):
    scenario=Scenario(DEFAULT_BUDGET)
    normal=allocate(prepared.candidates,scenario)
    reverse=allocate(tuple(reversed(prepared.candidates)),scenario)
    assert normal==reverse


def test_allocated_hours_never_leave_visible_window(prepared):
    allowed=Scenario(DEFAULT_BUDGET,start=430,stop=870)
    result=allocate(prepared.candidates,allowed)
    used=[]
    for row in result.rows:
        if row.assigned:
            ticket=row.candidate.draft.signal.record
            assert max(allowed.start,ticket.arrival)<=row.start<row.end<=min(allowed.stop,ticket.arrival+ticket.window)
            lane=WindowBook.resource(row.candidate.draft,PLACEMENT_MODE)
            assert all(lane!=other or right<=row.start or row.end<=left for other,left,right in used)
            used.append((lane,row.start,row.end))
