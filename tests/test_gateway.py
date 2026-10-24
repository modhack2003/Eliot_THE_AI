import json

import httpx
import pytest

from eliot_app.config import ConfigError, Provider, Settings
from eliot_app.gateway import Gateway, ProviderError


def profile(**values):
    return Provider(**{ "id": "one", "name": "Provider one", "base_url": "https://one.example/v1", "model": "exact-model", "streaming": False, **values})


def response(text="Hello", finish="stop"):
    return {"choices": [{"message": {"content": text}, "finish_reason": finish}], "usage": {"total_tokens": 12}}


async def test_distinct_endpoints_credentials_models_and_parameters(monkeypatch):
    monkeypatch.setenv("TEST_KEY_ONE", "test-secret-one")
    monkeypatch.setenv("TEST_KEY_TWO", "test-secret-two")
    requests = []
    async def handler(request):
        requests.append(request)
        return httpx.Response(200, json=response())
    gateway = Gateway(httpx.MockTransport(handler))
    one = profile(api_key_env="TEST_KEY_ONE", parameters={"max_completion_tokens": 100})
    two = profile(id="two", base_url="https://two.example/custom/v1/", model="another-model", api_key_env="TEST_KEY_TWO")
    await gateway.complete(one, [{"role": "user", "content": "first"}])
    await gateway.complete(two, [{"role": "user", "content": "second"}])
    assert str(requests[0].url) == "https://one.example/v1/chat/completions"
    assert str(requests[1].url) == "https://two.example/custom/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer test-secret-one"
    assert requests[1].headers["authorization"] == "Bearer test-secret-two"
    assert json.loads(requests[0].content)["max_completion_tokens"] == 100
    assert "temperature" not in json.loads(requests[1].content)
    assert json.loads(requests[1].content)["model"] == "another-model"


async def test_keyless_has_no_authorization_header():
    def handler(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, json=response())
    assert (await Gateway(httpx.MockTransport(handler)).complete(profile(auth="none"), [])).text == "Hello"


async def test_streaming_normalization():
    chunks = [dict(choices=[dict(delta={"content": text}, finish_reason=None)]) for text in ["Hello", " world"]]
    chunks.append(dict(choices=[dict(delta={}, finish_reason="stop")], usage={"total_tokens": 8}))
    stream = ": heartbeat\n\n" + "".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n"
    gateway = Gateway(httpx.MockTransport(lambda request: httpx.Response(200, text=stream, headers={"content-type": "text/event-stream"})))
    deltas = []
    async def delta(text):
        deltas.append(text)
    result = await gateway.complete(profile(streaming=True, auth="none"), [], delta)
    assert deltas == ["Hello", " world"]
    assert result.text == "Hello world" and result.usage["total_tokens"] == 8


@pytest.mark.parametrize("status,kind", [(401,"invalid_key"),(403,"forbidden"),(404,"not_found"),(429,"rate_limited"),(500,"provider_error"),(302,"provider_error")])
async def test_error_classification_and_redaction(status, kind):
    gateway = Gateway(httpx.MockTransport(lambda request: httpx.Response(status, json={"error": "secret-do-not-echo"})))
    with pytest.raises(ProviderError) as caught:
        await gateway.complete(profile(auth="none", max_retries=0), [])
    assert caught.value.kind == kind
    assert "secret-do-not-echo" not in str(caught.value)


async def test_retry_429_bounded():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"retry-after": "0"}) if len(calls) == 1 else httpx.Response(200, json=response())
    assert (await Gateway(httpx.MockTransport(handler)).complete(profile(auth="none"), [])).text == "Hello"
    assert len(calls) == 2


async def test_long_retry_after_is_not_retried_early():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"retry-after": "120"})
    with pytest.raises(ProviderError) as caught:
        await Gateway(httpx.MockTransport(handler)).complete(profile(auth="none", max_retries=2), [])
    assert caught.value.kind == "rate_limited" and len(calls) == 1


async def test_streaming_byte_limit_applies_without_line_breaks():
    class HugeLine(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(3):
                yield b"x" * 800_000
    gateway = Gateway(httpx.MockTransport(lambda request: httpx.Response(200, stream=HugeLine(), headers={"content-type":"text/event-stream"})))
    with pytest.raises(ProviderError) as caught:
        await gateway.complete(profile(auth="none", streaming=True), [])
    assert caught.value.kind == "response_limit"


async def test_auth_failure_is_not_retried():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(401)
    with pytest.raises(ProviderError):
        await Gateway(httpx.MockTransport(handler)).complete(profile(auth="none", max_retries=2), [])
    assert len(calls) == 1


async def test_connection_and_timeout_errors_are_safe():
    for error, kind in [(httpx.ConnectError("secret"), "connection"), (httpx.ReadTimeout("secret"), "timeout")]:
        def handler(request):
            raise error
        with pytest.raises(ProviderError) as caught:
            await Gateway(httpx.MockTransport(handler)).complete(profile(auth="none"), [])
        assert caught.value.kind == kind and "secret" not in str(caught.value)


@pytest.mark.parametrize("payload", [{}, {"choices": []}, {"choices": [{"message": {"content": []}}]}])
async def test_malformed_response(payload):
    gateway = Gateway(httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    with pytest.raises(ProviderError):
        await gateway.complete(profile(auth="none"), [])


async def test_tool_request_never_executes():
    payload = {"choices": [{"message": {"content": None, "tool_calls": [{"function": {"name": "shell", "arguments": "anything"}}]}, "finish_reason": "tool_calls"}]}
    gateway = Gateway(httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    with pytest.raises(ProviderError, match="not enabled"):
        await gateway.complete(profile(auth="none"), [])


async def test_interrupted_stream_is_not_completed():
    payload = 'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
    gateway = Gateway(httpx.MockTransport(lambda request: httpx.Response(200, text=payload, headers={"content-type":"text/event-stream"})))
    with pytest.raises(ProviderError) as caught:
        await gateway.complete(profile(auth="none", streaming=True), [])
    assert caught.value.kind == "interrupted"


def test_config_round_trip_and_environment_path(tmp_path, monkeypatch):
    path = tmp_path / "settings.yaml"
    monkeypatch.setenv("ELIOT_CONFIG", str(path))
    settings = Settings()
    settings.save_provider(profile())
    settings.save_provider(profile(id="two"))
    settings.select_default("two")
    loaded = Settings()
    assert loaded.path == path and loaded.default_provider == "two"
    assert len(loaded.providers) == 2
    assert "api_key:" not in path.read_text()
    loaded.delete_provider("two")
    assert Settings().default_provider == "one"


@pytest.mark.parametrize("changes", [dict(base_url="http://public.example/v1"), dict(base_url="https://user:secret@example.com/v1"), dict(base_url="https://example.com/v1?key=secret"), dict(parameters={"messages": []}), dict(parameters={"max_tokens": 3, "max_completion_tokens": 4}), dict(max_retries=10), dict(id="bad/id")])
def test_invalid_provider(changes):
    with pytest.raises(ConfigError):
        profile(**changes)


def test_bad_yaml_and_legacy_config_have_clear_errors(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("[broken")
    with pytest.raises(ConfigError, match="YAML"):
        Settings(path)
    path.write_text("llm: {}")
    with pytest.raises(ConfigError, match="Legacy"):
        Settings(path)
