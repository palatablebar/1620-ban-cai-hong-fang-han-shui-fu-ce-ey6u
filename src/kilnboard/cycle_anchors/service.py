from ..stack_cards.contracts import Hold, Ticket
from ..settings import IS_SURVIVAL
from .contracts import Cohort, Snapshot, Vintage, Windows
from .revisions import assert_disjoint, count_by_region, resolve_revisions


def snapshot(tickets: tuple[Ticket, ...], before: int) -> Snapshot:
    return resolve_revisions(tickets, before)


def bracket(source: Snapshot, name: str, lower: int, upper: int, known_until: int,
            keep_censoring: bool = IS_SURVIVAL) -> Cohort:
    good: list[Ticket] = []
    pending: list[str] = []
    censored: list[str] = []
    locks: list[str] = []
    for ticket in source.for_phase('history'):
        if not lower <= ticket.day < upper:
            continue
        if ticket.hold != Hold.CLEAR:
            locks.append(ticket.key)
            continue
        if ticket.outcome_day is None or ticket.outcome_day >= known_until:
            pending.append(ticket.key)
        elif not ticket.complete:
            censored.append(ticket.key)
            if keep_censoring:
                good.append(ticket)
        else:
            good.append(ticket)
    return Cohort(name, lower, upper, known_until, tuple(good), tuple(pending), tuple(censored), tuple(locks))


def split(tickets: tuple[Ticket, ...], windows: Windows) -> Vintage:
    early = snapshot(tickets, windows.train_end)
    mid = snapshot(tickets, windows.calibration_end)
    late = snapshot(tickets, windows.asof)
    train = bracket(early, '训练', 1, windows.train_end, windows.train_end)
    calibration = bracket(mid, '校准', windows.train_end, windows.calibration_end, windows.calibration_end)
    holdout = bracket(late, '回放', windows.calibration_end, windows.holdout_end, windows.asof)
    live = tuple(item for item in late.for_phase('live') if item.day >= windows.holdout_end)
    assert_disjoint((train.evaluated, calibration.evaluated, holdout.evaluated, live))
    return Vintage(train, calibration, holdout, live, late)


def temporal_report(vintage: Vintage) -> dict:
    return {'train': vintage.train.counts(), 'calibration': vintage.calibration.counts(),
            'holdout': vintage.holdout.counts(), 'current_by_region': count_by_region(vintage.live),
            'duplicate_arrivals': vintage.snapshot.duplicate_arrivals,
            'future_arrivals': vintage.snapshot.not_yet_seen, 'replaced_revisions': vintage.snapshot.superseded,
            'conflicts': list(vintage.snapshot.conflicts)}
