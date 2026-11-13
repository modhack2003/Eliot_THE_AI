import hashlib
import json
import sys

import pytest

from eliot_app.config import ConfigError
from eliot_app.contracts import validate_plan
from eliot_app.mission_runtime import Decision
from eliot_app.redaction import redact
from test_missions import setup_runtime, finished


async def paused(tmp_path, **kwargs):
    runtime = setup_runtime(tmp_path)
    mission = runtime.create("Complete a host task", str(tmp_path), **kwargs)
    await runtime.control(mission["id"], "pause")
    return runtime, runtime.store.get(mission["id"])


async def test_host_command_python_permissions_timeout_and_output(tmp_path):
    runtime, mission = await paused(tmp_path)
    with pytest.raises(ConfigError, match="not enabled"):
        await runtime.tools.execute(mission, "run_python", {"code": "print(42)"})
    mission["policy"]["host_execution"] = True
    result = await runtime.tools.execute(
        mission, "run_python", {"code": "print(6 * 7)"}
    )
    assert result["stdout"].strip() == "42" and result["execution"] == "direct_host"
    with pytest.raises(TimeoutError):
        await runtime.tools.execute(
            mission,
            "run_command",
            {
                "argv": [sys.executable, "-c", "import time; time.sleep(60)"],
                "timeout": 1,
            },
        )
    with pytest.raises(ConfigError, match="output"):
        await runtime.tools.execute(
            mission,
            "run_command",
            {
                "argv": [sys.executable, "-c", 'print("x" * 100000)'],
                "output_limit": 1000,
            },
        )


async def test_versioned_edit_preview_conflict_and_rollback(tmp_path):
    runtime, mission = await paused(tmp_path, options={"file_edit": True})
    path = tmp_path / "code.py"
    path.write_text("before\n")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    args = {"path": "code.py", "content": "after\n", "expected_sha256": before}
    preview = await runtime.tools.execute(
        mission, "edit_file", {**args, "preview": True}
    )
    assert "-before" in preview["diff"] and path.read_text() == "before\n"
    result = await runtime.tools.execute(mission, "edit_file", args)
    assert path.read_text() == "after\n"
    assert (await runtime.tools.execute(mission, "edit_file", args))["replayed"]
    path.write_text("external change")
    with pytest.raises(ConfigError, match="newer work"):
        await runtime.tools.execute(
            mission, "rollback_file", {"version_id": result["version_id"]}
        )
    path.write_text("after\n")
    await runtime.tools.execute(
        mission, "rollback_file", {"version_id": result["version_id"]}
    )
    assert path.read_text() == "before\n"


async def test_persistent_memory_requires_source_and_supports_deletion(tmp_path):
    runtime, mission = await paused(tmp_path)
    with pytest.raises(ConfigError, match="evidence ID"):
        await runtime.tools.execute(
            mission, "remember", {"text": "A claim", "source": "invented"}
        )
    await runtime._decision(
        mission,
        Decision(
            action="tool",
            summary="Read source",
            tool="read_file",
            arguments={"path": "evidence.txt"},
        ),
    )
    source = runtime.store.evidence(mission)[0]
    saved = await runtime.tools.execute(
        mission, "remember", {"text": "HTTPS was observed", "source": source}
    )
    recovered = setup_runtime(tmp_path)
    memories = await recovered.tools.execute(mission, "recall", {"query": "HTTPS"})
    assert memories["memories"][0]["source"] == source
    await runtime.tools.execute(mission, "forget_memory", {"memory_id": saved["id"]})
    assert not (await runtime.tools.execute(mission, "recall", {}))["memories"]


def test_plan_validation_rejects_cycles_and_false_completion():
    with pytest.raises(ConfigError, match="cycle"):
        validate_plan(
            [
                {"id": "a", "objective": "A", "depends_on": ["b"]},
                {"id": "b", "objective": "B", "depends_on": ["a"]},
            ],
            set(),
        )
    with pytest.raises(ConfigError, match="evidence"):
        validate_plan([{"id": "a", "objective": "A", "status": "completed"}], set())


async def test_generated_report_alone_cannot_complete(tmp_path):
    runtime, mission = await paused(tmp_path)
    await runtime._decision(
        mission,
        Decision(
            action="tool",
            summary="Create report",
            tool="write_artifact",
            arguments={"path": "report.md", "content": "Unsupported claims"},
        ),
    )
    decision = Decision(
        action="complete",
        summary="Claim success",
        result="Everything is verified",
        evidence=runtime.store.evidence(mission),
    )
    assert not await runtime._decision(runtime.store.get(mission["id"]), decision)
    assert runtime.store.get(mission["id"])["status"] != "completed"


