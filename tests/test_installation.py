"""Installer failure/preservation contracts and offline readiness checks."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from eliot_app.diagnostics import diagnose

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eliot_installer", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def test_diagnostics_no_provider_required_and_no_user_database_opened(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\nproviders: []\ndatabase_path: saved.db\n")
    database = tmp_path / "saved.db"
    database.write_bytes(b"existing user database must not be opened or migrated")
    monkeypatch.setattr("eliot_app.diagnostics.shutil.which", lambda name: "/usr/bin/nmap")
    report = diagnose(config, require_nmap=True)
    assert report["ready"] and report["provider_requests"] == 0
    assert next(c for c in report["checks"] if c["name"] == "provider")["status"] == "warning"
    assert database.read_bytes() == b"existing user database must not be opened or migrated"
    assert not list(tmp_path.glob(".eliot-check-*"))


def test_diagnostics_detect_missing_tool_and_modified_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr("eliot_app.diagnostics.shutil.which", lambda name: None)
    assert diagnose(tmp_path / "config.yaml")["ready"]
    assert not diagnose(tmp_path / "config.yaml", require_nmap=True)["ready"]
    from eliot_app.instructions import SkillCatalog
    catalog = SkillCatalog()
    # Alter a manifest expectation in memory, never the vendored files.
    first = next(iter(catalog.manifest["files"]))
    catalog.manifest["files"][first] = "0" * 64
    monkeypatch.setattr("eliot_app.diagnostics.SkillCatalog", lambda: catalog)
    report = diagnose(tmp_path / "config.yaml")
    assert not report["ready"]
    assert next(c for c in report["checks"] if c["name"] == "skills")["status"] == "error"


def test_doctor_strict_machine_readable_failure(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("llm: old-format\n")
    result = subprocess.run([sys.executable, "-m", "eliot_app", "--config", str(config), "doctor", "--strict", "--json"],
                            capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert not report["ready"]
    assert next(c for c in report["checks"] if c["name"] == "configuration")["status"] == "error"


def test_failed_upgrade_preserves_pointer_launcher_config_and_data(tmp_path, monkeypatch):
    prefix = tmp_path / "installation with spaces"
    data, config_dir, bin_dir = installer.locations(prefix)
    for path in (data, config_dir, bin_dir):
        path.mkdir(parents=True)
    pointer = data / "installation.json"
    pointer.write_text('{"runtime":"previous-runtime"}')
    config = config_dir / "config.yaml"
    config.write_text("keep-provider-config")
    database = data / "eliot.db"
    database.write_bytes(b"saved work")
    launcher = bin_dir / "eliot"
    launcher.write_text("old-launcher")
    calls = []

    def fail_on_diagnostics(arguments):
        calls.append(arguments)
        if "doctor" in arguments:
            raise subprocess.CalledProcessError(1, arguments)
    monkeypatch.setattr(installer, "run", fail_on_diagnostics)
    with pytest.raises(subprocess.CalledProcessError):
        installer.install(prefix, no_desktop=True)
    assert len(calls) == 3  # Fresh venv, install, offline verification before activation.
    assert pointer.read_text() == '{"runtime":"previous-runtime"}'
    assert launcher.read_text() == "old-launcher"
    assert config.read_text() == "keep-provider-config" and database.read_bytes() == b"saved work"
    assert not (data / "install.lock").exists()


def test_reinstall_preserves_config_and_database_and_sets_previous_runtime(tmp_path, monkeypatch):
    prefix = tmp_path / "installation with spaces"
    monkeypatch.setattr(installer, "run", lambda arguments: None)
    first = installer.install(prefix, no_desktop=True)
    config = Path(first["config"])
    original_config = config.read_bytes()
    database = config.parent.parent / "data/eliot.db"
    database.write_bytes(b"saved tasks")
    second = installer.install(prefix, no_desktop=True)
    assert second["previous_runtime"] == first["runtime"]
    assert second["runtime"] != first["runtime"]
    assert json.loads((database.parent / "installation.json").read_text())["runtime"] == second["runtime"]
    assert config.read_bytes() == original_config and database.read_bytes() == b"saved tasks"


def test_concurrent_install_is_rejected_without_releasing_owner_lock(tmp_path):
    with installer.install_lock(tmp_path):
        with pytest.raises(RuntimeError, match="Another installation"):
            with installer.install_lock(tmp_path):
                pytest.fail("second installer acquired lock")
        assert (tmp_path / "install.lock").exists()
    assert not (tmp_path / "install.lock").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX launcher contract")
def test_launcher_handles_shell_characters_and_defaults_to_serve(tmp_path, monkeypatch):
    import os
    data = tmp_path / "data ' $literal ; spaces"
    bin_dir = tmp_path / "bin"
    data.mkdir()
    config = data / "config.yaml"
    fake_python = data / "fake-python"
    output = data / "arguments.json"
    fake_python.write_text(f"#!{sys.executable}\nimport json, os, sys\nfrom pathlib import Path\nPath({str(output)!r}).write_text(json.dumps([sys.argv[1:], os.environ['ELIOT_CONFIG']]))\n")
    fake_python.chmod(0o755)
    installer.atomic_write(data / "installation.json", json.dumps({"python": str(fake_python), "config": str(config)}))
    monkeypatch.delenv("ELIOT_CONFIG", raising=False)
    launcher = installer.write_launchers(data, bin_dir)
    subprocess.run([str(launcher)], check=True, cwd=tmp_path)
    assert json.loads(output.read_text()) == [["-I", "-m", "eliot_app", "serve"], str(config)]
    subprocess.run([str(launcher), "chat", "--session", "literal $ ; value"], check=True, cwd=tmp_path)
    assert json.loads(output.read_text())[0][-1] == "literal $ ; value"
    os.environ["ELIOT_CONFIG"] = str(data / "override.yaml")
    try:
        subprocess.run([str(launcher), "doctor"], check=True)
        assert json.loads(output.read_text())[1] == str(data / "override.yaml")
    finally:
        os.environ.pop("ELIOT_CONFIG", None)
