from csv import DictReader
from io import StringIO
from pathlib import Path
from json import loads

from fastapi.testclient import TestClient

from kilnboard.api import application
from kilnboard.cli import run
from kilnboard.settings import DEFAULT_BUDGET,HAS_WORKBENCH,SAMPLE_NAME


def feed():
    return Path(__file__).resolve().parent.parent/'sample_data'/SAMPLE_NAME


def test_api_scenario_then_publish_present_and_repeatable(tmp_path):
    with TestClient(application(feed(),tmp_path)) as web:
        assert web.get('/health').status_code==200
        assert web.get('/').status_code==(200 if HAS_WORKBENCH else 404)
        baseline=web.get('/api/snapshot').json()
        lowered=web.post('/api/scenario',json={'budget':0}).json()
        assert baseline['result']['ledger']['booked_units']>lowered['result']['ledger']['booked_units']==0
        post={'scenario':{'budget':0},'id':lowered['id'],'expected_revision':lowered['revision']}
        assert web.post('/api/publish',json=post).json()['revision']==1
        assert web.post('/api/publish',json=post).json()['replay'] is True
        assert web.get(f'/api/ledger/{lowered["id"]}').json()['result']==lowered['result']


def test_api_validates_window_and_forged_preview(tmp_path):
    with TestClient(application(feed(),tmp_path)) as web:
        assert web.post('/api/scenario',json={'budget':3,'reserve':4}).status_code==422
        assert web.post('/api/scenario',json={'budget':True}).status_code==422
        invalid={'scenario':{'budget':3},'expected_revision':0,'id':'c'*64}
        assert web.post('/api/publish',json=invalid).status_code==409
        assert web.get('/api/ledger').json()['items']==[]


def test_api_csv_and_cli_preview_identical(tmp_path,capsys):
    with TestClient(application(feed(),tmp_path)) as web:
        exported=web.get('/api/manifest.csv')
        assert exported.status_code==200
        rows=list(DictReader(StringIO(exported.text.lstrip('\ufeff'))))
        assert run(['--source',str(feed()),'preview'])==0
        cli=loads(capsys.readouterr().out)
        payload=web.get('/api/snapshot').json()
        assert cli['id']==payload['id']
        assert payload['result']['ledger']['booked_units']==sum(int(row['units']) for row in rows)
        assert len(rows)==len(cli['plan']['decisions'])


def test_independent_preview_does_not_change_recent_model(tmp_path):
    with TestClient(application(feed(),tmp_path)) as web:
        initial=web.get('/api/model').json()
        assert web.post('/api/scenario',json={'budget':DEFAULT_BUDGET+5}).status_code==200
        again=web.get('/api/model').json()
        assert initial==again
        assert web.get('/api/drift').json()['unknown_regions']


def test_import_and_json_pagination(source_bytes,tmp_path):
    with TestClient(application(feed(),tmp_path)) as web:
        evidence=web.post('/api/feed/validate',content=source_bytes).json()
        assert evidence['isolated'] >= 1
        cases=web.get('/api/decisions?limit=2').json()
        assert len(cases['items'])==2 and cases['total']>2
        key=cases['items'][1]['key']
        assert web.get(f'/api/decisions/{key}').json()==cases['items'][1]
        assert web.get('/api/decisions/missing').status_code==404
