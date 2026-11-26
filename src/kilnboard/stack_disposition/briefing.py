from collections import defaultdict
from math import isfinite, sqrt

from ..settings import EXPOSURE_UNIT, FIELDS, moisture_ceiling


def reading(key: str, label: str, value: float, unit: str, trigger: float, direction: str) -> dict:
    number = float(value)
    boundary = float(trigger)
    if not isfinite(number) or not isfinite(boundary):
        raise ValueError(f'{label} 指标不是有限量')
    if direction not in ('high','low'):
        raise ValueError('证据边界方向不明')
    crossed = number > boundary if direction=='high' else number < boundary
    return {'field':key,'label':label,'value':round(number,3),'unit':unit,'trigger':round(boundary,3),
            'direction':direction,'exceeded':crossed}


def summarize(record: dict) -> dict:
    fields = record['raw']
    if any(fields[item.key] is None for item in FIELDS):
        return {'checks':[],'work':None,'exposure':None, 'work_label':None, 'status':'读数不全',
                'band':record.get('release_band')}
    values = tuple(fields[item.key] for item in FIELDS)
    window = record['window']
    prediction = record.get('estimate')
    thickness,hours,steam,inlet,level,vent = values
    tolerance = moisture_ceiling(thickness)
    high = record['interval'][1] if record['interval'] else float(prediction or 0)
    findings=[
        reading('layer_number','堆垛层',level,'层',6,'high'),
        reading('moisture_ceiling','含水率高估边界',high,'%',tolerance,'high'),
        reading('cooling_margin','复测与冷却窗净余量',window-15*record['requested'],'分钟',10,'low'),
        reading('drying_exposure','厚度折算烘干',hours/thickness,'小时/mm',.55,'low')]
    work=record['units']*30
    outcome='已留复测组分钟'
    exposure=max(0,high-tolerance) if record['status'] in ('manual','wait') else 0.
    return {'checks':findings,'work':round(work,3),'work_label':outcome,'exposure':round(exposure,3),'status':'可核算',
            'band':record.get('release_band')}


def tally(rows: list[dict]) -> dict:
    by_region = defaultdict(lambda: {'measured':0,'missing':0,'work':0.,'exposure':0.,'outside':0})
    for row in rows:
        area = by_region[row['region']]
        note = row['business_evidence']
        if note['work'] is None:
            area['missing'] += 1
        else:
            area['measured'] += 1
            area['work'] += note['work']
            area['exposure'] += note['exposure']
            area['outside'] += sum(check['exceeded'] for check in note['checks'])
    aggregates = {'work':0.,'exposure':0.,'source_missing':0,'outside_count':0}
    for area in by_region.values():
        aggregates['work'] += area['work']
        aggregates['exposure'] += area['exposure']
        aggregates['source_missing'] += area['missing']
        aggregates['outside_count'] += area['outside']
    aggregates['work'] = round(aggregates['work'],3)
    aggregates['exposure'] = round(aggregates['exposure'],3)
    return {**aggregates,'exposure_unit':EXPOSURE_UNIT,'regions':dict(sorted(by_region.items()))}
