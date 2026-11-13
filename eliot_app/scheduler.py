"""Durable interval/event jobs and a single supervised host runtime lease."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from .config import ConfigError
from .store import BusyError


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    task: dict
    interval_seconds: int = Field(default=0, ge=0, le=31536000)
    next_run: float = Field(default_factory=time.time, gt=0)
    trigger: str = Field(default="", max_length=100)
    enabled: bool = True


class Scheduler:
    def __init__(self, runtime):
        self.runtime = runtime
        self.store = runtime.store.store
        self.owner = uuid4().hex
        self.task = None
        with self.store.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runtime_lease(id INTEGER PRIMARY KEY CHECK(id=1),owner TEXT NOT NULL,expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY,name TEXT NOT NULL,task TEXT NOT NULL,interval_seconds INTEGER NOT NULL,next_run REAL NOT NULL,trigger TEXT NOT NULL,enabled INTEGER NOT NULL,last_task_id TEXT,last_error TEXT NOT NULL DEFAULT '');
                CREATE INDEX IF NOT EXISTS schedule_due ON schedules(enabled,next_run);
                CREATE TABLE IF NOT EXISTS schedule_triggers(schedule_id TEXT NOT NULL,event_id TEXT NOT NULL,task_id TEXT NOT NULL,PRIMARY KEY(schedule_id,event_id));
            """)

    def acquire(self):
        now = time.time()
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT owner,expires FROM runtime_lease WHERE id=1"
            ).fetchone()
            if row and row["owner"] != self.owner and row["expires"] > now:
                raise BusyError(
                    "Another Eliot execution worker owns this database. Use serve --external-worker for a separate UI."
                )
            db.execute(
                "INSERT INTO runtime_lease VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,expires=excluded.expires",
                (self.owner, now + 15),
            )

    def renew(self):
        with self.store.connection() as db:
            updated = db.execute(
                "UPDATE runtime_lease SET expires=? WHERE id=1 AND owner=?",
                (time.time() + 15, self.owner),
            ).rowcount
        if not updated:
            raise BusyError("Execution worker lease was lost.")

    def create(self, raw):
        item = ScheduleInput.model_validate(raw)
        from .web import NewTask

        task = NewTask.model_validate(item.task).model_dump()
        # Validate configuration and paths without starting an execution.
        self.runtime.service.provider(task.get("provider_id"))
        from pathlib import Path

        if not Path(task["workspace"]).expanduser().is_dir():
            raise ConfigError("Schedule workspace must be an existing directory.")
        identifier = uuid4().hex
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO schedules(id,name,task,interval_seconds,next_run,trigger,enabled) VALUES(?,?,?,?,?,?,?)",
                (
                    identifier,
                    item.name,
                    json.dumps(task),
                    item.interval_seconds,
                    item.next_run,
                    item.trigger,
                    int(item.enabled),
                ),
            )
        return self.get(identifier)

    def list(self):
        with self.store.connection() as db:
            return [
                self.unpack(row)
                for row in db.execute(
                    "SELECT * FROM schedules ORDER BY next_run,id LIMIT 200"
                )
            ]

    @staticmethod
    def unpack(row):
        item = dict(row)
        item["task"] = json.loads(item["task"])
        item["enabled"] = bool(item["enabled"])
        return item

    def get(self, identifier):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT * FROM schedules WHERE id=?", (identifier,)
            ).fetchone()
        if not row:
            raise KeyError(identifier)
        return self.unpack(row)

    def delete(self, identifier):
        self.get(identifier)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM schedule_triggers WHERE schedule_id=?", (identifier,)
            )
            db.execute("DELETE FROM schedules WHERE id=?", (identifier,))
        return {"deleted": True}

    def set_enabled(self, identifier, enabled):
        self.get(identifier)
        with self.store.connection() as db:
            db.execute(
                "UPDATE schedules SET enabled=? WHERE id=?", (int(enabled), identifier)
            )
        return self.get(identifier)

    def trigger(self, identifier, event_id):
        item = self.get(identifier)
        if not item["enabled"]:
            raise ConfigError("Schedule is disabled.")
        if not 1 <= len(event_id) <= 200:
            raise ConfigError(
                "Supply a stable event identifier of up to 200 characters."
            )
        mission_id = hashlib.sha256(
            f"{identifier}:event:{event_id}".encode()
        ).hexdigest()[:32]
        # A repeated event creates/reuses the same task, including across restarts.
        root = self.runtime.create(**item["task"], _mission_id=mission_id)
        with self.store.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO schedule_triggers VALUES(?,?,?)",
                (identifier, event_id, root["id"]),
            )
            db.execute(
                "UPDATE schedules SET last_task_id=?,last_error='' WHERE id=?",
                (root["id"], identifier),
            )
        return root

    def tick(self):
        now = time.time()
        for item in self.list():
            if not item["enabled"] or item["trigger"] or item["next_run"] > now:
                continue
            mission_id = hashlib.sha256(
                f"{item['id']}:{item['next_run']}".encode()
            ).hexdigest()[:32]
            try:
                root = self.runtime.create(**item["task"], _mission_id=mission_id)
                interval = item["interval_seconds"]
                # Coalesce missed runs; do not generate a backlog storm after downtime.
                due = (
                    item["next_run"]
                    + max(1, int((now - item["next_run"]) // interval) + 1) * interval
                    if interval
                    else item["next_run"]
                )
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE schedules SET next_run=?,enabled=?,last_task_id=?,last_error='' WHERE id=?",
                        (due, int(bool(interval)), root["id"], item["id"]),
                    )
            except (ValueError, KeyError):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE schedules SET enabled=0,last_error=? WHERE id=?",
                        (
                            "Schedule prerequisites unavailable; repair configuration and re-enable.",
                            item["id"],
                        ),
                    )

    async def loop(self):
        try:
            while True:
                self.renew()
                self.tick()
                self.runtime.recover()
                for identifier, task in list(self.runtime.tasks.items()):
                    if self.runtime.store.get(identifier)["status"] in {
                        "paused",
                        "cancelled",
                    }:
                        task.cancel()
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.runtime.close()
            raise

    def start(self):
        self.acquire()
        self.task = asyncio.create_task(self.loop())
        return self.task

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM runtime_lease WHERE id=1 AND owner=?", (self.owner,)
            )
