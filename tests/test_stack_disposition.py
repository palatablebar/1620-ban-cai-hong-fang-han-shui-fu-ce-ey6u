from concurrent.futures import ThreadPoolExecutor
from csv import DictReader
from io import StringIO
import pytest

from kilnboard.probe_windows.contracts import Scenario
from kilnboard.stack_disposition.contracts import PublicationBlocked,StalePublication
from kilnboard.stack_disposition.service import freeze,from_archive,history,latest,manifest,publish,safe_cell
from kilnboard.process import preview
from kilnboard.settings import DEFAULT_BUDGET


def plan(budget):
    return freeze('a'*64,'b'*64,'ready',{'budget':budget})


def test_archive_idempotent_before_revision_comparison(tmp_path):
    payload=plan(2)
    assert latest(tmp_path) is None
    first=publish(tmp_path,payload,0)
    second=publish(tmp_path,payload,0)
    assert first['id']==second['id']==payload.identifier
    assert first['revision']==second['revision']==1
    assert first['replay'] is False and second['replay'] is True
    assert len(history(tmp_path))==1


# TRAP-26
def test_stale_leaves_head(tmp_path):
    first=plan(4)
    stale=plan(5)
    publish(tmp_path,first,0)
    with pytest.raises(StalePublication) as error:
        publish(tmp_path,stale,0)
    assert error.value.expected==0 and error.value.actual==1
    assert latest(tmp_path)['id']==first.identifier
    assert from_archive(tmp_path,stale.identifier) is None


def test_blocked_snapshot_refuses_write(tmp_path):
    failed=freeze('a','b','blocked',{'reason':'证据缺失'})
    with pytest.raises(PublicationBlocked):
        publish(tmp_path,failed,0)
    assert latest(tmp_path) is None


def test_archive_rejects_detached_payload(tmp_path):
    payload=plan(2)
    publish(tmp_path,payload,0)
    payload.payload['budget']=9
    with pytest.raises(RuntimeError,match='不同内容'):
        publish(tmp_path,payload,1)
    assert latest(tmp_path)['result']['budget']==2


def test_race_different_releases_has_one_winner(tmp_path):
    def dispatch(budget):
        try:
            return publish(tmp_path,plan(budget),0)['revision']
        except StalePublication:
            return None
    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes=list(workers.map(dispatch,(8,9)))
    assert outcomes.count(1)==1 and outcomes.count(None)==1
    assert len(history(tmp_path))==1


def test_manifest_matches_archive_and_preserves_decimal(source_bytes):
    statement=preview(source_bytes,Scenario(DEFAULT_BUDGET))
    rows=list(DictReader(StringIO(manifest(statement.payload))))
    assert {row['key'] for row in rows}=={row['key'] for row in statement.payload['decisions']}
    assert {row['source_sha256'] for row in rows}=={statement.source}
    assert sum(int(row['units']) for row in rows)==statement.payload['ledger']['booked_units']


def test_export_neutralizes_formula_strings():
    for token in ('  =SUM(1,2)','@SEE', '+call','-something'):
        assert safe_cell(token).startswith("'")
    assert safe_cell(-42)==-42
    assert safe_cell('南区')=='南区'
