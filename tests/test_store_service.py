import asyncio

import pytest

from eliot_app.config import Settings
from eliot_app.gateway import Reply
from eliot_app.service import Service
from eliot_app.store import BusyError, Store
from test_gateway import profile


def test_persistence_history_and_concurrent_run_guard(tmp_path):
    path = tmp_path / "db.sqlite"
    store = Store(path)
    session = store.create_session()
    run = store.begin_run(session["id"], profile(), "First question")
    with pytest.raises(BusyError):
        store.begin_run(session["id"], profile(), "Duplicate")
    store.update(run["id"], "completed", "First answer", finish_reason="stop")
    other = store.begin_run(session["id"], profile(), "Failed question")
    store.update(other["id"], "failed", "partial", error="failure")
    final = store.begin_run(session["id"], profile(), "Next question")
    loaded = Store(path)
    assert loaded.history(session["id"], final["id"]) == [{"role":"user","content":"First question"},{"role":"assistant","content":"First answer"},{"role":"user","content":"Next question"}]
    assert len(loaded.session(session["id"])["messages"]) == 4
    assert loaded.session(session["id"])["title"] == "First question"
    with pytest.raises(BusyError):
        loaded.delete_session(session["id"])
    loaded.update(final["id"], "cancelled")
    loaded.delete_session(session["id"])
    assert loaded.list_sessions() == []
    with pytest.raises(KeyError):
        loaded.run(run["id"])


def test_crash_recovery_keeps_partial_text(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    run = store.begin_run(store.create_session()["id"], profile(), "Question")
    store.update(run["id"], "running", "Partial")
    store.recover()
    recovered = store.run(run["id"])
    assert recovered["status"] == "interrupted" and recovered["text"] == "Partial"


async def test_shared_service_completion_and_cancellation(tmp_path):
    class FakeGateway:
        runtime_keys = {}
        def has_key(self, provider):
            return True
        async def complete(self, provider, messages, delta):
            await delta("partial")
            await asyncio.sleep(10)
            return Reply("done", "stop")
    settings = Settings(tmp_path / "config.yaml")
    settings.save_provider(profile(auth="none"))
    service = Service(settings, FakeGateway())
    run = service.start(service.store.create_session()["id"], "Question")
    await asyncio.sleep(.01)
    result = await service.cancel(run["id"])
    assert result["status"] == "cancelled" and result["text"] == "partial"
    assert result["error_kind"] == "cancelled"
    await service.close()


async def test_immediate_cancellation_finishes_queued_run(tmp_path):
    class FakeGateway:
        def has_key(self, provider):
            return True
    settings = Settings(tmp_path / "config.yaml")
    settings.save_provider(profile(auth="none"))
    service = Service(settings, FakeGateway())
    run = service.start(service.store.create_session()["id"], "Question")
    assert (await service.cancel(run["id"]))["status"] == "cancelled"
