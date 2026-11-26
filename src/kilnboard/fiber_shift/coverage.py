from collections import defaultdict
from math import sqrt
from statistics import mean

from ..stack_backcheck.contracts import ValidationPoint


def wilson(count: int, total: int) -> tuple[float,float] | None:
    if type(count) is not int or type(total) is not int or not 0 <= count <= total:
        raise ValueError('证据占比无效')
    if not total:
        return None
    z = 1.96
    p = count/total
    divisor = 1+z**2/total
    location = (p+z**2/(2*total))/divisor
    length = z*sqrt(p*(1-p)/total+z**2/(4*total**2))/divisor
    return max(0,location-length),min(1,location+length)


def confidence(queue: list[dict], replay: tuple[ValidationPoint,...]) -> dict:
    matched = defaultdict(list)
    for point in replay:
        matched[point.region].append(point)
    counts = defaultdict(lambda: {'complete':0,'manual':0,'all':0,'partial':0})
    for result in queue:
        stats = counts[result['region']]
        stats['all'] += 1
        stats['complete'] += not result['missing']
        stats['manual'] += result['status']=='manual'
        stats['partial'] += bool(result['missing'])
    results = []
    for region,stats in sorted(counts.items()):
        labels = matched.get(region,[])
        confirmed = [item for item in labels if item.confirmed]
        fraction = wilson(len(confirmed),len(labels))
        all_flags = [abs(item.estimate-item.observed) for item in confirmed]
        results.append({'region':region,'cases':dict(stats),'matured':len(confirmed),'censored':len(labels)-len(confirmed),
                        'label_support':fraction,'raw_holdout_deviation':mean(all_flags) if all_flags else None})
    return {'regional_coverage':results,'confidence_method':'Wilson 95%'}


def missing_alignment(features: dict, distribution: dict) -> tuple[tuple[str,int],...]:
    pattern_counts: dict[str,int] = defaultdict(int)
    for pattern,count in features['missing_patterns'].items():
        if pattern=='完整测量':
            continue
        for key in pattern.split('+'):
            pattern_counts[key]+=count
    reported = distribution['missing_fields']
    differences = []
    for key in sorted(set(pattern_counts) | set(reported)):
        delta = pattern_counts[key] - reported.get(key,0)
        if delta:
            differences.append((key,delta))
    return tuple(differences)
