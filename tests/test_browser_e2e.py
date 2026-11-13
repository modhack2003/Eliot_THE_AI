"""Optional complete UI → API → host effect → verification → UI flow."""

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest


@pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None
    or (
        not (shutil.which("chromium") or shutil.which("google-chrome"))
        and os.environ.get("CI") != "true"
    ),
    reason="Optional Playwright/system Chromium integration dependencies are missing",
)
def test_browser_host_mission_and_schedule(tmp_path):
    from playwright.sync_api import sync_playwright, expect

    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        port = candidate.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    command = [
        sys.executable,
        "-c",
        f"import sys;sys.path.insert(0,'tests');from browser_fixture import app;import uvicorn;uvicorn.run(app,host='127.0.0.1',port={port},access_log=False)",
    ]
    env = {**os.environ, "ELIOT_E2E_DIRECTORY": str(tmp_path)}
    with (tmp_path / "server.log").open("w") as log:
        server = subprocess.Popen(command, env=env, stdout=log, stderr=log)
        try:
            for _ in range(100):
                try:
                    with urlopen(url + "/api/bootstrap", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise AssertionError((tmp_path / "server.log").read_text())
            with sync_playwright() as engine:
                try:
                    browser = engine.chromium.launch(
                        executable_path=shutil.which("chromium")
                        or shutil.which("google-chrome"),
                        headless=True,
                    )
                except Exception as error:
                    if (
                        "socket() failed: Operation not permitted" in str(error)
                        and os.environ.get("CI") != "true"
                    ):
                        pytest.skip(
                            "This execution environment denies Chromium native sockets; the browser flow runs in CI."
                        )
                    raise
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url)
                page.locator("#connect-provider").click()
                page.locator("#p-name").fill("Fixture model")
                page.locator("#p-id").fill("fixture")
                page.locator("#p-url").fill("http://127.0.0.1:9999/v1")
                page.locator("#p-model").fill("fixture-model")
                page.locator("#p-auth").select_option("none")
                page.locator("#save-provider").click()
                page.locator("#provider-dialog").wait_for(state="hidden")
                page.locator("#hero-mission").click()
                page.locator("#m-objective").fill("Create and verify a result file")
                page.locator("#m-workspace").fill(str(tmp_path))
                page.locator("#m-host").evaluate('(e)=>e.closest("details").open=true')
                page.locator("#m-host").check()
                page.locator("#m-check-file").fill("verified.txt")
                page.locator("#m-check-text").fill("completed host task")
                page.locator("#launch-mission").click()
                expect(page.locator("#task-status")).to_have_text(
                    "completed", timeout=30000
                )
                assert (tmp_path / "verified.txt").read_text() == "completed host task"
                assert "Generate result" in page.locator("#task-autonomy").inner_text()
                assert "Verify result" in page.locator("#task-autonomy").inner_text()
                page.get_by_role(
                    "button", name="Schedule this mission", exact=True
                ).click()
                definition = json.loads(
                    page.locator("#schedule-definition").input_value()
                )
                definition.update(name="Daily fixture", next_run=time.time() + 86400)
                page.locator("#schedule-definition").fill(json.dumps(definition))
                page.get_by_role("button", name="Create schedule", exact=True).click()
                page.locator("#schedule-list").get_by_text(
                    "Daily fixture", exact=True
                ).wait_for()
                page.set_viewport_size({"width": 390, "height": 844})
                page.locator("#menu-toggle").click()
                page.locator("#chat-nav").click()
                assert page.locator("#voice-input").is_visible()
                assert not errors, errors
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


@pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None
    or (
        not (shutil.which("chromium") or shutil.which("google-chrome"))
        and os.environ.get("CI") != "true"
    ),
    reason="Optional browser dependencies are missing",
)
async def test_real_host_browser_adapter_inspects_fills_clicks_and_captures(tmp_path):
    import asyncio
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    from test_autonomy import paused

    class Lab(BaseHTTPRequestHandler):
        def do_GET(self):
            raw = b'<html><head><title>Local lab</title></head><body><input id="q"><button id="go" onclick="document.getElementById(\'out\').textContent=document.getElementById(\'q\').value">Apply</button><p id="out">Waiting</p></body></html>'
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    lab = ThreadingHTTPServer(("127.0.0.1", 0), Lab)
    thread = threading.Thread(target=lab.serve_forever, daemon=True)
    thread.start()
    runtime, mission = await paused(
        tmp_path, network=True, targets=["127.0.0.1"], options={"browser": True}
    )
    try:
        try:
            result = await runtime.tools.execute(
                mission,
                "browser_action",
                {"action": "navigate", "url": f"http://127.0.0.1:{lab.server_port}/"},
            )
        except Exception as error:
            if (
                "socket() failed: Operation not permitted" in str(error)
                and os.environ.get("CI") != "true"
            ):
                pytest.skip(
                    "Local Chromium sockets are denied; CI runs this integration."
                )
            raise
        assert result["title"] == "Local lab"
        await runtime.tools.execute(
            mission,
            "browser_action",
            {"action": "fill", "selector": "#q", "text": "Verified browser tool"},
        )
        result = await runtime.tools.execute(
            mission, "browser_action", {"action": "click", "selector": "#go"}
        )
        assert "Verified browser tool" in result["text"]
        image = await runtime.tools.execute(
            mission, "browser_action", {"action": "screenshot"}
        )
        assert (tmp_path / image["image_path"]).is_file()
    finally:
        await runtime.close()
        await asyncio.to_thread(lab.shutdown)
        lab.server_close()