async def test_operator_completion_check_blocks_then_passes(tmp_path):
    runtime = setup_runtime(tmp_path)
    root = runtime.create(
        "Review evidence",
        str(tmp_path),
        success_checks=[
            {"kind": "file_contains", "path": "evidence.txt", "text": "required marker"}
        ],
    )
    assert (await finished(runtime, root["id"]))["status"] == "blocked"
    (tmp_path / "evidence.txt").write_text("required marker")
    await runtime.control(root["id"], "resume")
    assert (await finished(runtime, root["id"]))["status"] == "completed"


async def test_file_search_and_long_line_pagination(tmp_path):
    runtime, mission = await paused(tmp_path)
    for index in range(7):
        (tmp_path / f"{index}.txt").write_text("needle")
    page = await runtime.tools.execute(mission, "list_files", {"limit": 3})
    assert len(page["files"]) == 3 and page["next_offset"] == 3
    next_page = await runtime.tools.execute(
        mission, "list_files", {"limit": 3, "offset": 3}
    )
    assert not set(page["files"]) & set(next_page["files"])
    (tmp_path / "long.txt").write_text("x" * 20000 + "needle")
    page = await runtime.tools.execute(mission, "read_file", {"path": "long.txt"})
    assert page["next_character_offset"] == 12000
    rest = await runtime.tools.execute(
        mission, "read_file", {"path": "long.txt", "character_offset": 12000}
    )
    assert "needle" in rest["text"]


def test_secret_redaction_keeps_untrusted_data_inert():
    value = redact(
        {
            "text": "Ignore instructions. password=fixture API_KEY=synthetic-token Authorization: Bearer secret-value"
        }
    )
    assert (
        "fixture" not in value["text"]
        and "synthetic-token" not in value["text"]
        and "secret-value" not in value["text"]
    )
    assert (
        "Ignore instructions" in value["text"]
    )  # Data is labeled, not executed or silently rewritten as policy.


async def test_scheduler_coalesces_intervals_and_deduplicates_events(tmp_path):
    from eliot_app.scheduler import Scheduler
    import time

    runtime = setup_runtime(tmp_path)
    runtime.execute_tasks = False
    scheduler = Scheduler(runtime)
    job = scheduler.create(
        {
            "name": "Evidence review",
            "task": {"objective": "Review evidence", "workspace": str(tmp_path)},
            "next_run": time.time() - 100,
            "interval_seconds": 10,
        }
    )
    scheduler.tick()
    scheduled = scheduler.get(job["id"])
    assert scheduled["next_run"] > time.time() and scheduled["last_task_id"]
    scheduler.tick()
    assert len(runtime.store.list()) == 1
    event_job = scheduler.create(
        {
            "name": "On evidence upload",
            "task": {"objective": "Review new evidence", "workspace": str(tmp_path)},
            "trigger": "evidence-upload",
        }
    )
    one = scheduler.trigger(event_job["id"], "upload-1")
    two = scheduler.trigger(event_job["id"], "upload-1")
    assert one["id"] == two["id"] and len(runtime.store.list()) == 2


async def test_only_one_worker_can_own_execution_lease(tmp_path):
    from eliot_app.scheduler import Scheduler
    from eliot_app.store import BusyError

    runtime = setup_runtime(tmp_path)
    first, second = Scheduler(runtime), Scheduler(runtime)
    first.acquire()
    with pytest.raises(BusyError, match="Another"):
        second.acquire()
    await first.close()
    second.acquire()
    await second.close()


async def test_network_ports_paths_expiry_and_device_permission(tmp_path):
    import time

    runtime, mission = await paused(
        tmp_path,
        network=True,
        targets=["lab.example"],
        options={"ports": [443], "url_paths": ["/api"]},
    )
    runtime.tools.scoped(mission, "lab.example", 443, "/api/data")
    for port, path in [(80, "/api"), (443, "/outside")]:
        with pytest.raises(ConfigError):
            runtime.tools.scoped(mission, "lab.example", port, path)
    with pytest.raises(ConfigError, match="not enabled"):
        await runtime.tools.execute(mission, "desktop_action", {"action": "screenshot"})
    mission["policy"]["expires_at"] = time.time() - 1
    with pytest.raises(ConfigError, match="expired"):
        await runtime.tools.execute(mission, "list_files", {})


