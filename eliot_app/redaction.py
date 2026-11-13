"""Redact credential-shaped values and configured secrets at model/log boundaries."""

import os
import re

_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+|basic\s+)?)[^\s,;\"\}]+"),
    re.compile(
        r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[\"\x27]?\s*[:=]\s*[\"\x27]?)[^\s\"\x27,;\}]+"
    ),
    re.compile(
        r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----"
    ),
]


def redact(value, secrets=()):
    if isinstance(value, dict):
        return {
            key: item
            if key in {"url", "image_data_url"}
            and isinstance(item, str)
            and item.startswith("data:image/")
            else redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if not isinstance(value, str):
        return value
    for secret in sorted(
        {s for s in secrets if isinstance(s, str) and len(s) >= 6},
        key=len,
        reverse=True,
    ):
        value = value.replace(secret, "[REDACTED]")
    for pattern in _PATTERNS:
        value = pattern.sub(
            lambda m: (m.group(1) if m.lastindex else "") + "[REDACTED]", value
        )
    return value


def configured_secrets(service):
    values = list(getattr(service.gateway, "runtime_keys", {}).values())
    values.extend(
        os.getenv(p.api_key_env, "") for p in service.settings.providers.values()
    )
    return [v for v in values if v]
