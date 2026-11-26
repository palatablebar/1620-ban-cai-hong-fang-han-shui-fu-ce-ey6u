from collections import defaultdict
from collections.abc import Iterable

from ..stack_cards.contracts import Ticket
from .contracts import Snapshot


def resolve_revisions(tickets: Iterable[Ticket], before: int) -> Snapshot:
    by_key: dict[str, list[Ticket]] = defaultdict(list)
    unseen = 0
    superseded = 0
    for ticket in tickets:
        if ticket.received >= before or ticket.day >= before:
            unseen += 1
        else:
            by_key[ticket.key].append(ticket)
    duplicates = 0
    conflicts: list[str] = []
    accepted: list[Ticket] = []
    for identifier, versions in sorted(by_key.items()):
        latest = max(item.revision for item in versions)
        latest_editions = [item for item in versions if item.revision == latest]
        superseded += len(versions) - len(latest_editions)
        distinct = {item.fingerprint() for item in latest_editions}
        duplicates += len(latest_editions) - len(distinct)
        if len(distinct) > 1:
            conflicts.append(identifier)
            continue
        exact = min(latest_editions, key=lambda item: item.received)
        accepted.append(exact)
    accepted.sort(key=lambda item: (item.day, item.key))
    return Snapshot(tuple(accepted), tuple(conflicts), duplicates, unseen, superseded)


def count_by_region(tickets: Iterable[Ticket]) -> dict[str, int]:
    summary: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        summary[ticket.region] += 1
    return dict(sorted(summary.items()))


def assert_disjoint(groups: Iterable[Iterable[Ticket]]) -> None:
    previous: set[str] = set()
    for group in groups:
        these = {item.key for item in group}
        if previous & these:
            overlap = sorted(previous & these)[0]
            raise ValueError(f'单据 {overlap} 同时出现在不同历史窗口')
        previous.update(these)
