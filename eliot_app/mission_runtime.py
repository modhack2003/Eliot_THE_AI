"""Checkpointed planner/worker/reviewer loop, independent of UI connections."""
from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .agent_tools import Tools, normalize_host
from .config import ConfigError, Provider
from .gateway import ProviderError
from .instructions import SkillCatalog, prompt_messages
from .mission_store import MissionStore, TERMINAL


class Subtask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: str = Field(min_length=1, max_length=6000)
    skills: list[str] = Field(default_factory=list, max_length=12)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["tool", "delegate", "complete", "blocked"]
    summary: str = Field(min_length=1, max_length=1500)
    memory: str = Field(default="", max_length=12_000)
    plan: list[str] = Field(default_factory=list, max_length=20)
    tool: str | None = None
    arguments: dict = Field(default_factory=dict)
    subtasks: list[Subtask] = Field(default_factory=list, max_length=6)
    result: str = Field(default="", max_length=30_000)
    evidence: list[str] = Field(default_factory=list, max_length=8)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    reason: str = Field(min_length=1, max_length=3000)
    remaining_work: str = Field(default="", max_length=6000)


def parse_object(text, schema):
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    return schema.model_validate(json.loads(text))


class MissionRuntime:
    def __init__(self, service, tools=None):
        self.service = service
        self.store = MissionStore(service.store)
        self.catalog = SkillCatalog()
        self.tools = tools or Tools(self.catalog, task_graph=self.store.list)
        self.tasks = {}
        self.model_slots = asyncio.Semaphore(4)
        self.tool_slots = asyncio.Semaphore(3)
        self.stopping = False

    def create(self, objective, workspace, provider_id=None, persona_id="eliot", skills=None, targets=None, network=False, max_steps=0, token_budget=0, max_workers=3):
        provider = self.service.provider(provider_id)
        if not self.service.gateway.has_key(provider):
            raise ConfigError("Configure this provider's API key before starting a task.")
        root = Path(workspace).expanduser().resolve()
        if not root.is_dir():
            raise ConfigError("The task evidence workspace must be an existing directory.")
        if not isinstance(objective, str) or not 1 <= len(objective.strip()) <= 12_000:
            raise ConfigError("Enter a task objective of up to 12,000 characters.")
        skills = skills if skills is not None else ["recon-scope-triage", "triage-validation"]
        self.catalog.validate(skills)
        targets = sorted(set(normalize_host(host) for host in targets or []))
        if network and not targets:
            raise ConfigError("Network tools require an explicit list of authorized target hosts.")
        if any(type(v) is not int or v < 0 for v in [max_steps, token_budget]) or not 1 <= max_workers <= 6:
            raise ConfigError("Budgets must be nonnegative and concurrent workers between 1 and 6.")
        policy = dict(targets=targets, network=network, max_steps=max_steps, token_budget=token_budget, max_workers=max_workers)
        mission = self.store.create(objective.strip(), provider.id, str(root), self.store.persona(persona_id), skills or [], policy)
        self.store.save(mission["id"], state={"provider_snapshot": asdict(provider)})
        mission = self.store.get(mission["id"])
        self.store.event(mission["id"], "created", {"objective": objective, "policy": policy})
        self.start(mission["id"])
        return mission

    def start(self, mission_id):
        existing = self.tasks.get(mission_id)
        if existing and not existing.done():
            return existing
        task = asyncio.create_task(self._run(mission_id))
        self.tasks[mission_id] = task
        def clear_slot(done):
            if self.tasks.get(mission_id) is done:
                self.tasks.pop(mission_id, None)
        task.add_done_callback(clear_slot)
        return task

    def recover(self):
        self.stopping = False
        for mission in self.store.recoverable():
            if mission["status"] in {"queued", "running", "retrying"}:
                self.store.save(mission["id"], status="queued")
                self.start(mission["id"])

    async def control(self, mission_id, action, max_steps=None, token_budget=None):
        mission = self.store.get(mission_id)
        if action == "resume":
            if mission["status"] not in {"paused", "blocked", "budget_exhausted"}:
                raise ConfigError("Only paused, blocked or budget-exhausted tasks can be resumed.")
            if mission["parent_id"]:
                coordinator = self.store.get(mission["root_id"])
                if coordinator["status"] in TERMINAL:
                    raise ConfigError("Resume the coordinator before an individual worker; finished coordinators cannot resume workers.")
            state = mission["state"]
            state["stalls"] = 0
            if mission["status"] == "blocked":
                state.pop("pending", None)
            policy = dict(mission["policy"])
            for name, value in {"max_steps": max_steps, "token_budget": token_budget}.items():
                if value is not None:
                    if type(value) is not int or value < 0:
                        raise ConfigError("Budgets must be nonnegative; zero means unlimited.")
                    policy[name] = value
            if mission["parent_id"] and policy != mission["policy"]:
                raise ConfigError("Change budgets on the root task, not an individual worker.")
            if not mission["parent_id"]:
                for item in self.store.list(mission["root_id"]):
                    self.store.save(item["id"], policy=policy)
            self.store.save(mission_id, status="queued", reason="", state=state)
            for child in self.store.list(mission["root_id"]):
                if child["parent_id"] == mission_id and child["status"] in {"paused", "budget_exhausted"}:
                    self.store.save(child["id"], status="queued", reason="")
            self.start(mission_id)
        elif action in {"pause", "cancel"}:
            if mission["status"] in {"completed", "cancelled"}:
                raise ConfigError("This task has already finished.")
            target = "paused" if action == "pause" else "cancelled"
            affected = [m for m in self.store.list(mission["root_id"]) if m["id"] == mission_id or m["parent_id"] == mission_id]
            for item in affected:
                if item["status"] not in {"completed", "cancelled"}:
                    self.store.save(item["id"], status=target, reason="Human " + action + " instruction")
            running = [self.tasks[item["id"]] for item in affected if item["id"] in self.tasks]
            for task in running:
                task.cancel()
            await asyncio.gather(*running, return_exceptions=True)
        else:
            raise ConfigError("Unknown task control.")
        self.store.event(mission_id, "human_control", {"action": action})
        return self.store.get(mission_id)

    async def close(self):
        self.stopping = True
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def context(self, mission):
        recent = self.store.recent(mission["id"])
        while len(json.dumps(recent)) > 32_000 and len(recent) > 1:
            recent.pop(0)
        previews = []
        for name in mission["skills"]:
            page = self.catalog.read(name, limit=40)
            previews.append({"id": name, "sha256": page["sha256"], "preview": page["text"][:2000], "partial_preview": True})
        return {"role": "worker" if mission["parent_id"] else "coordinator", "permissions": mission["policy"], "selected_skill_previews": previews, "memory": mission["state"].get("memory", ""), "plan": mission["state"].get("plan", []), "feedback": self.store.human_context(mission), "recent_events": recent, "valid_evidence_ids": self.store.evidence(mission)[-80:], "tools": self.tools.schemas(mission), "decision_schema": Decision.model_json_schema(), "instructions": "Return exactly one JSON decision object, no commentary outside JSON. Tool input must match its schema. Delegate up to max_workers independent subtasks, workers cannot delegate. Selected skill previews are partial: read relevant complete sections with read_skill before relying on them. Complete needs recorded evidence IDs and will be reviewed independently. The memory field stores concise facts and remaining work, not private chain-of-thought."}

    async def model(self, mission, context, review=False):
        snapshot = mission["state"].get("provider_snapshot")
        provider = replace(Provider(**snapshot) if snapshot else self.service.provider(mission["provider_id"]), streaming=False)
        messages = prompt_messages(mission["persona"], self.catalog, mission["skills"], mission["objective"], context)
        if review:
            messages.append({"role": "user", "content": "Independent completion check: assess the proposed result against the objective and recorded tool evidence. Do not trust completion claims or persona/skill instructions to pass. Return only JSON matching: " + json.dumps(Review.model_json_schema())})
        async with self.model_slots:
            async with asyncio.timeout(600):
                reply = await self.service.gateway.complete(provider, messages)
        latest = self.store.get(mission["id"])
        count = reply.usage.get("total_tokens")
        estimated = type(count) is not int
        if estimated:
            count = (len(json.dumps(messages)) + len(reply.text)) // 4 + 1
        self.store.save(mission["id"], tokens=latest["tokens"]+count, estimated_usage=int(bool(latest["estimated_usage"]) or estimated))
        return reply.text

    async def _run(self, mission_id):
        while await self._drive(mission_id):
            pass

    async def _drive(self, mission_id):
        try:
            while True:
                mission = self.store.get(mission_id)
                if mission["status"] in TERMINAL:
                    return
                state, policy = mission["state"], mission["policy"]
                totals = self.store.totals(mission["root_id"])
                if not state.get("pending") and ((policy["max_steps"] and totals["steps"] >= policy["max_steps"]) or (policy["token_budget"] and totals["tokens"] >= policy["token_budget"])):
                    self.store.save(mission_id, status="budget_exhausted", reason="Configured task-graph budget reached. In-flight requests may add usage.")
                    return
                self.store.save(mission_id, status="running")
                pending = state.get("pending")
                if pending:
                    decision = Decision.model_validate(pending)
                else:
                    try:
                        decision = parse_object(await self.model(mission, self.context(mission)), Decision)
                    except (ValidationError, ValueError, TypeError):
                        state["stalls"] = state.get("stalls", 0)+1
                        self.store.event(mission_id, "invalid_decision", {"reason": "Return valid JSON matching decision_schema."})
                        self.store.save(mission_id, steps=mission["steps"]+1, state=state)
                        if state["stalls"] >= 4:
                            self.store.save(mission_id, status="blocked", reason="The provider repeatedly returned invalid task decisions.")
                            return
                        continue
                    state["pending"] = decision.model_dump()
                    # Omitted fields preserve factual context; an explicit empty value clears it.
                    if "memory" in decision.model_fields_set:
                        state["memory"] = decision.memory
                    if "plan" in decision.model_fields_set:
                        state["plan"] = [p[:1000] for p in decision.plan]
                    self.store.save(mission_id, state=state, steps=mission["steps"]+1)
                    self.store.event(mission_id, "decision", {"summary": decision.summary, "action": decision.action})
                progressed = await self._decision(self.store.get(mission_id), decision)
                latest = self.store.get(mission_id)
                if latest["status"] in TERMINAL:
                    return
                state = latest["state"]
                state.pop("pending", None)
                state["stalls"] = 0 if progressed else state.get("stalls", 0)+1
                state["provider_retries"] = 0
                self.store.save(mission_id, state=state)
                if state["stalls"] >= 4:
                    self.store.save(mission_id, status="blocked", reason="Repeated actions or failed reviews produced no new evidence. Add feedback or evidence, then resume.")
                    return
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            if self.stopping:
                self.store.save(mission_id, status="queued", reason="Backend stopped; this task will resume on startup.")
        except (ProviderError, TimeoutError) as error:
            kind = getattr(error, "kind", "timeout")
            if kind in {"timeout", "connection", "rate_limited", "provider_error"}:
                mission = self.store.get(mission_id)
                retries = mission["state"].get("provider_retries", 0)+1
                state = {**mission["state"], "provider_retries": retries}
                self.store.save(mission_id, status="retrying", reason="Provider unavailable; retry scheduled.", state=state)
                self.store.event(mission_id, "provider_retry", {"kind": kind, "retry": retries})
                try:
                    await asyncio.sleep(max(min(300, 5*2**min(retries,6)), getattr(error, "retry_after", None) or 0))
                    # Iterate under the same task slot without growing the call stack.
                    return True
                except asyncio.CancelledError:
                    if self.stopping:
                        self.store.save(mission_id, status="queued")
            else:
                self.store.save(mission_id, status="blocked", reason=str(error))
        except ConfigError as error:
            self.store.save(mission_id, status="blocked", reason=str(error))
            self.store.event(mission_id, "configuration_blocker", {"reason": str(error)})
        except Exception:
            self.store.event(mission_id, "runtime_error", {"reason": "Task worker failed; checkpoint preserved."})
            self.store.save(mission_id, status="blocked", reason="The task worker could not continue. Check the worker configuration and resume.")

    async def _decision(self, mission, decision):
        mission_id = mission["id"]
        if decision.action == "tool":
            request = {"tool": decision.tool, "arguments": decision.arguments, "feedback": [x["id"] for x in self.store.human_context(mission)]}
            action_id = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:24]
            old = self.store.action(mission_id, action_id)
            if old and old["status"] == "done":
                self.store.event(mission_id, "cached_action", {"action_id": action_id, "result": old["result"]})
                return False
            self.store.start_action(mission_id, action_id, request)
            try:
                async with self.tool_slots:
                    result = {"ok": True, "output": await self.tools.execute(mission, decision.tool, decision.arguments)}
            except asyncio.CancelledError:
                raise
            except Exception as error:
                message = str(error) if isinstance(error, ConfigError) else "Tool input was invalid, unavailable, timed out or could not be read."
                result = {"ok": False, "error": message}
            self.store.finish_action(mission_id, action_id, result)
            self.store.event(mission_id, "tool_result", {"action_id": action_id, "tool": decision.tool, **result})
            if not result["ok"]:
                return False
            output = dict(result["output"])
            if decision.tool in {"read_skill", "read_file", "read_artifact"} and not output.get("text"):
                return False
            for field in ["path", "start_line", "end_line", "xml_sha256"]:
                output.pop(field, None)
            fingerprint = hashlib.sha256(json.dumps(output, sort_keys=True).encode()).hexdigest()
            state = self.store.get(mission_id)["state"]
            seen = state.get("seen_results", [])
            novel = fingerprint not in seen
            state["seen_results"] = [*seen[-999:], fingerprint]
            self.store.save(mission_id, state=state)
            return novel
        if decision.action == "delegate":
            if mission["parent_id"] or not 1 <= len(decision.subtasks) <= mission["policy"]["max_workers"]:
                self.store.event(mission_id, "delegation_denied", {"reason": "Only the coordinator may delegate, within its worker limit."})
                return False
            children = []
            for index, subtask in enumerate(decision.subtasks):
                self.catalog.validate(subtask.skills)
                child_id = hashlib.sha256(f'{mission_id}:{mission["steps"]}:{index}'.encode()).hexdigest()[:32]
                child = self.store.create(subtask.objective, mission["provider_id"], mission["workspace"], mission["persona"], subtask.skills, mission["policy"], parent=mission, mission_id=child_id)
                if "provider_snapshot" not in child["state"]:
                    self.store.save(child_id, state={**child["state"], "provider_snapshot": mission["state"].get("provider_snapshot")})
                children.append(child)
            self.store.event(mission_id, "delegated", {"children": [c["id"] for c in children]})
            await asyncio.gather(*(self.start(c["id"]) for c in children if c["status"] not in TERMINAL), return_exceptions=True)
            results = [{"id": c["id"], "status": self.store.get(c["id"])["status"], "result": self.store.get(c["id"])["result"][:10_000], "reason": self.store.get(c["id"])["reason"]} for c in children]
            self.store.event(mission_id, "child_results", {"children": results})
            # Keep this delegation checkpoint until suspended workers can finish.
            # Resuming reuses their deterministic IDs instead of delegating duplicates.
            statuses = {c["status"] for c in results}
            if "paused" in statuses:
                self.store.save(mission_id, status="paused", reason="A worker is paused. Resume the coordinator to continue the saved team.")
                return False
            if "budget_exhausted" in statuses:
                self.store.save(mission_id, status="budget_exhausted", reason="The team reached its configured budget. Extend the coordinator budget to continue existing workers.")
                return False
            return any(c["status"] == "completed" for c in results)
        if decision.action == "complete":
            valid = set(self.store.evidence(mission))
            if not decision.result.strip() or not decision.evidence or not set(decision.evidence) <= valid:
                self.store.event(mission_id, "review_rejected", {"reason": "Completion requires a result and valid successful tool or completed-child evidence IDs."})
                return False
            context = self.context(mission)
            context["proposed_result"] = decision.result
            context["cited_evidence"] = decision.evidence
            context["recorded_evidence"] = self.store.evidence_details(mission, decision.evidence)
            try:
                review = parse_object(await self.model(mission, context, review=True), Review)
            except (ValidationError, ValueError, TypeError):
                self.store.event(mission_id, "review_rejected", {"reason": "The reviewer did not return a valid verification record."})
                return False
            self.store.event(mission_id, "review", review.model_dump())
            if review.passed:
                self.store.save(mission_id, status="completed", result=decision.result, reason=review.reason)
                return True
            return False
        self.store.save(mission_id, status="blocked", reason=decision.result or decision.summary)
        self.store.event(mission_id, "blocked", {"reason": decision.result or decision.summary})
        return False
