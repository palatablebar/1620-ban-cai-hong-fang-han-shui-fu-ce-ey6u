from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from .settings import FIELDS, MODE, RESOURCE, SIGNAL_NAMES, TITLE, TARGET, WORKFLOW
from .stack_cards.service import MAX_BYTES, inspect_feed, isolation_counts
from .cycle_anchors.contracts import Windows
from .cycle_anchors.service import split, temporal_report
from .cycle_anchors.visibility import exposure
from .drying_features.service import fit, prepare_all, profile_evidence
from .drying_features.audit import compare_support
from .moisture_tree.service import describe, estimate, explain, fit_model
from .stack_backcheck.service import backcheck
from .fiber_shift.service import drift
from .fiber_shift.coverage import confidence, missing_alignment
from .probe_windows.contracts import Candidate, Scenario
from .probe_windows.service import allocate, draft
from .stack_disposition.service import decision_line, freeze
from .stack_disposition.briefing import summarize, tally


@dataclass(frozen=True, slots=True)
class PreparedBatch:
    report: object
    vintage: object
    profile: object
    fitted: object
    replay: object
    shift: object
    candidates: tuple[Candidate,...]


@lru_cache(maxsize=3)
def prepare_batch(content: bytes, windows: Windows) -> PreparedBatch:
    feed = inspect_feed(content)
    vintage = split(feed.tickets,windows)
    profile = fit(vintage.train.evaluated)
    train = prepare_all(profile,vintage.train.evaluated)
    calibration = prepare_all(profile,vintage.calibration.evaluated)
    holdout = prepare_all(profile,vintage.holdout.evaluated)
    incoming = prepare_all(profile,vintage.live)
    fitted = fit_model(train,profile)
    replay = backcheck(fitted,calibration,holdout)
    shift = drift(train,incoming,replay)
    items = []
    adjustment = replay.adjustment
    for item in incoming:
        band = replay.band_for(item.record.region) if adjustment.native_scale else None
        raw = estimate(fitted,item) if item.can_score() else None
        value = adjustment.apply(raw) if raw is not None else None
        sensitivity = explain(fitted,item,raw).contributions if raw is not None else ()
        interval = adjustment.interval(value,band.radius) if value is not None and band is not None and band.trusted else None
        plan = draft(item,value,band.radius if band is not None else 0.0,
                     band.trusted if band is not None else True)
        items.append(Candidate(plan,value,interval,sensitivity,band))
    return PreparedBatch(feed,vintage,profile,fitted,replay,shift,tuple(items))


def load_path(path: Path) -> bytes:
    with path.open('rb') as document:
        return document.read(MAX_BYTES+1)


def scenario_view(scenario: Scenario) -> dict:
    return asdict(scenario)


def baseline_rows(batch: PreparedBatch) -> list[dict]:
    adjustment = batch.replay.adjustment
    return [{'id':row.key,'region':row.region,'day':row.day,
             'observed':row.observed,'estimate':round(adjustment.apply(row.estimate),5),
             'matured':row.confirmed} for row in batch.replay.points]


def preview(content: bytes, scenario: Scenario, windows: Windows = Windows()):
    batch = prepare_batch(content,windows)
    if scenario.region and scenario.region not in batch.shift.by_region:
        raise ValueError('所选片区在当班批次中没有单据')
    schedule = allocate(batch.candidates,scenario)
    report = batch.report
    isolated = [asdict(row) for row in report.rejected]
    decisions = [decision_line(row) for row in schedule.rows]
    for line in decisions:
        line['business_evidence'] = summarize(line)
    counts = {status:sum(row['status']==status for row in decisions)
              for status in ('booked','wait','manual','normal','locked')}
    model = describe(batch.fitted)
    signal_support = compare_support((candidate.draft.signal for candidate in batch.candidates),batch.profile)
    shift = batch.shift.view()
    if missing_alignment(signal_support,shift):
        raise RuntimeError('单据缺测与漂移统计无法对账')
    payload = {'context':{'title':TITLE,'target':TARGET,'estimate_type':MODE,'resource':RESOURCE,'workflow':WORKFLOW,
                          'fields':[asdict(field) for field in FIELDS],'features':list(SIGNAL_NAMES)},
               'windows':windows.bounds(),'scenario':scenario_view(scenario),
               'ledger':{'booked_units':schedule.used,'free_units':schedule.left,'reserved_units':schedule.protected,
                         'by_region':schedule.by_region,'by_resource':schedule.by_resource,'status_counts':counts},
               'decisions':decisions, 'cohorts':temporal_report(batch.vintage), 'model':model,
               'replay':batch.replay.report(),'holdout_points':baseline_rows(batch), 'drift':shift,
               'intake':{**report.counts(),'isolation_reasons':isolation_counts(report),'rejected':isolated[:100]},
               'features':profile_evidence(batch.profile), 'signal_support':signal_support,
               'coverage':confidence(decisions,batch.replay.points), 'visibility':exposure(report.tickets,batch.vintage,windows),
               'business':tally(decisions)}
    return freeze(report.dataset_hash,batch.fitted.signature,batch.shift.readiness,payload)
