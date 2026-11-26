from collections import defaultdict

from .contracts import Vintage,Windows
from ..stack_cards.contracts import Ticket


def exposure(tickets: tuple[Ticket,...],vintage: Vintage,windows: Windows) -> dict:
    labels = defaultdict(lambda: {'in_window':0,'historical_pending':0,'current':0,'later':0})
    included = {row.key for cohort in (vintage.train,vintage.calibration,vintage.holdout) for row in cohort.evaluated}
    for record in vintage.snapshot.accepted:
        stats = labels[record.region]
        if record.phase=='live':
            stats['current'] += 1
        elif record.key in included:
            stats['in_window'] += 1
        else:
            stats['historical_pending'] += 1
    for record in tickets:
        if record.received>=windows.asof or record.day>=windows.asof:
            labels[record.region]['later'] += 1
    return {'by_region':dict(sorted(labels.items())),'conflicting_keys':list(vintage.snapshot.conflicts),
            'counts_basis':'可见最高版单据和尚未到档的原始版次'}
