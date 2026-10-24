"""SQLite conversation and run records shared by all clients."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import time
from uuid import uuid4


class BusyError(ValueError):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] not in {0, 1}:
                raise ValueError("This session database was created by a newer Eliot version.")
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    provider_id TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL,
                    text TEXT NOT NULL DEFAULT '', error TEXT, error_kind TEXT,
                    finish_reason TEXT, usage TEXT NOT NULL DEFAULT '{}',
                    created REAL NOT NULL, updated REAL NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON runs(session_id)
                    WHERE status IN ('queued', 'running');
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    role TEXT NOT NULL, content TEXT NOT NULL, created REAL NOT NULL
                );
                PRAGMA user_version=1;
            """)
        if os.name != "nt":
            self.path.chmod(0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def recover(self):
        with self.connection() as db:
            db.execute("UPDATE runs SET status='interrupted', error='The backend stopped before this response completed.', error_kind='interrupted', updated=? WHERE status IN ('queued','running')", (time.time(),))

    def create_session(self, title="New conversation"):
        now = time.time()
        item = dict(id=uuid4().hex, title=title, created=now, updated=now)
        with self.connection() as db:
            db.execute("INSERT INTO sessions VALUES (:id,:title,:created,:updated)", item)
        return item

    def list_sessions(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM sessions ORDER BY updated DESC LIMIT 200")]

    def session(self, session_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                raise KeyError(session_id)
            item = dict(row)
            item["messages"] = [dict(row) for row in db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY id", (session_id,))]
            item["runs"] = [self._run(row) for row in db.execute("SELECT * FROM runs WHERE session_id=? ORDER BY created", (session_id,))]
            return item

    def delete_session(self, session_id):
        with self.connection() as db:
            if db.execute("SELECT 1 FROM runs WHERE session_id=? AND status IN ('queued','running')", (session_id,)).fetchone():
                raise BusyError("Stop the active response before deleting this conversation.")
            if db.execute("DELETE FROM sessions WHERE id=?", (session_id,)).rowcount == 0:
                raise KeyError(session_id)

    def begin_run(self, session_id, provider, content):
        now, run_id = time.time(), uuid4().hex
        try:
            with self.connection() as db:
                if not db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone():
                    raise KeyError(session_id)
                db.execute("INSERT INTO runs(id,session_id,provider_id,model,status,created,updated) VALUES (?,?,?,?,'queued',?,?)", (run_id, session_id, provider.id, provider.model, now, now))
                db.execute("INSERT INTO messages(session_id,run_id,role,content,created) VALUES (?,?,'user',?,?)", (session_id, run_id, content, now))
                db.execute("UPDATE sessions SET title=CASE WHEN title='New conversation' THEN ? ELSE title END, updated=? WHERE id=?", (content[:70], now, session_id))
        except sqlite3.IntegrityError:
            raise BusyError("This conversation already has an active response.") from None
        return self.run(run_id)

    @staticmethod
    def _run(row):
        item = dict(row)
        item["usage"] = json.loads(item["usage"])
        return item

    def run(self, run_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            return self._run(row)

    def history(self, session_id, run_id):
        with self.connection() as db:
            rows = list(db.execute("""SELECT m.role,m.content FROM messages m JOIN runs r ON r.id=m.run_id
                WHERE m.session_id=? AND (r.status='completed' OR r.id=?) ORDER BY m.id DESC LIMIT 41""", (session_id, run_id)))
            messages, size = [], 0
            for row in rows:
                size += len(row["content"])
                if size > 80_000:
                    break
                messages.append(dict(row))
            messages.reverse()
            while messages and messages[0]["role"] != "user":
                messages.pop(0)
            return messages

    def update(self, run_id, status, text="", error=None, error_kind=None, finish_reason=None, usage=None):
        with self.connection() as db:
            db.execute("UPDATE runs SET status=?,text=?,error=?,error_kind=?,finish_reason=?,usage=?,updated=? WHERE id=?", (status, text, error, error_kind, finish_reason, json.dumps(usage or {}), time.time(), run_id))
            if status == "completed":
                row = db.execute("SELECT session_id FROM runs WHERE id=?", (run_id,)).fetchone()
                db.execute("INSERT INTO messages(session_id,run_id,role,content,created) VALUES (?,?,'assistant',?,?)", (row["session_id"], run_id, text, time.time()))

