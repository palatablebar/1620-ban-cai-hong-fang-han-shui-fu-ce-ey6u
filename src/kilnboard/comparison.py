from math import isclose

from .cycle_anchors.contracts import Windows
from .probe_windows.contracts import Scenario
from .process import preview


def inspect_tradeoff(content: bytes,original: Scenario,alternative: Scenario,windows: Windows=Windows()) -> dict:
    old = preview(content,original,windows)
    planned = preview(content,alternative,windows)
    if old.model!=planned.model:
        raise RuntimeError('同批方案对照必须使用同一模型版本')
    before = {row['key']:row for row in old.payload['decisions']}
    after = {row['key']:row for row in planned.payload['decisions']}
    changed = []
    status_pairs: dict[str,int] = {}
    for key in sorted(before.keys()|after.keys()):
        prior,next_ = before.get(key),after.get(key)
        pair = (prior['status'] if prior else 'excluded', next_['status'] if next_ else 'excluded')
        if prior and next_ and prior['estimate']!=next_['estimate']:
            raise RuntimeError('调整班次资源时单条预测变化')
        left,right = prior['units'] if prior else 0, next_['units'] if next_ else 0
        if pair[0]==pair[1] and left==right and prior['start']==next_['start']:
            continue
        status_link = '→'.join(pair)
        status_pairs[status_link] = status_pairs.get(status_link,0)+1
        changed.append({'key':key,'region':(next_ or prior)['region'],'before':pair[0],'after':pair[1],
                        'booking_delta':right-left,'previous_window':prior['start'] if prior else None,
                        'next_window':next_['start'] if next_ else None})
    left_sum = old.payload['ledger']['booked_units']
    right_sum = planned.payload['ledger']['booked_units']
    if sum(row['booking_delta'] for row in changed)!=right_sum-left_sum:
        raise RuntimeError('方案差异占用与总账不平')
    previous_risk = old.payload['business']['exposure']
    next_risk = planned.payload['business']['exposure']
    return {'base':old.identifier,'candidate':planned.identifier,'model':old.model,'booked_delta':right_sum-left_sum,
            'exposure_delta':round(next_risk-previous_risk,3),'metric_unit':planned.payload['business']['exposure_unit'],
            'budget_delta':alternative.budget-original.budget,'changes':changed,'transitions':dict(sorted(status_pairs.items()))}
