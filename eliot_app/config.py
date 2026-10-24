"""Validated configuration; secrets are references, never YAML values."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

import yaml


class ConfigError(ValueError):
    pass


def loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    base_url: str
    model: str
    api_key_env: str = "ELIOT_API_KEY"
    auth: str = "bearer"
    streaming: bool = True
    timeout_seconds: float = 60
    max_retries: int = 1
    parameters: dict = field(default_factory=dict)

    def __post_init__(self):
        if any(not isinstance(value, str) for value in (self.id, self.name, self.base_url, self.model, self.api_key_env, self.auth)):
            raise ConfigError("Provider identity, endpoint, model and authentication fields must be text.")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", self.id):
            raise ConfigError("Provider ID must contain 1–64 letters, digits, underscores or hyphens.")
        if not self.name.strip() or len(self.name) > 120:
            raise ConfigError("Enter a provider name of up to 120 characters.")
        try:
            url = urlsplit(self.base_url)
            url.port
        except ValueError:
            raise ConfigError("The endpoint URL or port is invalid.") from None
        if not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ConfigError("Use an endpoint URL without credentials, query parameters or fragments.")
        if url.scheme not in {"http", "https"} or (url.scheme == "http" and not loopback(url.hostname)):
            raise ConfigError("Remote endpoints require HTTPS. HTTP is supported for loopback model servers.")
        if not self.model.strip() or len(self.model) > 200:
            raise ConfigError("Enter the exact model ID from your provider.")
        if len(self.base_url) > 2048:
            raise ConfigError("The endpoint URL is too long.")
        if self.auth not in {"bearer", "none"}:
            raise ConfigError("Authentication must be bearer or none.")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.api_key_env):
            raise ConfigError("Enter a valid environment variable name for the API key.")
        if type(self.streaming) is not bool:
            raise ConfigError("Streaming must be true or false.")
        if type(self.timeout_seconds) not in {int, float} or not 1 <= self.timeout_seconds <= 300:
            raise ConfigError("Request timeout must be between 1 and 300 seconds.")
        if type(self.max_retries) is not int or not 0 <= self.max_retries <= 2:
            raise ConfigError("Retries must be between 0 and 2.")
        # Explicit generation controls cover ordinary compatible chat servers.
        allowed = {"temperature", "top_p", "max_tokens", "max_completion_tokens", "seed", "presence_penalty", "frequency_penalty", "reasoning_effort"}
        if not isinstance(self.parameters, dict) or set(self.parameters) - allowed:
            raise ConfigError("Unsupported generation parameter. See config.example.yaml.")
        if "max_tokens" in self.parameters and "max_completion_tokens" in self.parameters:
            raise ConfigError("Choose one token-limit parameter supported by your model.")
        try:
            json.dumps(self.parameters, allow_nan=False)
        except (TypeError, ValueError):
            raise ConfigError("Generation parameters must contain valid JSON values.") from None


class Settings:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.getenv("ELIOT_CONFIG") or os.getenv("CONFIG_FILE") or "config.yaml").resolve()
        self.providers: dict[str, Provider] = {}
        self.default_provider: str | None = None
        self.database_path = self.path.parent / "data" / "eliot.db"
        self.load()

    def load(self):
        if not self.path.exists():
            return
        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            raise ConfigError("Configuration is not valid YAML.") from None
        if not isinstance(raw, dict) or raw.get("version") != 1:
            raise ConfigError("Use a version: 1 remaster config. Legacy config.yaml is not compatible; see config.example.yaml.")
        try:
            profiles = raw.get("providers", [])
            if not isinstance(profiles, list):
                raise ConfigError("providers must be a list of profiles.")
            parsed = [Provider(**profile) for profile in profiles]
            self.providers = {p.id: p for p in parsed}
            if len(parsed) != len(self.providers):
                raise ConfigError("Provider IDs must be unique.")
            self.default_provider = raw.get("default_provider") or next(iter(self.providers), None)
            if self.default_provider and self.default_provider not in self.providers:
                raise ConfigError("The default provider does not exist.")
            db = raw.get("database_path", "data/eliot.db")
            self.database_path = (self.path.parent / db).resolve()
        except (TypeError, KeyError, ValueError) as error:
            if isinstance(error, ConfigError):
                raise
            raise ConfigError("Invalid provider configuration. Check the fields in config.example.yaml.") from None

    def save_provider(self, provider: Provider):
        providers = {**self.providers, provider.id: provider}
        default = self.default_provider or provider.id
        self._save(providers, default)

    def select_default(self, provider_id: str):
        if provider_id not in self.providers:
            raise ConfigError("Provider not found.")
        self._save(self.providers, provider_id)

    def delete_provider(self, provider_id: str):
        if provider_id not in self.providers:
            raise ConfigError("Provider not found.")
        providers = {key: value for key, value in self.providers.items() if key != provider_id}
        default = self.default_provider if self.default_provider in providers else next(iter(providers), None)
        self._save(providers, default)

    def _save(self, providers, default):
        raw = {"version": 1, "default_provider": default, "database_path": str(self.database_path), "providers": [asdict(p) for p in providers.values()]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".eliot-config-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.safe_dump(raw, handle, sort_keys=False)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.providers = dict(providers)
        self.default_provider = default

