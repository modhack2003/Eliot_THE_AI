"""Offline installation checks. No provider requests or target scans."""
from __future__ import annotations

import hashlib
import importlib
from contextlib import closing
from importlib.metadata import version
from pathlib import Path
import platform
import shutil
import sqlite3
import sys
import tempfile

from . import __version__
from .config import Settings
from .instructions import SkillCatalog


def diagnose(config=None, require_nmap=False):
    checks = []

    def check(name, operation, required=True):
        try:
            detail = operation()
            checks.append({"name": name, "status": "ok", "detail": str(detail)})
        except Exception as error:
            checks.append({"name": name, "status": "error" if required else "warning", "detail": str(error)})

    def python_check():
        if sys.version_info < (3, 11):
            raise ValueError("Python 3.11 or newer is required.")
        return platform.python_version()

    check("python", python_check)
    for name in ("fastapi", "pydantic", "uvicorn", "httpx", "PyYAML"):
        def dependency(name=name):
            importlib.import_module("yaml" if name == "PyYAML" else name)
            return version(name)
        check(name, dependency)
    settings = None

    def configuration():
        nonlocal settings
        settings = Settings(config)
        return settings.path

    check("configuration", configuration)
    if settings is not None:
        def storage():
            # Use a disposable database, never migrate/open the user's database here.
            settings.database_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".eliot-check-", dir=settings.database_path.parent) as folder:
                with closing(sqlite3.connect(str(Path(folder) / "probe.db"))) as db:
                    db.execute("CREATE TABLE probe (value TEXT)")
                    db.execute("INSERT INTO probe VALUES ('ok')")
                    if db.execute("SELECT value FROM probe").fetchone()[0] != "ok":
                        raise ValueError("SQLite read/write failed.")
            return settings.database_path.parent
        check("storage", storage)
        checks.append({"name": "provider", "status": "ok" if settings.providers else "warning",
                       "detail": f"{len(settings.providers)} configured; connection not tested" if settings.providers
                       else "Connect your API endpoint, model and key in the web interface."})

    def assets():
        for name in ("index.html", "style.css", "app.js", "workspace.js", "neural.js", "transport.js"):
            if not (Path(__file__).parent / "static" / name).is_file():
                raise ValueError(f"Missing web asset: {name}")
        return "All browser assets present"
    check("web_assets", assets)

    def skills():
        catalog = SkillCatalog()
        for relative, expected in catalog.manifest["files"].items():
            target = (catalog.root / relative).resolve()
            if not target.is_relative_to(catalog.root.resolve()):
                raise ValueError("Invalid bundle path")
            if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Skill integrity check failed: {relative}")
        return f"{len(catalog.entries)} bundled skills; all pinned file hashes verified"
    check("skills", skills)

    def nmap():
        executable = shutil.which("nmap")
        if not executable:
            raise ValueError("nmap not found. On Kali/Debian/Ubuntu, rerun bash install.sh.")
        return executable
    check("nmap", nmap, required=require_nmap)
    return {"version": __version__, "ready": not any(c["status"] == "error" for c in checks),
            "checks": checks, "provider_requests": 0}
