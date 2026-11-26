from csv import writer
from dataclasses import asdict
from hashlib import sha256
from io import StringIO
from json import dumps, loads
from pathlib import Path

from ..probe_windows.contracts import Booking, Disposition
from ..settings import ACTION, FIELDS, MANUAL_ACTION, NORMAL_ACTION, SIGNAL_NAMES
from .contracts import Statement
from .storage import DispatchArchive


LABELS = {Disposition.BOOKED:ACTION,Disposition.WAIT:'候补待排',Disposition.MANUAL:MANUAL_ACTION,
          Disposition.NORMAL:NORMAL_ACTION,Disposition.LOCKED:'维持上游锁定'}


def decision_line(result: Booking) -> dict:
    candidate = result.candidate
    item = candidate.draft.signal
    source = item.record
    readings = {field.key: value for field,value in zip(FIELDS,source.raw,strict=True)}
    signals = {name:round(value,5) for name,value in zip(SIGNAL_NAMES,item.values,strict=True)}
    return {**source.metadata(),'status':result.state,'action':LABELS[result.state],'reason':result.why,
            'estimate':round(candidate.estimate,5) if candidate.estimate is not None else None,
            'interval': None if candidate.range is None else [round(value,5) for value in candidate.range],
            'requested':candidate.draft.units,'minimum':candidate.draft.minimum,'units':result.assigned,
            'start':result.start,'end':result.end,'resource':candidate.draft.resource,
            'priority':round(candidate.draft.priority,3),'raw':readings,'features':signals,
            'flags':list(item.flags),'missing':list(item.missing),'drivers':dict(candidate.explanations)}


def canonical(value) -> str:
    return dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def freeze(source: str, model: str, state: str, payload: dict) -> Statement:
    value = dict(payload,source_sha256=source,model_hash=model,readiness=state)
    identifier = sha256(canonical(value).encode()).hexdigest()
    return Statement(identifier,model,source,value,state)


def publish(directory: Path, plan: Statement, prior: int) -> dict:
    encoded = canonical(plan.payload)
    if sha256(encoded.encode()).hexdigest() != plan.identifier:
        raise RuntimeError('同一发布摘要命中不同内容')
    return DispatchArchive(directory).write(plan,encoded,prior).wire()


def restore(row: tuple[int,str,str] | None) -> dict | None:
    if row is None:
        return None
    revision,identifier,coded = row
    if sha256(coded.encode()).hexdigest()!=identifier:
        raise RuntimeError('归档内容与发布摘要不符')
    return {'revision':revision,'id':identifier,'result':loads(coded)}


def latest(directory: Path) -> dict | None:
    return restore(DispatchArchive(directory).latest())


def from_archive(directory: Path,identifier: str) -> dict | None:
    return restore(DispatchArchive(directory).get(identifier))


def history(directory: Path,limit: int = 30) -> list[dict]:
    return [dict(revision=revision,id=identifier,model_hash=model,source_sha256=source)
            for revision,identifier,model,source in DispatchArchive(directory).history(limit)]


def safe_cell(value):
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r')):
        return "'"+value
    return value


def manifest(payload: dict) -> str:
    result = StringIO(newline='')
    csv = writer(result)
    base = ('key','region','pool','revision','action','status','reason','estimate','requested','units','start','end','resource')
    csv.writerow((*base,*(field.key for field in FIELDS),'work_quantity','exposure_quantity','source_sha256','model_hash'))
    for row in payload['decisions']:
        cells = [row[key] for key in base]
        cells.extend(row['raw'][field.key] for field in FIELDS)
        note = row['business_evidence']
        cells.extend([note['work'],note['exposure'],payload['source_sha256'],payload['model_hash']])
        csv.writerow(map(safe_cell,cells))
    return result.getvalue()
