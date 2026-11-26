from collections import Counter

from ..stack_cards.contracts import Hold
from ..drying_features.contracts import Prepared
from ..settings import PLACEMENT_MODE, POOL_LIMIT, SEPARATE_CONTEXTS
from .calendar import WindowBook, packing_order
from .contracts import Booking, Candidate, Disposition, Draft, Scenario, Schedule
from .domain import interpret


def draft(signal: Prepared,value: float | None,radius: float) -> Draft:
    if signal.record.hold == Hold.RESERVED:
        return Draft(signal,Disposition.LOCKED,0,0,1,0,0,'上游已锁定原流程','')
    if signal.record.hold == Hold.CHAIN:
        return Draft(signal,Disposition.MANUAL,0,0,1,0,0,'缺少上游签收或现场手续','')
    if value is None:
        return Draft(signal,Disposition.MANUAL,0,0,1,0,0,'模型无法覆盖当前输入','')
    return interpret(signal,value,radius)


def quantity(candidate: Draft, allowance: int, other: int, scenario: Scenario) -> int:
    cap = min(allowance,candidate.units)
    if PLACEMENT_MODE == 'stock_family':
        family_stock = (scenario.spendable+1)//2
        cap = min(cap,max(0,family_stock-other))
    rounded = cap - cap%candidate.step
    return rounded if rounded>=candidate.minimum else 0


def allocate(items: tuple[Candidate,...], scenario: Scenario) -> Schedule:
    decisions: dict[str,Booking] = {}
    staged: list[Candidate] = []
    for item in items:
        plan = item.draft
        record = plan.signal.record
        if scenario.region and record.region != scenario.region:
            continue
        if record.key in decisions or any(prior.draft.signal.record.key == record.key for prior in staged):
            raise ValueError('同一调度单据重复')
        if plan.state == Disposition.BOOKED:
            staged.append(item)
        else:
            decisions[record.key] = Booking(item,plan.state,0,None,None,plan.why)
    remaining = scenario.spendable
    cursor = WindowBook()
    group_count: Counter = Counter()
    region_use: Counter = Counter()
    resource_use: Counter = Counter()
    schedules: set[tuple] = set()
    served = set()
    ordered = packing_order(staged,PLACEMENT_MODE)
    if PLACEMENT_MODE == 'station_fair':
        first_in_region, followups = [], []
        for option in ordered:
            region = option.draft.signal.record.region
            (followups if region in served else first_in_region).append(option)
            served.add(region)
        ordered = first_in_region+followups
    for item in ordered:
        plan = item.draft
        ticket = plan.signal.record
        physical = (ticket.region,ticket.pool)
        identity = (*physical,plan.resource) if SEPARATE_CONTEXTS else physical
        amount = quantity(plan,remaining,resource_use[plan.resource],scenario)
        slot = cursor.seek(plan,scenario,PLACEMENT_MODE)
        if not amount:
            reason = '剩余资源量不足以完成最小作业单元'
        elif POOL_LIMIT and group_count[physical] >= POOL_LIMIT:
            reason = '同片区或设备组达到本轮上限'
        elif SEPARATE_CONTEXTS and identity in schedules:
            reason = '同一对象已排定，本轮禁止重复占用'
        elif slot is None:
            reason = '未找到完整可服务窗口'
        else:
            start,end = slot
            cursor.commit(plan,PLACEMENT_MODE,start,end)
            reason = plan.why if amount == plan.units else f'{plan.why}，本窗只确认 {amount} 个单位'
            decisions[ticket.key] = Booking(item,Disposition.BOOKED,amount,start,end,reason)
            remaining -= amount
            group_count[physical] += 1
            region_use[ticket.region] += amount
            resource_use[plan.resource] += amount
            schedules.add(identity)
            continue
        decisions[ticket.key] = Booking(item,Disposition.WAIT,0,None,None,reason)
    state_rank = {Disposition.BOOKED:0,Disposition.MANUAL:1,Disposition.WAIT:2,Disposition.LOCKED:3,Disposition.NORMAL:4}
    rows = tuple(sorted(decisions.values(),key=lambda row:(state_rank[row.state],-row.candidate.draft.priority,row.key)))
    result = Schedule(rows,scenario.spendable-remaining,remaining,scenario.reserve,dict(sorted(region_use.items())),
                      dict(sorted(resource_use.items())))
    result.verify(scenario)
    return result
