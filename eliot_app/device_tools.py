"""Optional browser, desktop, image and robotics adapters on the host."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field
from .config import ConfigError


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BrowserAction(Input):
    action: Literal[
        "navigate", "inspect", "click", "fill", "press", "screenshot", "close"
    ]
    url: str = Field(default="", max_length=2048)
    selector: str = Field(default="", max_length=1000)
    text: str = Field(default="", max_length=12000)


class DesktopAction(Input):
    action: Literal["screenshot", "click", "type", "press", "scroll"]
    x: int = Field(default=0, ge=0, le=20000)
    y: int = Field(default=0, ge=0, le=20000)
    text: str = Field(default="", max_length=12000)
    key: str = Field(default="", max_length=50)
    amount: int = Field(default=0, ge=-100, le=100)


class InspectImage(Input):
    path: str


class RobotAction(Input):
    action: Literal["status", "command", "emergency_stop"]
    command: dict = Field(default_factory=dict)


MODELS = {
    "browser_action": BrowserAction,
    "desktop_action": DesktopAction,
    "inspect_image": InspectImage,
    "robot_action": RobotAction,
}
DESCRIPTIONS = {
    "browser_action": "Control a persistent Chromium browser on the host: navigate, inspect visible text/controls, click, fill, press, screenshot or close. Requests must stay inside the mission network scope.",
    "desktop_action": "Control the logged-in host desktop or capture its screenshot. Requires desktop permission. PyAutoGUI failsafe is enabled.",
    "inspect_image": "Attach a PNG/JPEG workspace or task-artifact image to the next vision-capable model request. Returns metadata; text-only models cannot inspect image contents.",
    "robot_action": "Call the explicitly configured robotics bridge /status, /command or /emergency-stop. Command limits and independent physical emergency stopping belong to the bridge/controller.",
}


def allowed(mission, name):
    if name == "browser_action":
        return mission["policy"].get("browser", False) and mission["policy"]["network"]
    if name == "desktop_action":
        return mission["policy"].get("desktop", False)
    if name == "robot_action":
        return mission["policy"].get("robotics", False)
    return True


def binary_artifact(tools, mission, raw, suffix):
    name = f"captures/{uuid4().hex}.{suffix}"
    path = tools.artifact_path(mission, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tools.artifact_path(mission, name)
    from .filesystem import write_artifact

    write_artifact(
        Path(mission["workspace"]), path.relative_to(mission["workspace"]), raw
    )
    return {
        "image_path": str(path.relative_to(mission["workspace"])),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "provenance": "host_visual_observation",
    }


def image_path(tools, mission, path):
    supplied = Path(path)
    if supplied.parts and supplied.parts[0] == ".eliot-artifacts":
        owners = (
            {member["id"] for member in tools.mission_store.list(mission["root_id"])}
            if tools.mission_store
            else {mission["id"]}
        )
        if len(supplied.parts) < 3 or supplied.parts[1] not in owners:
            raise ConfigError("Image does not belong to this task graph.")
        target = tools.artifact_path(
            mission, Path(*supplied.parts[2:]), supplied.parts[1]
        )
    else:
        target = tools.path(mission, path)
    if not target.is_file() or target.stat().st_size > 2000000:
        raise ConfigError("Choose a PNG/JPEG image smaller than 2 MB.")
    raw = target.read_bytes()
    mime = (
        "image/png"
        if raw.startswith(b"\x89PNG\r\n\x1a\n")
        else "image/jpeg"
        if raw.startswith(b"\xff\xd8\xff")
        else None
    )
    if not mime:
        raise ConfigError("Only PNG and JPEG images are supported.")
    return target, raw, mime


class DeviceTools:
    def __init__(self, tools):
        self.tools = tools
        self.sessions = {}
        self.locks = {}
        self.desktop_lock = asyncio.Lock()

    async def execute(self, mission, name, args):
        if not allowed(mission, name):
            raise ConfigError("This device capability is not enabled for the mission.")
        if name == "inspect_image":
            _, raw, mime = image_path(self.tools, mission, args["path"])
            return {
                "image_path": args["path"],
                "mime_type": mime,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "requires_vision_model": True,
            }
        if name == "browser_action":
            async with self.locks.setdefault(mission["root_id"], asyncio.Lock()):
                async with asyncio.timeout(mission["policy"].get("tool_timeout", 60)):
                    return await self.browser(mission, **args)
        if name == "desktop_action":
            async with self.desktop_lock:
                # These short host interactions settle before acknowledging stop.
                return await asyncio.to_thread(self.desktop, mission, **args)
        if name == "robot_action":
            return await self.robot(mission, **args)
        raise ConfigError("Device adapter unavailable.")

    def check_url(self, mission, url):
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ConfigError(
                "Use an HTTP(S) browser URL without embedded credentials."
            )
        self.tools.scoped(
            mission,
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            parsed.path or "/",
        )

    async def browser(self, mission, action, url="", selector="", text=""):
        if importlib.util.find_spec("playwright") is None:
            raise ConfigError(
                "Install the browser extra and run: python -m playwright install chromium"
            )
        from playwright.async_api import async_playwright

        key = mission["root_id"]
        if action == "close":
            await self.close_one(key)
            return {"closed": True}
        session = self.sessions.get(key)
        if not session:
            engine = await async_playwright().start()
            data = (
                self.tools.mission_store.store.path.parent
                if self.tools.mission_store
                else Path(mission["workspace"]) / ".eliot-browser"
            )
            profile = data / "browser-profiles" / key
            profile.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                context = await engine.chromium.launch_persistent_context(
                    str(profile),
                    headless=True,
                    executable_path=shutil.which("chromium")
                    or shutil.which("google-chrome"),
                    accept_downloads=False,
                    service_workers="block",
                )
            except BaseException:
                await engine.stop()
                raise
            context.set_default_timeout(15000)

            async def route(request_route):
                try:
                    self.check_url(mission, request_route.request.url)
                except ConfigError:
                    await request_route.abort()
                    return
                await request_route.continue_()

            await context.route("**/*", route)
            page = context.pages[0] if context.pages else await context.new_page()
            session = (engine, context, page)
            self.sessions[key] = session
        engine, context, page = session
        if action == "navigate":
            self.check_url(mission, url)
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        else:
            self.check_url(mission, page.url)
            if action in {"click", "fill", "press"}:
                if not selector:
                    raise ConfigError("Supply a locator selector.")
                locator = page.locator(selector)
                if action == "click":
                    await locator.click()
                elif action == "fill":
                    await locator.fill(text)
                else:
                    await locator.press(text)
        self.check_url(mission, page.url)
        if action == "screenshot":
            return binary_artifact(
                self.tools,
                mission,
                await page.screenshot(type="jpeg", quality=70, full_page=False),
                "jpg",
            )
        controls = await page.locator("a,button,input,select,textarea").evaluate_all(
            '(items) => items.slice(0,80).map(e => ({tag:e.tagName,role:e.getAttribute("role"),name:(e.getAttribute("aria-label")||e.getAttribute("name")||e.innerText||"").slice(0,200),id:e.id,type:e.getAttribute("type")}))'
        )
        return {
            "url": page.url,
            "title": await page.title(),
            "text": (await page.locator("body").inner_text())[:12000],
            "controls": controls,
            "provenance": "browser_dom_observation",
            "execution": "direct_host",
        }

    def desktop(self, mission, action, x=0, y=0, text="", key="", amount=0):
        try:
            import pyautogui
        except ImportError:
            raise ConfigError(
                "Install the desktop extra to use the host desktop."
            ) from None
        pyautogui.FAILSAFE = True
        if action == "screenshot":
            import io

            buffer = io.BytesIO()
            pyautogui.screenshot().convert("RGB").save(
                buffer, format="JPEG", quality=65
            )
            return binary_artifact(self.tools, mission, buffer.getvalue(), "jpg")
        if action == "click":
            pyautogui.click(x, y)
        elif action == "type":
            pyautogui.write(text, interval=0.01)
        elif action == "press":
            if key not in pyautogui.KEYBOARD_KEYS:
                raise ConfigError("Unknown desktop key.")
            pyautogui.press(key)
        elif action == "scroll":
            pyautogui.scroll(amount)
        return {
            "action": action,
            "performed": True,
            "verification_required": "Capture and inspect the resulting desktop state.",
            "execution": "direct_host",
        }

    async def robot(self, mission, action, command):
        base = mission["policy"].get("robot_url")
        if not base:
            raise ConfigError("Configure the robotics bridge URL for this mission.")
        endpoint = {
            "status": "status",
            "command": "command",
            "emergency_stop": "emergency-stop",
        }[action]
        self.check_url(mission, base.rstrip("/") + "/" + endpoint)
        async with (
            asyncio.timeout(10),
            httpx.AsyncClient(
                timeout=8,
                follow_redirects=False,
                trust_env=False,
                transport=self.tools.http_transport,
            ) as client,
        ):
            request = client.build_request(
                "GET" if action == "status" else "POST",
                base.rstrip("/") + "/" + endpoint,
                json=None
                if action == "status"
                else {"command": command}
                if action == "command"
                else {},
            )
            async with client.stream(
                request.method,
                request.url,
                headers=request.headers,
                content=request.content,
            ) as response:
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 64000:
                        raise ConfigError("Robotics bridge response is too large.")
                if response.status_code >= 300:
                    raise ConfigError("Robotics bridge rejected the action.")
                return {
                    "action": action,
                    "response": json.loads(raw),
                    "provenance": "robot_bridge_response",
                    "physical_state_verified": False,
                }

    async def close_one(self, key):
        session = self.sessions.pop(key, None)
        if session:
            engine, context, _ = session
            try:
                await context.close()
            finally:
                await engine.stop()

    async def close(self):
        for key in list(self.sessions):
            await self.close_one(key)
