import json
import time

from fastapi.testclient import TestClient
import httpx
import pytest

from eliot_app.gateway import Gateway
from eliot_app.web import create_app


def profile_data(**changes):
    return {"id":"test", "name":"Test profile", "base_url":"https://fixture.example/v1", "model":"fixture", "streaming":False, **changes}


@pytest.fixture
def workspace(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"choices":[{"message":{"content":"A stored response <script>literal text</script>"},"finish_reason":"stop"}], "usage":{"total_tokens":7}})
    app = create_app(tmp_path / "config.yaml", Gateway(httpx.MockTransport(handler)))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        bootstrap = client.get("/api/bootstrap").json()
        client.headers["X-Eliot-Token"] = bootstrap["token"]
        yield client, app, requests, tmp_path


def test_complete_web_session_and_export(workspace):
    client, app, requests, tmp_path = workspace
    assert client.put("/api/providers/test", json=profile_data()).status_code == 200
    assert client.put("/api/providers/test/key", json={"api_key":"test-private-key"}).status_code == 200
    session = client.post("/api/sessions", json={}).json()
    run = client.post(f'/api/sessions/{session["id"]}/runs', json={"content":"hello"}).json()
    with client.stream("GET", f'/api/runs/{run["id"]}/events') as response:
        records = [json.loads(line[5:]) for line in response.iter_lines() if line.startswith("data:")]
    assert records[-1]["status"] == "completed"
    assert records[-1]["usage"]["total_tokens"] == 7
    exported = client.get(f'/api/sessions/{session["id"]}/export').json()
    assert [m["role"] for m in exported["messages"]] == ["user", "assistant"]
    assert len(requests) == 1 and json.loads(requests[0].content)["messages"][-1]["content"] == "hello"
    assert "test-private-key" not in client.get("/api/bootstrap").text
    assert "test-private-key" not in (tmp_path / "config.yaml").read_text()
    assert "test-private-key" not in client.get(f'/api/sessions/{session["id"]}/export').text
    client.put("/api/providers/test", json=profile_data(base_url="https://changed.example/v1"))
    assert not client.get("/api/providers").json()[0]["key_configured"]


def test_origin_host_and_token_protection(workspace):
    client, _, _, _ = workspace
    assert client.post("/api/sessions", json={}, headers={"Origin":"https://attacker.example"}).status_code == 403
    assert client.get("/api/bootstrap", headers={"Origin":"null"}).status_code == 403
    assert client.get("/api/bootstrap", headers={"Host":"attacker.example"}).status_code == 400
    assert client.post("/api/sessions", json={}, headers={"X-Eliot-Token":"bad"}).status_code == 403
    assert client.get("/").status_code == 200
    assert "frame-ancestors 'none'" in client.get("/").headers["content-security-policy"]


def test_validation_does_not_echo_key_and_missing_resources_are_404(workspace):
    client, _, _, _ = workspace
    result = client.put("/api/providers/test/key", json={"api_key":"private-value-" * 1000})
    assert result.status_code == 422 and "private-value" not in result.text
    assert client.get("/api/sessions/missing").status_code == 404
    assert client.get("/api/runs/missing").status_code == 404
    assert client.put("/api/providers/mismatch", json=profile_data()).status_code == 400


def test_provider_test_is_explicit(workspace):
    client, _, requests, _ = workspace
    client.put("/api/providers/test", json=profile_data(auth="none"))
    client.get("/api/bootstrap")
    client.get("/api/providers")
    assert requests == []
    assert client.post("/api/providers/test/test").json()["status"] == "healthy"
    assert len(requests) == 1


def test_failed_key_preflight_does_not_store_user_message(workspace):
    client, app, requests, _ = workspace
    client.put("/api/providers/test", json=profile_data(api_key_env="UNSET_ELIOT_TEST_KEY"))
    session = client.post("/api/sessions", json={}).json()
    result = client.post(f'/api/sessions/{session["id"]}/runs', json={"content":"hi"})
    assert result.status_code == 400
    assert client.get(f'/api/sessions/{session["id"]}').json()["messages"] == []


def test_sessions_and_context_survive_backend_restart(tmp_path):
    payloads = []
    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"choices":[{"message":{"content":"Saved answer"},"finish_reason":"stop"}]})
    path = tmp_path / "config.yaml"
    with TestClient(create_app(path, Gateway(httpx.MockTransport(handler))), base_url="http://127.0.0.1") as client:
        client.headers["X-Eliot-Token"] = client.get("/api/bootstrap").json()["token"]
        client.put("/api/providers/test", json=profile_data(auth="none"))
        session = client.post("/api/sessions", json={}).json()
        run = client.post(f'/api/sessions/{session["id"]}/runs', json={"content":"Remember my first question"}).json()
        client.get(f'/api/runs/{run["id"]}/events')
    with TestClient(create_app(path, Gateway(httpx.MockTransport(handler))), base_url="http://127.0.0.1") as client:
        client.headers["X-Eliot-Token"] = client.get("/api/bootstrap").json()["token"]
        assert client.get("/api/sessions").json()[0]["id"] == session["id"]
        run = client.post(f'/api/sessions/{session["id"]}/runs', json={"content":"What was it?"}).json()
        client.get(f'/api/runs/{run["id"]}/events')
        assert [m["content"] for m in payloads[-1]["messages"]][2:] == ["Remember my first question", "Saved answer", "What was it?"]


def test_api_cancellation_and_conflicting_sends(tmp_path):
    import asyncio
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
            await asyncio.sleep(20)
    gateway = Gateway(httpx.MockTransport(lambda request: httpx.Response(200, stream=SlowStream(), headers={"content-type":"text/event-stream"})))
    with TestClient(create_app(tmp_path / "config.yaml", gateway), base_url="http://127.0.0.1") as client:
        client.headers["X-Eliot-Token"] = client.get("/api/bootstrap").json()["token"]
        client.put("/api/providers/test", json=profile_data(auth="none", streaming=True))
        session = client.post("/api/sessions", json={}).json()
        path = f'/api/sessions/{session["id"]}/runs'
        run = client.post(path, json={"content":"first"}).json()
        assert client.post(path, json={"content":"second"}).status_code == 409
        assert client.delete(f'/api/sessions/{session["id"]}').status_code == 409
        assert client.put("/api/providers/test", json=profile_data()).status_code == 409
        assert client.post(f'/api/runs/{run["id"]}/cancel').json()["status"] == "cancelled"


def test_skill_reader_pages_and_invalid_requests(workspace):
    from eliot_app.instructions import SkillCatalog
    client, _, requests, _ = workspace
    catalog = SkillCatalog()
    skill_id = "triage-validation"
    first = client.get(f"/api/skills/{skill_id}")
    assert first.status_code == 200
    assert first.json() == catalog.read(skill_id)
    start = first.json()["end_line"] + 1
    second = client.get(f"/api/skills/{skill_id}?start_line={start}")
    assert second.json() == catalog.read(skill_id, start_line=start)
    assert second.json()["sha256"] == first.json()["sha256"]
    assert client.get(f"/api/skills/{skill_id}?start_line=0").status_code == 400
    assert client.get("/api/skills/missing").status_code == 400
    assert client.get(f"/api/skills/{skill_id}?start_line=bad").status_code == 422
    assert requests == []


def test_all_workspace_assets_are_served(workspace):
    client, _, _, _ = workspace
    html = client.get("/").text
    for asset in ("style.css", "app.js", "workspace.js", "neural.js"):
        assert f"/static/{asset}" in html
        response = client.get(f"/static/{asset}")
        assert response.status_code == 200 and len(response.content) > 100
