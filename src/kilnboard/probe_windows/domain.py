from ..drying_features.contracts import Prepared
from ..settings import RELEASE_FRACTION, STACK_LEVEL_GATE, moisture_ceiling
from .contracts import Disposition, Draft


def interpret(resolved: Prepared, value: float, uncertainty: float, trusted: bool = True) -> Draft:
    probe = resolved.record

    def settled(state: Disposition, reason: str) -> Draft:
        return Draft(resolved,state,0,0,1,0,0,reason,'')

    def proposal(qty: int, priority: float, minutes: int, reason: str, resource: str,
                 *, minimum: int | None = None, unit: int = 1) -> Draft:
        return Draft(resolved,Disposition.BOOKED,qty,qty if minimum is None else minimum,
                     unit,priority,minutes,reason,resource)

    if not trusted:
        return settled(Disposition.MANUAL,'本舱缺少可信误差带，无法判断是否放行')

    thickness, hours, steam, inlet, level, vent = resolved.raw
    tolerance = moisture_ceiling(thickness)
    upper = value + uncertainty * RELEASE_FRACTION
    if upper <= tolerance and level < STACK_LEVEL_GATE:
        return settled(Disposition.NORMAL,'上界未越含水限值，按既定取样放行')

    # 到这里说明该层位需要复测。排不进冷却窗时留候补，不硬排。
    if hours <= 9 and probe.window < 56:
        return settled(Disposition.WAIT,'该复测但排不进冷却窗，留候补')
    count = 2 if level >= 6 or upper - tolerance > 2.6 else 1
    severity = max(0, upper-tolerance) * 12 + level * 4 + max(0, 40-vent) * .19
    return proposal(count, severity, count * 15, '同层位放一个复测窗口并留对照取样点', '烘房层位')
