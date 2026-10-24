"""Durable task graph, action journal, feedback and uploaded personas."""
from __future__ import annotations

import json
import re
import time
from uuid import uuid4

from .config import ConfigError
from .instructions import DEFAULT_PERSONA
from .store import BusyError


TERMINAL = {"completed", "cancelled", "blocked", "budget_exhausted", "paused"}


class MissionStore:
    def __init__(self, store):
        self.store = store
        with store.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS personas(id TEXT PRIMARY KEY, name TEXT NOT NULL, instructions TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS missions(
                    id TEXT PRIMARY KEY, root_id TEXT NOT NULL, parent_id TEXT,
                    objective TEXT NOT NULL, provider_id TEXT NOT NULL, workspace TEXT NOT NULL,
                    persona TEXT NOT NULL, skills TEXT NOT NULL, policy TEXT NOT NULL,
                    status TEXT NOT NULL, state TEXT NOT NULL, steps INTEGER NOT NULL DEFAULT 0,
                    tokens INTEGER NOT NULL DEFAULT 0, estimated_usage INTEGER NOT NULL DEFAULT 0,
                    result TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '',
                    created REAL NOT NULL, updated REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS mission_tree ON missions(root_id,parent_id);
                CREATE TABLE IF NOT EXISTS mission_events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL REFERENCES missions(id),
                    kind TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mission_actions(
                    mission_id TEXT NOT NULL REFERENCES missions(id), action_id TEXT NOT NULL,
                    request TEXT NOT NULL, status TEXT NOT NULL, result TEXT NOT NULL DEFAULT '{}',
                    created REAL NOT NULL, PRIMARY KEY(mission_id,action_id)
                );
            """)

    def personas(self):
        with self.store.connection() as db:
            return [dict(DEFAULT_PERSONA), *[dict(row) for row in db.execute("SELECT * FROM personas ORDER BY name")]]

    def persona(self, persona_id):
        for persona in self.personas():
            if persona["id"] == persona_id:
                return persona
        raise ConfigError("Persona not found.")

    def save_persona(self, persona_id, name, instructions):
        if persona_id == "eliot" or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", persona_id):
            raise ConfigError("Choose a custom persona ID; the built-in Eliot persona is read-only.")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120 or not isinstance(instructions, str) or not 1 <= len(instructions.strip()) <= 12_000:
            raise ConfigError("A persona needs a name and up to 12,000 characters of text instructions.")
        with self.store.connection() as db:
            db.execute("INSERT INTO personas VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,instructions=excluded.instructions", (persona_id, name.strip(), instructions.strip()))
        return self.persona(persona_id)

    def create(self, objective, provider_id, workspace, persona, skills, policy, parent=None, mission_id=None):
        mission_id = mission_id or uuid4().hex
        root_id = parent["root_id"] if parent else mission_id
        now = time.time()
        with self.store.connection() as db:
            db.execute("INSERT OR IGNORE INTO missions(id,root_id,parent_id,objective,provider_id,workspace,persona,skills,policy,status,state,created,updated) VALUES (?,?,?,?,?,?,?,?,?,'queued','{}',?,?)", (mission_id, root_id, parent["id"] if parent else None, objective, provider_id, workspace, json.dumps(persona), json.dumps(skills), json.dumps(policy), now, now))
        return self.get(mission_id)

    @staticmethod
    def unpack(row):
        item = dict(row)
        for field in ["persona", "skills", "policy", "state"]:
            item[field] = json.loads(item[field])
        return item

    def get(self, mission_id):
        with self.store.connection() as db:
            row = db.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
            if row is None:
                raise KeyError(mission_id)
            return self.unpack(row)

    def list(self, root_id=None):
        with self.store.connection() as db:
            if root_id:
                return [self.unpack(row) for row in db.execute("SELECT * FROM missions WHERE root_id=? ORDER BY created", (root_id,))]
            return [self.unpack(row) for row in db.execute("SELECT * FROM missions WHERE parent_id IS NULL ORDER BY created DESC LIMIT 200")]

    def recoverable(self):
        with self.store.connection() as db:
            return [self.unpack(row) for row in db.execute("SELECT * FROM missions WHERE parent_id IS NULL AND status IN ('queued','running','retrying') ORDER BY created")]

    def save(self, mission_id, **values):
        allowed = {"status", "state", "policy", "result", "reason", "steps", "tokens", "estimated_usage"}
        if not values or set(values) - allowed:
            raise ValueError("Invalid task update")
        for field in ["state", "policy"]:
            if field in values:
                values[field] = json.dumps(values[field])
        values["updated"] = time.time()
        fields = ",".join(key + "=?" for key in values)
        with self.store.connection() as db:
            db.execute(f"UPDATE missions SET {fields} WHERE id=?", (*values.values(), mission_id))

    def event(self, mission_id, kind, data):
        with self.store.connection() as db:
            cursor = db.execute("INSERT INTO mission_events(mission_id,kind,data,created) VALUES (?,?,?,?)", (mission_id, kind, json.dumps(data, ensure_ascii=False), time.time()))
            return cursor.lastrowid

    def events(self, mission_id, after=0, limit=100):
        with self.store.connection() as db:
            rows = db.execute("SELECT * FROM mission_events WHERE mission_id=? AND id>? ORDER BY id LIMIT ?", (mission_id, after, limit))
            return [{**dict(row), "data": json.loads(row["data"])} for row in rows]

    def recent(self, mission_id, limit=12):
        with self.store.connection() as db:
            rows = list(db.execute("SELECT * FROM mission_events WHERE mission_id=? ORDER BY id DESC LIMIT ?", (mission_id, limit)))
            return [{**dict(row), "data": json.loads(row["data"])} for row in reversed(rows)]

    def feedback(self, mission_id, text):
        return self.event(mission_id, "human_feedback", {"text": text})

    def human_context(self, mission):
        with self.store.connection() as db:
            rows = db.execute("SELECT id,data FROM mission_events WHERE mission_id IN (?,?) AND kind='human_feedback' ORDER BY id DESC LIMIT 8", (mission["id"], mission["root_id"]))
            return [{"id": row["id"], **json.loads(row["data"])} for row in reversed(list(rows))]

    def action(self, mission_id, action_id):
        with self.store.connection() as db:
            row = db.execute("SELECT * FROM mission_actions WHERE mission_id=? AND action_id=?", (mission_id, action_id)).fetchone()
            return {**dict(row), "result": json.loads(row["result"])} if row else None

    def start_action(self, mission_id, action_id, request):
        with self.store.connection() as db:
            db.execute("INSERT OR IGNORE INTO mission_actions(mission_id,action_id,request,status,created) VALUES (?,?,?,'pending',?)", (mission_id, action_id, json.dumps(request, sort_keys=True), time.time()))

    def finish_action(self, mission_id, action_id, result):
        with self.store.connection() as db:
            db.execute("UPDATE mission_actions SET status='done',result=? WHERE mission_id=? AND action_id=?", (json.dumps(result, ensure_ascii=False), mission_id, action_id))

    def evidence(self, mission):
        with self.store.connection() as db:
            own = [row["action_id"] for row in db.execute("SELECT action_id,result FROM mission_actions WHERE mission_id=? AND status='done'", (mission["id"],)) if json.loads(row["result"]).get("ok")]
            children = ["child:" + row["id"] for row in db.execute("SELECT id FROM missions WHERE parent_id=? AND status='completed'", (mission["id"],))]
            return own + children

    def totals(self, root_id):
        with self.store.connection() as db:
            row = db.execute("SELECT SUM(steps) AS steps, SUM(tokens) AS tokens, MAX(estimated_usage) AS estimated_usage FROM missions WHERE root_id=?", (root_id,)).fetchone()
            return dict(row)

    def evidence_details(self, mission, ids):
        details = []
        for evidence_id in ids[:8]:
            if evidence_id.startswith("child:"):
                child = self.get(evidence_id[6:])
                details.append({"id": evidence_id, "result": child["result"][:6000], "verification": child["reason"]})
            else:
                action = self.action(mission["id"], evidence_id)
                raw = json.dumps(action["result"], ensure_ascii=False)
                request = json.loads(action["request"])
                if "content" in request.get("arguments", {}):
                    text = request["arguments"]["content"]
                    request["arguments"]["content"] = text[:6000]
                    request["content_truncated"] = len(text)>6000
                details.append({"id": evidence_id, "request": request, "recorded_result": raw[:6000], "truncated": len(raw)>6000})
        return details
