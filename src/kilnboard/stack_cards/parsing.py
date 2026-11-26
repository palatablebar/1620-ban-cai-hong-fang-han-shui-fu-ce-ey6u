from math import isfinite
import re

from .contracts import Field, FormatError, Hold, Ticket

METADATA = ('key', 'region', 'pool', 'day', 'received', 'revision', 'arrival', 'window',
            'hold', 'phase', 'target', 'outcome_day', 'confirmed', 'complete')
IDENTIFIER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,47}$')
MISSING = {'', 'NA', 'N/A', '-'}


def strict_int(row: dict[str, str], key: str, low: int, high: int) -> int:
    value = row[key].strip()
    if not re.fullmatch(r'[0-9]{1,6}', value):
        raise FormatError('invalid_integer', f'{key} 须填写整数')
    result = int(value)
    if result < low or result > high:
        raise FormatError('integer_range', f'{key} 超出 {low}–{high}')
    return result


def numeric(value: str, field: str) -> float | None:
    text = value.strip().upper()
    if text in MISSING:
        return None
    try:
        number = float(text)
    except ValueError as error:
        raise FormatError('invalid_reading', f'{field} 须填写数值或缺测标记') from error
    if not isfinite(number):
        raise FormatError('nonfinite_reading', f'{field} 出现非有限数值')
    return number


def flag(value: str, name: str) -> bool:
    token = value.strip()
    if token not in ('0', '1'):
        raise FormatError('invalid_flag', f'{name} 须填 0 或 1')
    return token == '1'


def read_row(row: dict[str, str], fields: tuple[Field, ...], mode: str) -> Ticket:
    key, pool = row['key'].strip(), row['pool'].strip()
    if not (IDENTIFIER.fullmatch(key) and IDENTIFIER.fullmatch(pool)):
        raise FormatError('invalid_identity', '单据号与分组标识须为短业务编码')
    region = row['region'].strip()
    if not region or len(region) > 28 or not region.isprintable():
        raise FormatError('invalid_region', '片区名无效')
    day = strict_int(row, 'day', 1, 50000)
    received = strict_int(row, 'received', day, 50000)
    revision = strict_int(row, 'revision', 1, 999)
    arrival = strict_int(row, 'arrival', 0, 1439)
    window = strict_int(row, 'window', 1, 1440)
    phase = row['phase'].strip()
    if phase not in ('history', 'live'):
        raise FormatError('invalid_phase', '记录来源须为 history 或 live')
    try:
        hold = Hold(row['hold'].strip())
    except ValueError as error:
        raise FormatError('invalid_hold', '人工锁定状态未知') from error
    measures = tuple(numeric(row[field.key], field.key) for field in fields)
    for field, value in zip(fields, measures, strict=True):
        if value is not None:
            if not field.allowed(value):
                raise FormatError('reading_range', f'{field.title} 超出采集范围 {field.unit}')
            if field.integer and not value.is_integer():
                raise FormatError('reading_integral', f'{field.title} 必须为完整计量单位')
    target = numeric(row['target'], 'target')
    if target is not None and (target < 0 or target > 1_000_000):
        raise FormatError('target_range', '结果值超出采集范围')
    if target is not None and mode in ('classification', 'anomaly') and target not in (0,1):
        raise FormatError('target_class', '已确认结果须为 0 或 1')
    outcome_day = strict_int(row, 'outcome_day', day, 50000) if row['outcome_day'].strip() else None
    confirmed = flag(row['confirmed'], 'confirmed') if row['confirmed'].strip() else None
    complete = flag(row['complete'], 'complete')
    if phase == 'live' and (target is not None or outcome_day is not None or confirmed is not None or complete):
        raise FormatError('live_outcome', '当班单据不能带历史结果字段')
    if phase == 'history' and (target is None) != (outcome_day is None):
        raise FormatError('missing_outcome_day', '结果值和首次可见日需要成对')
    if complete and outcome_day is None:
        raise FormatError('unobserved_outcome', '已确认结果必须带首次可见日')
    if mode == 'residual' and complete and confirmed is None:
        raise FormatError('missing_confirmation', '表计稽核反馈缺少偏差确认')
    return Ticket(key, region, pool, day, received, revision, arrival, window, hold,
                  measures, target, outcome_day, confirmed, complete, phase)
