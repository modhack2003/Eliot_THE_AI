"""Operator-granted mission capabilities. Execution always uses the host directly."""

import time
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .config import ConfigError


class MissionOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    host_execution: bool = False
    file_edit: bool = False
    browser: bool = False
    desktop: bool = False
    robotics: bool = False
    executables: list[str] = Field(default_factory=list, max_length=100)
    ports: list[int] = Field(default_factory=list, max_length=256)
    url_paths: list[str] = Field(default_factory=list, max_length=100)
    expires_at: float | None = Field(default=None, gt=0)
    wall_seconds: int = Field(default=0, ge=0, le=604800)
    cost_budget_usd: float = Field(default=0, ge=0, le=100000)
    max_tool_calls: int = Field(default=0, ge=0)
    tool_timeout: int = Field(default=60, ge=1, le=600)
    max_provider_retries: int = Field(default=6, ge=0, le=100)
    outage_seconds: int = Field(default=900, ge=1, le=86400)
    reviewer_provider_id: str | None = None
    worker_provider_id: str | None = None
    robot_url: str | None = None
    routing_mode: Literal["fixed", "fastest", "lowest_cost", "highest_completion"] = (
        "fixed"
    )
    approved_providers: list[str] = Field(default_factory=list, max_length=20)


def active(policy):
    if policy.get("expires_at") and time.time() >= policy["expires_at"]:
        raise ConfigError("This engagement permission window has expired.")


def network_scope(policy, host, port=None, path=None):
    active(policy)
    if not policy["network"] or host not in policy["targets"]:
        raise ConfigError(
            "Network action denied: this exact host is not enabled in the task scope."
        )
    if policy.get("ports") and port is not None and port not in policy["ports"]:
        raise ConfigError("Network port is not enabled in the task scope.")
    if (
        policy.get("url_paths")
        and path is not None
        and not any(
            path == prefix or path.startswith(prefix.rstrip("/") + "/")
            for prefix in policy["url_paths"]
        )
    ):
        raise ConfigError("URL path is not enabled in the task scope.")
