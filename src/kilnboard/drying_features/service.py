from collections.abc import Iterable
from hashlib import sha256
from json import dumps
from statistics import median

from ..settings import FIELDS, SIGNAL_NAMES
from ..stack_cards.contracts import Ticket
from .contracts import FittedSignals, Prepared, SignalFlag
from .indicators import derive
from .scaling import clipped, fit_axis, recover, support_distance


def fit(tickets: tuple[Ticket, ...]) -> FittedSignals:
    if len(tickets) < 12:
        raise ValueError('有效训练记录少于 12 条，无法估计基线')
    if any(ticket.phase != 'history' for ticket in tickets):
        raise ValueError('训练特征只能由历史输入生成')
    medians = []
    for index, field in enumerate(FIELDS):
        readings = [ticket.raw[index] for ticket in tickets if ticket.raw[index] is not None]
        if not readings:
            raise ValueError(f'训练窗持续缺测 {field.title}')
        medians.append(float(median(readings)))
    replacements = tuple(medians)
    vectors = [derive(recover(ticket.raw, replacements)) for ticket in tickets]
    axes = tuple(fit_axis(name, values) for name, values in zip(SIGNAL_NAMES, zip(*vectors), strict=True))
    regions = frozenset(ticket.region for ticket in tickets)
    source = {'shape': [(a.name, a.median, a.scale, a.low, a.high) for a in axes], 'input': medians,
              'regions': sorted(regions), 'support': len(tickets)}
    fingerprint = sha256(dumps(source, sort_keys=True).encode()).hexdigest()
    return FittedSignals(replacements, axes, regions, len(tickets), fingerprint)


def prepare(profile: FittedSignals, ticket: Ticket) -> Prepared:
    missing = tuple(field.key for field, value in zip(FIELDS, ticket.raw, strict=True) if value is None)
    raw = recover(ticket.raw, profile.input_medians)
    signals = derive(raw)
    unbounded = tuple(axis.z(value) for axis, value in zip(profile.axes, signals, strict=True))
    distance = max(support_distance(value, z, axis) for value, z, axis in zip(signals, unbounded, profile.axes, strict=True))
    warnings = []
    if missing:
        warnings.append(SignalFlag.PARTIAL)
    if len(missing) > 1 or FIELDS[0].key in missing or any(not field.allowed(value) for field, value in zip(FIELDS, raw, strict=True)):
        warnings.append(SignalFlag.TOO_FEW)
    if ticket.region not in profile.regions:
        warnings.append(SignalFlag.UNSEEN)
    if distance > 7.2:
        warnings.append(SignalFlag.DISTANT)
    return Prepared(ticket, raw, signals, tuple(map(clipped, unbounded)), tuple(warnings), missing, distance)


def prepare_all(profile: FittedSignals, tickets: Iterable[Ticket]) -> tuple[Prepared, ...]:
    return tuple(prepare(profile, ticket) for ticket in tickets)


def profile_evidence(profile: FittedSignals) -> dict:
    return {'signature': profile.signature, 'train_rows': profile.support, 'regions': sorted(profile.regions),
            'axes': [{'signal': x.name, 'median': x.median, 'scale': x.scale,
                      'support': [x.low, x.high], 'constant': x.constant} for x in profile.axes]}
