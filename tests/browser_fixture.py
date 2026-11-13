"""Loopback-only deterministic model fixture for the optional browser flow test."""

import json
import os
from pathlib import Path
from eliot_app.gateway import Reply
from eliot_app.web import create_app


class FixtureModel:
    runtime_keys = {}

    def has_key(self, provider):
        return True

    async def complete(self, provider, messages, on_delta=None):
        review = messages[-1]["content"].startswith("Independent completion check")
        content = messages[-2 if review else -1]["content"]
        context = json.loads(
            content.split("RUNTIME CONTEXT AND RECORDED EVIDENCE:\n", 1)[1]
        )
        evidence = context["valid_evidence_ids"]
        steps = context.get("plan_steps", [])
        if review:
            result = {
                "passed": True,
                "reason": "The file and host-process observations support completion.",
            }
        elif not steps:
            result = {
                "action": "plan",
                "summary": "Plan the requested host task",
                "plan_steps": [
                    {
                        "id": "generate",
                        "objective": "Generate result",
                        "expected_output": "verified.txt",
                    },
                    {
                        "id": "verify",
                        "objective": "Verify result",
                        "depends_on": ["generate"],
                        "expected_output": "Required text confirmed",
                    },
                ],
            }
        elif not evidence:
            result = {
                "action": "tool",
                "summary": "Generate the requested file on the host",
                "tool": "run_python",
                "arguments": {
                    "code": "from pathlib import Path; Path('verified.txt').write_text('completed host task')"
                },
            }
        elif len(evidence) < 2:
            result = {
                "action": "tool",
                "summary": "Read back actual file contents",
                "tool": "read_file",
                "arguments": {"path": "verified.txt"},
            }
        elif any(step["status"] != "completed" for step in steps):
            result = {
                "action": "plan",
                "summary": "Record verified plan completion",
                "plan_steps": [
                    {**step, "status": "completed", "evidence": [evidence[-1]]}
                    for step in steps
                ],
            }
        else:
            result = {
                "action": "complete",
                "summary": "Deliver verified file",
                "result": "Created verified.txt on the host and read back its required contents.",
                "evidence": [evidence[-1]],
            }
        return Reply(json.dumps(result), "stop", {"total_tokens": 10})


app = (
    create_app(Path(os.environ["ELIOT_E2E_DIRECTORY"]) / "config.yaml", FixtureModel())
    if os.environ.get("ELIOT_E2E_DIRECTORY")
    else None
)
