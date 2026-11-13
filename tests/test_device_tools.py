import sys
import types

import pytest
from test_autonomy import paused
from eliot_app.config import ConfigError


async def test_browser_navigation_scope_inspection_fill_and_screenshot(
    tmp_path, monkeypatch
):
    import eliot_app.device_tools as module

    runtime, mission = await paused(
        tmp_path, network=True, targets=["lab.example"], options={"browser": True}
    )
    calls = []

    class Locator:
        async def fill(self, text):
            calls.append(("fill", text))

        async def click(self):
            calls.append(("click",))

        async def press(self, text):
            calls.append(("press", text))

        async def evaluate_all(self, code):
            return [{"tag": "INPUT", "id": "q", "name": "Query"}]

        async def inner_text(self):
            return "Visible fixture evidence"

    class Page:
        url = "about:blank"

        async def goto(self, url, **kwargs):
            self.url = url

        def locator(self, selector):
            return Locator()

        async def title(self):
            return "Fixture lab"

        async def screenshot(self, **kwargs):
            return b"\xff\xd8\xfffixture"

    class Context:
        pages = [Page()]

        def set_default_timeout(self, value):
            pass

        async def route(self, *args):
            calls.append(("route",))

        async def close(self):
            calls.append(("close",))

    class Chromium:
        async def launch_persistent_context(self, *args, **kwargs):
            return Context()

    class Engine:
        chromium = Chromium()

        async def start(self):
            return self

        async def stop(self):
            calls.append(("stop",))

    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setitem(
        sys.modules,
        "playwright.async_api",
        types.SimpleNamespace(async_playwright=lambda: Engine()),
    )
    output = await runtime.tools.execute(
        mission, "browser_action", {"action": "navigate", "url": "https://lab.example/"}
    )
    assert output["text"] == "Visible fixture evidence"
    await runtime.tools.execute(
        mission,
        "browser_action",
        {"action": "fill", "selector": "#q", "text": "security"},
    )
    assert ("fill", "security") in calls
    image = await runtime.tools.execute(
        mission, "browser_action", {"action": "screenshot"}
    )
    assert (tmp_path / image["image_path"]).exists()
    with pytest.raises(ConfigError, match="denied"):
        await runtime.tools.execute(
            mission,
            "browser_action",
            {"action": "navigate", "url": "https://outside.example/"},
        )
    await runtime.tools.devices.close()
    assert ("stop",) in calls


async def test_desktop_operations_set_failsafe_and_record_image(tmp_path, monkeypatch):
    runtime, mission = await paused(tmp_path, options={"desktop": True})
    calls = []

    class Image:
        def convert(self, mode):
            return self

        def save(self, buffer, **kwargs):
            buffer.write(b"\xff\xd8\xfffixture")

    fake = types.SimpleNamespace(
        FAILSAFE=False,
        KEYBOARD_KEYS=["enter"],
        screenshot=lambda: Image(),
        click=lambda x, y: calls.append((x, y)),
        write=lambda *a, **kw: None,
        press=lambda key: calls.append(key),
        scroll=lambda amount: None,
    )
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    await runtime.tools.execute(
        mission, "desktop_action", {"action": "click", "x": 20, "y": 30}
    )
    assert fake.FAILSAFE and calls == [(20, 30)]
    output = await runtime.tools.execute(
        mission, "desktop_action", {"action": "screenshot"}
    )
    assert (tmp_path / output["image_path"]).exists()
    with pytest.raises(ConfigError):
        await runtime.tools.execute(
            mission, "desktop_action", {"action": "press", "key": "unknown"}
        )
