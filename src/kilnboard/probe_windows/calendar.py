from collections import defaultdict
from dataclasses import dataclass, field

from .contracts import Draft, Scenario


@dataclass
class WindowBook:
    busy: dict[tuple[str,str],list[tuple[int,int]]] = field(default_factory=lambda: defaultdict(list))

    @staticmethod
    def bounds(draft: Draft, scenario: Scenario) -> tuple[int,int]:
        row = draft.signal.record
        return max(scenario.start,row.arrival), min(scenario.stop,row.arrival+row.window)

    @staticmethod
    def resource(draft: Draft, scope: str) -> tuple[str,str]:
        row = draft.signal.record
        return row.region, row.pool if scope in ('segment_gap','context_lock','early_run') else draft.resource

    def seek(self,draft: Draft,scenario: Scenario,scope: str) -> tuple[int,int] | None:
        start, end = self.bounds(draft,scenario)
        lane = self.resource(draft,scope)
        buffer = 10 if scope == 'segment_gap' else 0
        for left,right in self.busy[lane]:
            if right+buffer <= start:
                continue
            if start+draft.duration+buffer <= left:
                break
            start = right+buffer
        if start+draft.duration > end:
            return None
        return start,start+draft.duration

    def commit(self,draft: Draft,scope: str,start: int,end: int) -> None:
        key = self.resource(draft,scope)
        timeline = self.busy[key]
        if any(left<end and start<right for left,right in timeline):
            raise ValueError('同一实体时段发生覆盖')
        timeline.append((start,end))
        timeline.sort()


def packing_order(drafts: list, mode: str) -> list:
    def priority(row):
        draft = row.draft
        ticket = draft.signal.record
        deadline = ticket.arrival+ticket.window
        if mode == 'early_run':
            return deadline - min(100,draft.priority)*.8, -draft.priority, ticket.key
        if mode == 'firm_first':
            return -draft.minimum, -draft.priority / max(1,draft.units), ticket.key
        if mode == 'stock_family':
            return -draft.priority / max(1,draft.units), deadline, ticket.key
        if mode == 'segment_gap':
            return -draft.priority, ticket.arrival, ticket.key
        return -draft.priority, deadline, ticket.key
    return sorted(drafts,key=priority)