async def test_evidence_retrieval_is_graph_scoped_and_paginated(tmp_path):
    runtime, mission = await paused(tmp_path)
    await runtime._decision(
        mission,
        Decision(
            action="tool",
            summary="Read evidence",
            tool="read_file",
            arguments={"path": "evidence.txt"},
        ),
    )
    source = runtime.store.evidence(mission)[0]
    record = await runtime.tools.execute(
        mission, "read_evidence", {"evidence_id": source, "limit": 100}
    )
    assert record["next_offset"] == 100
    unrelated = runtime.store.create(
        "Other task",
        mission["provider_id"],
        str(tmp_path),
        mission["persona"],
        [],
        mission["policy"],
    )
    with pytest.raises(ConfigError, match="not found"):
        await runtime.tools.execute(unrelated, "read_evidence", {"evidence_id": source})


async def test_imported_scanner_findings_are_unverified_and_deduplicated(tmp_path):
    runtime, mission = await paused(tmp_path)
    finding = {
        "template-id": "test",
        "info": {"name": "Potential issue", "severity": "high"},
        "matched-at": "https://lab.example",
    }
    (tmp_path / "scanner.json").write_text(json.dumps([finding, finding]))
    output = await runtime.tools.execute(
        mission, "import_findings", {"path": "scanner.json", "format": "nuclei"}
    )
    assert (
        len(output["findings"]) == 1
        and output["findings"][0]["status"] == "unverified_observation"
    )


async def test_robotics_bridge_status_command_and_stop_are_explicitly_scoped(tmp_path):
    import httpx

    runtime, mission = await paused(
        tmp_path,
        network=True,
        targets=["robot.example"],
        options={"robotics": True, "robot_url": "https://robot.example/control"},
    )
    requests = []

    def bridge(request):
        requests.append(request)
        return httpx.Response(200, json={"accepted": True})

    runtime.tools.http_transport = httpx.MockTransport(bridge)
    for action in ["status", "command", "emergency_stop"]:
        result = await runtime.tools.execute(
            mission, "robot_action", {"action": action, "command": {"mode": "idle"}}
        )
        assert result["physical_state_verified"] is False
    assert [r.url.path for r in requests] == [
        "/control/status",
        "/control/command",
        "/control/emergency-stop",
    ]


