from ..drying_features.contracts import Prepared
from .contracts import Disposition, Draft


def interpret(resolved: Prepared, value: float, uncertainty: float) -> Draft:
    probe = resolved.record

    def block(reason: str) -> Draft:
        return Draft(resolved,Disposition.MANUAL,0,0,1,0,0,reason,'')

    def normal(reason: str) -> Draft:
        return Draft(resolved,Disposition.NORMAL,0,0,1,0,0,reason,'')

    def proposal(qty: int, priority: float, minutes: int, reason: str, resource: str,
                 *, minimum: int | None = None, unit: int = 1) -> Draft:
        return Draft(resolved,Disposition.BOOKED,qty,qty if minimum is None else minimum,
                     unit,priority,minutes,reason,resource)

    thickness, hours, steam, inlet, level, vent = resolved.raw
    if hours <= 9 and probe.window < 56:
        return block('入窑时间不足且复测可能跨冷却窗口')
    tolerance = 12.4 if thickness >= 26 else 11.6
    upper = value + uncertainty * .65
    if upper <= tolerance and level < 7:
        return normal('上界未越含水限值，按既定取样放行')
    count = 2 if level >= 6 or upper - tolerance > 2.6 else 1
    severity = max(0, upper-tolerance) * 12 + level * 4 + max(0, 40-vent) * .19
    return proposal(count, severity, count * 15, '同层位放一个复测窗口并留对照取样点', '烘房层位')
