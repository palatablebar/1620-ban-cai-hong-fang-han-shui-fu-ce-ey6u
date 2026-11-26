from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection, connect

from .contracts import Publication, PublicationBlocked, StalePublication, Statement

SCHEMA = '''
CREATE TABLE IF NOT EXISTS dispatch_versions (
    revision INTEGER PRIMARY KEY CHECK(revision>0),
    identifier TEXT UNIQUE NOT NULL,
    data TEXT NOT NULL,
    model TEXT NOT NULL,
    source TEXT NOT NULL
)
'''


class DispatchArchive:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True,exist_ok=True)
        self.database = directory/'dispatch.sqlite3'

    @contextmanager
    def linked(self):
        session: Connection = connect(self.database,timeout=8,isolation_level=None)
        try:
            session.execute('PRAGMA busy_timeout=8000')
            session.execute(SCHEMA)
            yield session
        finally:
            session.close()

    def write(self, plan: Statement, canonical: str, expected: int) -> Publication:
        if plan.state == 'blocked':
            raise PublicationBlocked('本窗未达到发布所需的回放和证据条件')
        if type(expected) is not int or expected<0:
            raise ValueError('发布需提供最近可见版号')
        with self.linked() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                actual, = db.execute('SELECT COALESCE(MAX(revision),0) FROM dispatch_versions').fetchone()
                existing = db.execute('SELECT revision,data FROM dispatch_versions WHERE identifier=?',
                                      (plan.identifier,)).fetchone()
                if existing:
                    revision,data = existing
                    if data != canonical:
                        raise RuntimeError('同一发布摘要命中不同内容')
                    db.commit()
                    return Publication(revision,plan.identifier,True,actual)
                if expected!=actual:
                    raise StalePublication(expected,actual)
                next_revision = actual+1
                db.execute('INSERT INTO dispatch_versions VALUES(?,?,?,?,?)',
                           (next_revision,plan.identifier,canonical,plan.model,plan.source))
                db.commit()
                return Publication(next_revision,plan.identifier,False,next_revision)
            except Exception:
                db.rollback()
                raise

    def latest(self) -> tuple[int,str,str] | None:
        with self.linked() as db:
            return db.execute('SELECT revision,identifier,data FROM dispatch_versions ORDER BY revision DESC LIMIT 1').fetchone()

    def history(self,limit: int) -> list[tuple[int,str,str,str]]:
        with self.linked() as db:
            return db.execute('SELECT revision,identifier,model,source FROM dispatch_versions ORDER BY revision DESC LIMIT ?',
                              (limit,)).fetchall()

    def get(self,identifier: str) -> tuple[int,str,str] | None:
        with self.linked() as db:
            return db.execute('SELECT revision,identifier,data FROM dispatch_versions WHERE identifier=?',(identifier,)).fetchone()