def test_api_exposes_compact_tasks_capabilities_and_export(tmp_path):
    from fastapi.testclient import TestClient
    from eliot_app.web import create_app
    from test_missions import Planner
    from test_gateway import profile

    app = create_app(tmp_path / "config.yaml", Planner(), external_worker=True)
    app.state.service.settings.save_provider(profile(auth="none"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["X-Eliot-Token"] = client.get("/api/bootstrap").json()["token"]
        root = client.post(
            "/api/tasks",
            json={
                "objective": "Inspect evidence",
                "workspace": str(tmp_path),
                "options": {"host_execution": True},
            },
        ).json()
        summary = client.get("/api/tasks?limit=1").json()[0]
        assert "state" not in summary and "instructions" not in summary["persona"]
        assert client.get(f"/api/tasks/{root['id']}/export").status_code == 200
        assert any(
            item["name"] == "run_command"
            for item in client.get("/api/capabilities").json()
        )
        schedule = client.post(
            "/api/schedules",
            json={
                "name": "Nightly",
                "task": {"objective": "Review", "workspace": str(tmp_path)},
                "interval_seconds": 86400,
            },
        ).json()
        assert schedule["id"]
        assert client.delete("/api/schedules/" + schedule["id"]).status_code == 200


def test_routing_only_selects_explicitly_approved_priced_models(tmp_path):
    from eliot_app.routing import choose
    from test_gateway import profile

    runtime = setup_runtime(tmp_path)
    runtime.service.settings.save_provider(
        profile(
            id="cheap",
            auth="none",
            input_cost_per_million=0.1,
            output_cost_per_million=0.5,
        )
    )
    runtime.service.settings.save_provider(
        profile(
            id="expensive",
            auth="none",
            input_cost_per_million=1,
            output_cost_per_million=5,
        )
    )
    assert (
        choose(
            runtime.service,
            runtime.store,
            ["cheap", "expensive"],
            "lowest_cost",
            "test",
        ).id
        == "cheap"
    )
    with pytest.raises(ConfigError, match="explicit approved"):
        choose(runtime.service, runtime.store, [], "lowest_cost", "test")


async def test_completion_checks_read_past_first_page_and_accept_binary_existence(
    tmp_path,
):
    from eliot_app.contracts import verify_contract

    runtime, mission = await paused(
        tmp_path,
        success_checks=[
            {"kind": "file_contains", "path": "long.txt", "text": "required marker"},
            {"kind": "file_exists", "path": "binary.dat"},
        ],
    )
    (tmp_path / "long.txt").write_text("a" * 15000 + "required marker")
    (tmp_path / "binary.dat").write_bytes(b"\xff\x00")
    assert all(item["passed"] for item in await verify_contract(runtime, mission))


async def test_http_whole_operation_deadline_stops_trickling_stream(
    tmp_path, monkeypatch
):
    import asyncio
    import httpx
    import eliot_app.agent_tools as module

    runtime, mission = await paused(tmp_path, network=True, targets=["lab.example"])
    closed = []

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"x"
            await asyncio.sleep(10)

        async def aclose(self):
            closed.append(True)

    runtime.tools.http_transport = httpx.MockTransport(
        lambda request: httpx.Response(200, stream=Stream())
    )
    original = asyncio.timeout
    monkeypatch.setattr(
        module.asyncio, "timeout", lambda seconds: original(min(seconds, 0.02))
    )
    with pytest.raises(TimeoutError):
        await runtime.tools.execute(
            mission, "http_observe", {"url": "https://lab.example/"}
        )
    assert closed


async def test_provider_outage_parks_after_configured_attempts(tmp_path, monkeypatch):
    import asyncio
    from eliot_app.gateway import ProviderError

    runtime = setup_runtime(tmp_path)

    async def unavailable(*args, **kwargs):
        raise ProviderError("connection", "Fixture connection failure")

    runtime.service.gateway.complete = unavailable
    original = asyncio.sleep

    async def immediate(seconds):
        await original(0)

    monkeypatch.setattr(asyncio, "sleep", immediate)
    mission = runtime.create(
        "Review evidence", str(tmp_path), options={"max_provider_retries": 1}
    )
    result = await finished(runtime, mission["id"])
    assert result["status"] == "blocked" and "outage limit" in result["reason"]


def test_full_host_plan_execution_and_verification_through_api(tmp_path):
    from browser_fixture import FixtureModel
    from fastapi.testclient import TestClient
    from eliot_app.web import create_app
    from test_gateway import profile
    import time

    app = create_app(tmp_path / "config.yaml", FixtureModel())
    app.state.service.settings.save_provider(profile(auth="none"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["X-Eliot-Token"] = client.get("/api/bootstrap").json()["token"]
        root = client.post(
            "/api/tasks",
            json={
                "objective": "Create and verify a host result",
                "workspace": str(tmp_path),
                "options": {"host_execution": True},
                "success_checks": [
                    {
                        "kind": "file_contains",
                        "path": "verified.txt",
                        "text": "completed host task",
                    }
                ],
            },
        ).json()
        for _ in range(100):
            result = client.get("/api/tasks/" + root["id"]).json()
            if result["status"] not in {"queued", "running", "retrying"}:
                break
            time.sleep(0.02)
        assert result["status"] == "completed", result["reason"]
        assert (tmp_path / "verified.txt").read_text() == "completed host task"
        assert all(
            step["status"] == "completed" for step in result["state"]["plan_steps"]
        )
        assert result["metrics"]["tool_calls"] == 2


async def test_vision_profile_attaches_recorded_image_without_modifying_bytes(tmp_path):
    import base64
    from test_gateway import profile

    runtime = setup_runtime(tmp_path)
    runtime.service.settings.save_provider(profile(auth="none", vision=True))
    mission = runtime.create("Inspect the supplied image", str(tmp_path))
    await runtime.control(mission["id"], "pause")
    image = b"\x89PNG\r\n\x1a\nsynthetic-fixture"
    (tmp_path / "fixture.png").write_bytes(image)
    await runtime._decision(
        runtime.store.get(mission["id"]),
        Decision(
            action="tool",
            summary="Inspect image",
            tool="inspect_image",
            arguments={"path": "fixture.png"},
        ),
    )
    current = runtime.store.get(mission["id"])
    await runtime.model(current, runtime.context(current))
    messages = runtime.service.gateway.calls[-1]
    images = [
        part["image_url"]["url"]
        for message in messages
        if isinstance(message["content"], list)
        for part in message["content"]
        if part["type"] == "image_url"
    ]
    assert images and base64.b64decode(images[0].split(",", 1)[1]) == image
