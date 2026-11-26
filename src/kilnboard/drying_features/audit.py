from collections import Counter
from collections.abc import Iterable

from ..settings import FIELDS, SIGNAL_NAMES
from .contracts import FittedSignals, Prepared
from .scaling import quantile


def compare_support(items: Iterable[Prepared],profile: FittedSignals) -> dict:
    rows = tuple(items)
    if not rows:
        return {'supports':[],'missing_patterns':{},'total':0}
    sources = Counter('+'.join(row.missing) or '完整测量' for row in rows)
    details = []
    for index,axis in enumerate(profile.axes):
        measurements = [row.unscaled[index] for row in rows if row.can_score()]
        beyond_low = sum(value<axis.low for value in measurements)
        beyond_high = sum(value>axis.high for value in measurements)
        band = [quantile(measurements,get) for get in (.1,.5,.9)] if measurements else []
        details.append({'axis':SIGNAL_NAMES[index],'eligible':len(measurements),'lower':beyond_low,
                        'upper':beyond_high,'reference':[axis.low,axis.high],'current_deciles':band})
    return {'supports':details,'missing_patterns':dict(sorted(sources.items())),
            'raw_units':{item.key:item.unit for item in FIELDS},'total':len(rows)}
