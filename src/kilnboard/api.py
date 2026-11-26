from contextlib import asynccontextmanager
from pathlib import Path
from os import getenv

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .settings import ALGORITHM, DEFAULT_BUDGET, SAMPLE_NAME, TITLE
from .stack_cards.service import MAX_BYTES, inspect_feed, isolation_counts
from .probe_windows.contracts import Disposition, Scenario
from .stack_disposition.contracts import PublicationBlocked, StalePublication
from .stack_disposition.service import from_archive, history, latest, manifest, publish
from .process import load_path, preview
from .comparison import inspect_tradeoff


class WhatIf(BaseModel):
    model_config = ConfigDict(extra='forbid')
    budget: int = Field(DEFAULT_BUDGET,ge=0,le=10000,strict=True)
    reserve: int = Field(0,ge=0,le=10000,strict=True)
    region: str | None = Field(None,max_length=28)
    start: int = Field(360,ge=0,le=1439,strict=True)
    stop: int = Field(1005,gt=0,le=1440,strict=True)

    def scenario(self) -> Scenario:
        return Scenario(self.budget,self.reserve,self.region,self.start,self.stop)


class Comparison(BaseModel):
    model_config = ConfigDict(extra='forbid')
    baseline: WhatIf
    proposal: WhatIf


class Release(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0,strict=True)
    id: str = Field(pattern=r'^[0-9a-f]{64}$')
    scenario: WhatIf


def application(feed: Path | None = None, directory: Path | None = None) -> FastAPI:
    source_file = feed or Path(getenv('SOURCE_FILE',f'sample_data/{SAMPLE_NAME}'))
    store = directory or Path(getenv('DISPATCH_STORE','state'))

    @asynccontextmanager
    async def onboard(app: FastAPI):
        content = load_path(source_file)
        app.state.content = content
        app.state.default = await run_in_threadpool(preview,content,Scenario(DEFAULT_BUDGET))
        yield

    app = FastAPI(title=TITLE,version='1.0.0',description='当班单据、近窗回放和可追溯派工。',lifespan=onboard)
    frontend = Path(__file__).parent/'web'
    app.mount('/static',StaticFiles(directory=frontend/'assets'),name='static')

    @app.get('/',include_in_schema=False)
    def workbench():
        return FileResponse(frontend/'index.html')

    @app.get('/health',tags=['服务状态'])
    def health():
        record = app.state.default
        return {'service':TITLE,'status':'ok','readiness':record.state,'model':ALGORITHM,
                'dataset_sha256':record.source,'historical_train':record.payload['model']['train_rows'],
                'holdout_samples':record.payload['replay']['holdout']['count']}

    @app.get('/api/decisions',tags=['处置单'])
    def cases(limit: int = Query(20,ge=1,le=200),offset: int = Query(0,ge=0),
              region: str | None = Query(None,max_length=28), status: Disposition | None = None):
        plan = app.state.default
        rows = [case for case in plan.payload['decisions']
                if (region is None or case['region']==region) and (status is None or case['status']==status)]
        return {'id':plan.identifier,'total':len(rows),'offset':offset,'limit':limit,'items':rows[offset:offset+limit]}

    @app.get('/api/decisions/{key}',tags=['处置单'])
    def case_detail(key: str):
        for case in app.state.default.payload['decisions']:
            if case['key']==key:
                return case
        raise HTTPException(404,'未找到当班单据')

    @app.get('/api/snapshot',tags=['处置单'])
    def snapshot():
        state = latest(store)
        baseline = app.state.default
        return {'id':baseline.identifier,'revision':state['revision'] if state else 0,'result':baseline.payload}

    @app.post('/api/scenario',tags=['处置单'])
    def what_if(body: WhatIf):
        try:
            plan = preview(app.state.content,body.scenario())
        except ValueError as error:
            raise HTTPException(422,str(error)) from error
        head = latest(store)
        return {'id':plan.identifier,'revision':head['revision'] if head else 0,'result':plan.payload}

    @app.post('/api/compare',tags=['处置单'])
    def compare(body: Comparison):
        try:
            return inspect_tradeoff(app.state.content,body.baseline.scenario(),body.proposal.scenario())
        except ValueError as error:
            raise HTTPException(422,str(error)) from error

    @app.get('/api/briefing',tags=['处置单'])
    def briefing():
        current = app.state.default.payload
        return {'work':current['business'],'coverage':current['coverage'],'visibility':current['visibility']}

    @app.get('/api/replay',tags=['模型证据'])
    def replay():
        plan = app.state.default.payload
        return {'windows':plan['cohorts'],'summary':plan['replay'],'observed':plan['holdout_points']}

    @app.get('/api/model',tags=['模型证据'])
    def model():
        return {'fit':app.state.default.payload['model'],'signals':app.state.default.payload['features']}

    @app.get('/api/drift',tags=['模型证据'])
    def drift_report():
        return app.state.default.payload['drift']

    @app.post('/api/feed/validate',tags=['数据接收'])
    async def feed_check(request: Request):
        pieces = bytearray()
        async for piece in request.stream():
            if len(pieces)+len(piece)>MAX_BYTES:
                raise HTTPException(413,'CSV 超过 3.2 MB')
            pieces.extend(piece)
        try:
            report = await run_in_threadpool(inspect_feed,bytes(pieces))
        except ValueError as error:
            raise HTTPException(422,str(error)) from error
        return {**report.counts(),'reasons':isolation_counts(report),'sha256':report.dataset_hash}

    @app.post('/api/publish',tags=['归档'],status_code=201)
    def release(body: Release):
        try:
            plan = preview(app.state.content,body.scenario.scenario())
            if body.id!=plan.identifier:
                raise HTTPException(409,'预览摘要与待发布参数不一致')
            return publish(store,plan,body.expected_revision)
        except StalePublication as error:
            raise HTTPException(409,{'reason':str(error),'expected':error.expected,'current':error.actual}) from error
        except PublicationBlocked as error:
            raise HTTPException(409,str(error)) from error
        except ValueError as error:
            raise HTTPException(422,str(error)) from error

    @app.get('/api/ledger',tags=['归档'])
    def journal(limit: int = Query(30,ge=1,le=200)):
        return {'items':history(store,limit)}

    @app.get('/api/ledger/{identifier}',tags=['归档'])
    def archive(identifier: str):
        value = from_archive(store,identifier)
        if value is None:
            raise HTTPException(404,'找不到发布版本')
        return value

    @app.get('/api/manifest.csv',tags=['归档'])
    def current_manifest(identifier: str | None = None):
        if identifier is None:
            payload = app.state.default.payload
        else:
            fixed = from_archive(store,identifier)
            if fixed is None:
                raise HTTPException(404,'找不到发布版本')
            payload = fixed['result']
        return csv_response(payload)

    @app.post('/api/manifest.csv',tags=['归档'])
    def what_if_manifest(body: WhatIf):
        try:
            plan = preview(app.state.content,body.scenario())
        except ValueError as error:
            raise HTTPException(422,str(error)) from error
        return csv_response(plan.payload)

    return app


def csv_response(payload: dict) -> Response:
    return Response('\ufeff'+manifest(payload),media_type='text/csv',
                    headers={'Content-Disposition':'attachment; filename="dispatch-manifest.csv"'})


app = application()
