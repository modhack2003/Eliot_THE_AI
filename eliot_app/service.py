"""One run lifecycle for browser and terminal clients."""
from __future__ import annotations

import asyncio

from .config import ConfigError, Settings
from .gateway import Gateway, ProviderError
from .store import Store
from .instructions import CORE_SYSTEM
from .mission_store import MissionStore


SYSTEM = CORE_SYSTEM + "\nConversation mode has no execution tools. Start a durable task to act; do not claim to run tools in conversation mode."


class Service:
    def __init__(self, settings: Settings, gateway: Gateway | None = None):
        self.settings = settings
        self.store = Store(settings.database_path)
        self.persona_store = MissionStore(self.store)
        self.gateway = gateway or Gateway()
        self.tasks: dict[str, asyncio.Task] = {}

    def provider(self, provider_id=None):
        key = provider_id or self.settings.default_provider
        if key not in self.settings.providers:
            raise ConfigError("Add a provider in Providers before starting a conversation.")
        return self.settings.providers[key]

    def providers(self):
        from dataclasses import asdict
        return [{**asdict(p), "key_configured": self.gateway.has_key(p), "temporary_key": p.id in self.gateway.runtime_keys, "is_default": p.id == self.settings.default_provider} for p in self.settings.providers.values()]

    def start(self, session_id, content, provider_id=None, persona_id="eliot"):
        provider = self.provider(provider_id)
        persona = self.persona_store.persona(persona_id)
        if not self.gateway.has_key(provider):
            raise ConfigError(f"Set {provider.api_key_env} or supply a temporary key in Providers.")
        run = self.store.begin_run(session_id, provider, content)
        task = asyncio.create_task(self._execute(run, provider, persona))
        self.tasks[run["id"]] = task
        task.add_done_callback(lambda done: self.tasks.pop(run["id"], None))
        return run

    async def _execute(self, run, provider, persona):
        text = ""
        async def delta(part):
            nonlocal text
            text += part
            self.store.update(run["id"], "running", text)
        try:
            self.store.update(run["id"], "running")
            import json
            messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Subordinate persona data: " + json.dumps(persona)}, *self.store.history(run["session_id"], run["id"])]
            # A total deadline also bounds retry sleeps and stalled event streams.
            async with asyncio.timeout(min(600, provider.timeout_seconds * (provider.max_retries + 1) + 20)):
                result = await self.gateway.complete(provider, messages, delta)
            self.store.update(run["id"], "completed", result.text, finish_reason=result.finish_reason, usage=result.usage)
        except asyncio.CancelledError:
            self.store.update(run["id"], "cancelled", text, error="Response stopped. The provider may still bill work already performed.", error_kind="cancelled")
        except TimeoutError:
            self.store.update(run["id"], "failed", text, error="The response exceeded the total time limit.", error_kind="timeout")
        except ProviderError as error:
            self.store.update(run["id"], "failed", text, error=str(error), error_kind=error.kind)
        except Exception:
            self.store.update(run["id"], "failed", text, error="The response could not be completed. Check the backend and provider configuration.", error_kind="internal")

    async def cancel(self, run_id):
        run = self.store.run(run_id)
        task = self.tasks.get(run_id)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            # A task cancelled before its coroutine starts cannot write its state.
            if self.store.run(run_id)["status"] in {"queued", "running"}:
                self.store.update(run_id, "cancelled", run["text"], error="Response stopped.", error_kind="cancelled")
        return self.store.run(run_id)

    async def close(self):
        for run_id in list(self.tasks):
            await self.cancel(run_id)

