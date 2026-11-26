from collections import Counter, defaultdict

from ..stack_backcheck.contracts import Validation
from ..drying_features.contracts import Prepared, SignalFlag
from ..settings import SIGNAL_NAMES
from .contracts import MarketShift, Readiness
from .distribution import draw


def judge(live_count: int, rejected: int, psi_spikes: int, history_count: int, calibrated: int) -> tuple[Readiness, tuple[str,...]]:
    reasons = []
    if not live_count:
        return Readiness.BLOCK, ('决策窗内没有当班单据',)
    if history_count < 8 or calibrated < 7:
        return Readiness.BLOCK, ('历史回放或校准未达到最低样本数',)
    if rejected * 2 > live_count:
        return Readiness.BLOCK, ('需人工判别的单据超过当前窗的一半',)
    if live_count >= 9 and psi_spikes >= 2:
        reasons.append('两个以上特征分布越过观察线')
    if rejected:
        reasons.append('存在缺测、新片区或超出拟合支撑的单据')
    if live_count < 5:
        reasons.append('当前窗口样本稀疏，分布指标仅供观测')
    return (Readiness.REVIEW if reasons else Readiness.READY), tuple(reasons)


def drift(train: tuple[Prepared,...], incoming: tuple[Prepared,...], validation: Validation) -> MarketShift:
    eligible_train = tuple(item for item in train if item.can_score())
    known = tuple(obj for obj in incoming if SignalFlag.UNSEEN not in obj.flags)
    unknown = Counter(obj.record.region for obj in incoming if SignalFlag.UNSEEN in obj.flags)
    missing = Counter(field for item in incoming for field in item.missing)
    warning_counts = Counter(str(flag) for sample in incoming for flag in sample.flags)
    bands = tuple(draw(name,index,eligible_train,known) for index,name in enumerate(SIGNAL_NAMES))
    flagged = sum(not item.can_score() for item in incoming)
    levels = sum(axis.psi > .58 for axis in bands)
    phase,reasons = judge(len(incoming),flagged,levels,validation.holdout_metrics['count'],validation.adjustment.samples)
    cohorts: dict[str,list[Prepared]] = defaultdict(list)
    for signal in incoming:
        cohorts[signal.record.region].append(signal)
    regions = {name: {'incoming':len(rows),'manual':sum(not item.can_score() for item in rows),
                      'missing_items':sum(bool(item.missing) for item in rows),
                      'replay_support':validation.regions.get(name,{}).get('count',0)}
               for name,rows in sorted(cohorts.items())}
    return MarketShift(len(incoming),dict(unknown),dict(missing),regions,dict(warning_counts),bands,phase,reasons)
