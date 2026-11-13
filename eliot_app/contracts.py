"""Persisted goal contracts, dependency plans and deterministic outcome checks."""

from __future__ import annotations

import hashlib
from pathlib import Path
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .config import ConfigError


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    objective: str = Field(min_length=1, max_length=2000)
    depends_on: list[str] = Field(default_factory=list, max_length=30)
    status: Literal["pending", "running", "completed", "blocked"] = "pending"
    expected_output: str = Field(default="", max_length=2000)
    evidence: list[str] = Field(default_factory=list, max_length=30)


class SuccessCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["file_exists", "file_contains", "command_exit", "http_status"]
    path: str = Field(default="", max_length=200)
    text: str = Field(default="", max_length=2000)
    tool: str = Field(default="", max_length=64)
    expected: int = 0
    description: str = Field(default="", max_length=500)


def validate_plan(steps, valid_evidence):
    parsed = [PlanStep.model_validate(step).model_dump() for step in steps]
    by_id = {step["id"]: step for step in parsed}
    if len(by_id) != len(parsed):
        raise ConfigError("Plan step IDs must be unique.")
    visiting, visited = set(), set()

    def visit(key):
        if key in visiting:
            raise ConfigError("Plan dependencies contain a cycle.")
        if key in visited:
            return
        if key not in by_id:
            raise ConfigError("Plan dependency does not exist.")
        visiting.add(key)
        for dependency in by_id[key]["depends_on"]:
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key, step in by_id.items():
        visit(key)
        if not set(step["evidence"]) <= valid_evidence:
            raise ConfigError(
                "Plan evidence must refer to successful recorded actions."
            )
        if step["status"] == "completed":
            if not step["evidence"] or any(
                by_id[d]["status"] != "completed" for d in step["depends_on"]
            ):
                raise ConfigError(
                    "Completed steps need evidence and completed dependencies."
                )
    return parsed


def plan_fingerprint(steps):
    return hashlib.sha256(json.dumps(steps, sort_keys=True).encode()).hexdigest()


async def verify_contract(runtime, mission):
    """Checks are supplied by the operator, not rewritten by planner output."""
    results = []
    for raw in mission["state"].get("success_checks", []):
        check = SuccessCheck.model_validate(raw)
        passed, reason = False, ""
        try:
            if check.kind in {"file_exists", "file_contains"}:
                artifact = check.path.startswith(".eliot-artifacts/")
                if check.kind == "file_exists":
                    if artifact:
                        supplied = Path(check.path)
                        owners = {
                            member["id"]
                            for member in runtime.store.list(mission["root_id"])
                        }
                        if len(supplied.parts) < 3 or supplied.parts[1] not in owners:
                            raise ConfigError("Artifact not owned by this task.")
                        target = runtime.tools.artifact_path(
                            mission, Path(*supplied.parts[2:]), supplied.parts[1]
                        )
                    else:
                        target = runtime.tools.path(mission, check.path)
                    passed = target.is_file()
                else:
                    arguments = {"path": check.path, "start_line": 1, "limit": 200}
                    while True:
                        output = await runtime.tools.execute(
                            mission,
                            "read_artifact" if artifact else "read_file",
                            arguments,
                        )
                        if check.text in output["text"]:
                            passed = True
                            break
                        if output.get("next_character_offset") is not None:
                            arguments["character_offset"] = output[
                                "next_character_offset"
                            ]
                        elif output.get("next_start_line") is not None:
                            arguments.update(
                                start_line=output["next_start_line"], character_offset=0
                            )
                        else:
                            break
                reason = (
                    "File outcome inspected"
                    if passed
                    else "Required file or text absent"
                )
            else:
                actions = [
                    action
                    for member in runtime.store.list(mission["root_id"])
                    for action in runtime.store.actions(member["id"])
                ]
                for action in sorted(
                    actions, key=lambda item: item["created"], reverse=True
                ):
                    output = action["result"].get("output", {})
                    request = json.loads(action["request"])
                    if check.kind == "command_exit" and request["tool"] == (
                        check.tool or "run_command"
                    ):
                        argv = request.get("arguments", {}).get("argv", [])
                        if check.path and (not argv or argv[0] != check.path):
                            continue
                        passed = (
                            bool(action["result"].get("ok"))
                            and output.get("returncode") == check.expected
                        )
                    elif (
                        check.kind == "http_status"
                        and request["tool"] == "http_observe"
                    ):
                        url = output.get("url") or request.get("arguments", {}).get(
                            "url"
                        )
                        if check.path and url != check.path:
                            continue
                        passed = (
                            bool(action["result"].get("ok"))
                            and output.get("status") == check.expected
                        )
                    else:
                        continue
                    reason = "Latest matching tool outcome inspected"
                    break
        except (ConfigError, OSError, UnicodeError, ValueError):
            reason = "Required evidence is unavailable"
        results.append(
            {
                "check": raw,
                "passed": passed,
                "reason": reason or "No matching successful tool outcome",
            }
        )
    steps = mission["state"].get("plan_steps", [])
    if steps:
        results.append(
            {
                "check": {"kind": "plan_complete"},
                "passed": all(s["status"] == "completed" for s in steps),
                "reason": "All declared plan steps must complete",
            }
        )
    return results
