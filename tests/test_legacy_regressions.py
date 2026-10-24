"""Exercise repaired legacy definitions without importing or starting the legacy app."""
import ast
from dataclasses import dataclass
import logging
from pathlib import Path
import sys
import time
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]


def isolated(path, names):
    tree = ast.parse((ROOT / "legacy" / path).read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name in names]
    module = types.ModuleType("legacy_regression_" + path.replace("/", "_").replace(".", "_"))
    sys.modules[module.__name__] = module
    module.__dict__.update(dataclass=dataclass, logging=logging, time=time)
    nodes.insert(0, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), path, "exec"), module.__dict__)
    return module


async def test_legacy_mongo_target_read_accepts_existing_record():
    module = isolated("agent/persistence/database.py", ["Target", "ExperienceDatabase"])
    class Collection:
        async def find_one(self, query):
            return {"_id":"fake-object-id", "ip":"192.0.2.1"}
    database = module.ExperienceDatabase("unused")
    database.db = types.SimpleNamespace(targets=Collection())
    assert (await database.get_target("192.0.2.1")).ip == "192.0.2.1"


async def test_legacy_complete_is_terminal_and_tools_route_is_reachable():
    module = isolated("legacy_main.py", ["ELIOTAssistant"])
    app = module.ELIOTAssistant.__new__(module.ELIOTAssistant)
    app.current_objective = "unused"
    app.continuous_mode = app.pentesting_active = True
    app.session_context = dict(targets=[], vulnerabilities=[], credentials_found=[], exploits_tried=[])
    app._has_working_api_keys = lambda: True
    app.llm_manager = types.SimpleNamespace(generate_text=lambda prompt: types.SimpleNamespace(content="COMPLETE"))
    assert await app._get_next_pentesting_action() is None
    assert not app.continuous_mode and not app.pentesting_active
    app._list_available_tools = lambda: "fixture tool list"
    app._is_continuous_pentesting_request = lambda text: False
    assert await app.process_message("tools") == "fixture tool list"


def test_legacy_key_cooldown_is_respected_after_prior_use():
    module = isolated("legacy_main.py", ["ELIOTAssistant"])
    app = module.ELIOTAssistant.__new__(module.ELIOTAssistant)
    app.llm_manager = types.SimpleNamespace(providers={"gemini":{"api_keys":["fake-key"]}}, api_key_status={"fake-key":types.SimpleNamespace(usage_count=10, is_active=True, rate_limited_until=time.time()+1000)})
    assert app._has_working_api_keys() is False


def test_source_no_longer_embeds_database_credentials():
    import re
    for path in [*ROOT.glob("*.py"), *(ROOT / "legacy").glob("*.py")]:
        assert not re.search(r"mongodb(?:\+srv)?://[^\s'\"]+:[^\s'\"]+@", path.read_text(encoding="utf-8"))
