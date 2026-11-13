import asyncio
import json
import threading

import pytest

from eliot_app.config import ConfigError
from eliot_app.mission_runtime import Decision
from test_gateway import profile
from test_missions import Planner, finished, setup_runtime
from eliot_app.gateway import Reply


def tool(name, **arguments):
    return Decision(
        action="tool",
        summary="Inspect the supplied source",
        tool=name,
        arguments=arguments,
    )


async def paused(tmp_path):
    runtime = setup_runtime(tmp_path)
    root = runtime.create("Review supplied evidence", str(tmp_path))
    await runtime.control(root["id"], "pause")
    return runtime, runtime.store.get(root["id"])


async def test_artifact_directory_symlink_cannot_read_secret_or_write_workspace(
    tmp_path,
):
    runtime, root = await paused(tmp_path)
    (tmp_path / ".eliot-artifacts").mkdir()
    try:
        (tmp_path / ".eliot-artifacts" / root["id"]).symlink_to(
            tmp_path, target_is_directory=True
        )
    except OSError:
        pytest.skip("Symlink creation is not permitted on this host")
    (tmp_path / ".env").write_text("SYNTHETIC_SECRET=fixture")
    for name, args in [
        ("read_artifact", {"path": f".eliot-artifacts/{root['id']}/.env"}),
        ("write_artifact", {"path": "escaped.txt", "content": "fixture"}),
    ]:
        with pytest.raises(ConfigError):
            await runtime.tools.execute(root, name, args)
    assert not (tmp_path / "escaped.txt").exists()


async def test_snapshot_never_receives_replacement_endpoint_key(tmp_path):
    runtime, root = await paused(tmp_path)
    original = profile(auth="bearer")
    runtime.store.save(root["id"], state={"provider_snapshot": original.__dict__})
    runtime.service.settings.save_provider(
        profile(auth="bearer", base_url="https://replacement.example/v1")
    )
    with pytest.raises(ConfigError, match="binding changed"):
        await runtime.model(runtime.store.get(root["id"]), {})


async def test_fixed_failure_and_changed_source_are_observed(tmp_path):
    runtime, root = await paused(tmp_path)
    read = tool("read_file", path="new.txt")
    assert not await runtime._decision(root, read)
    (tmp_path / "new.txt").write_text("First observation")
    assert await runtime._decision(runtime.store.get(root["id"]), read)
    (tmp_path / "new.txt").write_text("Second changed observation")
    assert await runtime._decision(runtime.store.get(root["id"]), read)
    last = runtime.store.events(root["id"])[-1]
    assert "Second changed observation" in last["data"]["output"]["text"]


async def test_distinct_sources_count_even_when_text_is_identical(tmp_path):
    runtime, root = await paused(tmp_path)
    for index in range(5):
        (tmp_path / f"source-{index}.txt").write_text(
            "Identical text from a required source"
        )
        assert await runtime._decision(
            runtime.store.get(root["id"]), tool("read_file", path=f"source-{index}.txt")
        )


async def test_cancel_waits_for_atomic_write_and_journals_its_result(tmp_path):
    runtime, root = await paused(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = runtime.tools.local

    def delayed(*args):
        entered.set()
        assert release.wait(3)
        return original(*args)

    runtime.tools.local = delayed
    action = asyncio.create_task(
        runtime._decision(
            root, tool("write_artifact", path="settled.txt", content="Recorded effect")
        )
    )
    assert await asyncio.to_thread(entered.wait, 2)
    action.cancel()
    await asyncio.sleep(0)
    assert not action.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await action
    assert (tmp_path / ".eliot-artifacts" / root["id"] / "settled.txt").exists()
    assert len(runtime.store.evidence(root)) == 1


async def test_duplicate_delegation_reuses_worker_and_blocks_cycle(tmp_path):
    class Repeater(Planner):
        async def complete(self, provider, messages, on_delta=None):
            if messages[-1]["content"].startswith("Independent completion check"):
                return await super().complete(provider, messages, on_delta)
            context = json.loads(
                messages[-1]["content"].split(
                    "RUNTIME CONTEXT AND RECORDED EVIDENCE:\n", 1
                )[1]
            )
            if context["role"] == "coordinator":
                return Reply(
                    json.dumps(
                        {
                            "action": "delegate",
                            "summary": "Delegate the same objective",
                            "subtasks": [{"objective": "Inspect identical evidence"}],
                        }
                    ),
                    "stop",
                )
            return await super().complete(provider, messages, on_delta)

    runtime = setup_runtime(tmp_path, Repeater())
    root = runtime.create("Complete a useful review", str(tmp_path))
    result = await finished(runtime, root["id"])
    assert result["status"] == "blocked"
    assert len(runtime.store.list(root["id"])) == 2
