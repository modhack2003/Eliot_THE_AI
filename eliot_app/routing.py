"""Opt-in routing among operator-approved providers using recorded measurements."""

from .config import ConfigError


def performance(store):
    groups = {}
    with store.store.connection() as db:
        rows = db.execute(
            "SELECT e.data,m.status FROM mission_events e JOIN missions m ON m.id=e.mission_id WHERE e.kind='model_usage' ORDER BY e.id DESC LIMIT 10000"
        )
        import json

        for row in rows:
            event = json.loads(row["data"])
            key = event["provider_id"]
            bucket = groups.setdefault(
                key,
                {
                    "provider_id": key,
                    "calls": 0,
                    "seconds": 0,
                    "cost_usd": 0,
                    "priced_calls": 0,
                    "completed_task_calls": 0,
                },
            )
            bucket["calls"] += 1
            bucket["seconds"] += event.get("seconds", 0)
            if event.get("cost_usd") is not None:
                bucket["cost_usd"] += event["cost_usd"]
                bucket["priced_calls"] += 1
            bucket["completed_task_calls"] += int(row["status"] == "completed")
    for bucket in groups.values():
        bucket["average_seconds"] = bucket["seconds"] / bucket["calls"]
        bucket["completion_proxy"] = bucket["completed_task_calls"] / bucket["calls"]
        bucket["quality_note"] = (
            "Completion is an operational proxy, not a measured finding-accuracy score."
        )
    return list(groups.values())


def choose(service, store, approved, mode, fallback):
    if mode == "fixed":
        return service.provider(fallback)
    if not approved:
        raise ConfigError(
            "Automatic routing requires an explicit approved provider list."
        )
    candidates = [service.provider(identifier) for identifier in approved]
    candidates = [
        provider for provider in candidates if service.gateway.has_key(provider)
    ]
    if not candidates:
        raise ConfigError("No approved routed provider has usable credentials.")
    measured = {item["provider_id"]: item for item in performance(store)}
    if mode == "lowest_cost":
        priced = [
            provider
            for provider in candidates
            if provider.input_cost_per_million is not None
            and provider.output_cost_per_million is not None
        ]
        if not priced:
            raise ConfigError(
                "Lowest-cost routing requires configured input/output prices."
            )
        return min(
            priced,
            key=lambda provider: (
                provider.input_cost_per_million + provider.output_cost_per_million
            ),
        )
    sampled = [
        provider
        for provider in candidates
        if measured.get(provider.id, {}).get("calls", 0) >= 5
    ]
    if not sampled:
        return next((p for p in candidates if p.id == fallback), candidates[0])
    if mode == "fastest":
        return min(
            sampled, key=lambda provider: measured[provider.id]["average_seconds"]
        )
    if mode == "highest_completion":
        return max(
            sampled, key=lambda provider: measured[provider.id]["completion_proxy"]
        )
    raise ConfigError("Unknown routing mode.")
