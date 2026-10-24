"""User-local installation shared by Linux and Windows launchers (stdlib only)."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import tomllib
import uuid

SOURCE = Path(__file__).resolve().parents[1]


def locations(prefix=None):
    if prefix:
        root = Path(prefix).expanduser().resolve()
        return root / "data", root / "config", root / "bin"
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Eliot"
        return root / "data", root / "config", root / "bin"
    return (Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "eliot",
            Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "eliot",
            Path.home() / ".local/bin")


def atomic_write(path, content, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".eliot-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def install_lock(data):
    lock = data / "install.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError(f"Another installation is active. If it was interrupted, confirm it has stopped, then remove {lock} and retry.") from None
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def runtime_python(runtime):
    return runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(arguments):
    # No shell interpolation; source/install paths can contain spaces.
    subprocess.run([str(arg) for arg in arguments], check=True, cwd=tempfile.gettempdir())


DISPATCH = '''"""Stable launcher: the active runtime pointer changes only after verification."""
import json
import os
from pathlib import Path
import subprocess
import sys

state = json.loads((Path(__file__).parent / "installation.json").read_text(encoding="utf-8"))
os.environ.setdefault("ELIOT_CONFIG", state["config"])
arguments = sys.argv[1:] or ["serve"]
command = [state["python"], "-I", "-m", "eliot_app", *arguments]
if os.name == "nt":
    # Windows execv does not quote argv containing spaces; subprocess does.
    try:
        raise SystemExit(subprocess.call(command))
    except KeyboardInterrupt:
        raise SystemExit(130)
os.execv(command[0], command)
'''


def write_launchers(data, bin_dir):
    dispatch = data / "launch.py"
    atomic_write(dispatch, DISPATCH)
    if os.name == "nt":
        # Avoid cmd expansion/injection for unusual Windows paths.
        if any(c in str(p) for p in (Path(sys.executable), dispatch, bin_dir) for c in '%!\r\n"'):
            raise ValueError('Installation paths cannot contain %, !, quotes or newlines on Windows.')
        content = f'@echo off\n"{sys.executable}" -I "{dispatch}" %*\nexit /b %ERRORLEVEL%\n'
        launcher = bin_dir / "eliot.cmd"
    else:
        content = f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -I {shlex.quote(str(dispatch))} "$@"\n'
        launcher = bin_dir / "eliot"
    atomic_write(launcher, content, 0o755)
    return launcher


def desktop_entry(launcher):
    if os.name == "nt":
        # A double-clickable launcher is enough; no registry or shell profile changes.
        shortcut = Path.home() / "Desktop" / "Eliot.cmd"
        if shortcut.parent.is_dir():
            atomic_write(shortcut, f'@echo off\ncall "{launcher}" %*\n', 0o700)
        return
    applications = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "applications"
    # Desktop Exec has its own quoting rules (not POSIX sh quoting).
    quoted = str(launcher).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    atomic_write(applications / "eliot.desktop", f'''[Desktop Entry]
Version=1.0
Type=Application
Name=Eliot
Comment=Start the local Eliot terminal and web backend
Exec="{quoted}"
Icon=utilities-terminal
Terminal=true
Categories=Network;Security;
''', 0o644)


def install(prefix=None, no_desktop=False):
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required.")
    data, config_home, bin_dir = (p.resolve() for p in locations(prefix))
    for folder in (data, config_home, bin_dir):
        folder.mkdir(parents=True, exist_ok=True, mode=0o755 if folder == bin_dir else 0o700)
    with install_lock(data):
        metadata = tomllib.loads((SOURCE / "pyproject.toml").read_text(encoding="utf-8"))
        release = metadata["project"]["version"]
        runtime = data / "runtimes" / f"{release}-{uuid.uuid4().hex[:12]}"
        python = runtime_python(runtime)
        print(f"Installing Eliot {release} in {runtime}", flush=True)
        # Each attempt has a new final venv path. Relocating a venv breaks its entrypoints.
        # An unsuccessful attempt never changes the active runtime pointer.
        run([sys.executable, "-I", "-m", "venv", runtime])
        run([python, "-I", "-m", "pip", "install", "--disable-pip-version-check", SOURCE])
        config = config_home / "config.yaml"
        if not config.exists():
            # Exclusively create: a concurrent app/config writer must never be overwritten.
            with config.open("x", encoding="utf-8") as stream:
                os.chmod(config, 0o600)
                stream.write("version: 1\nproviders: []\ndefault_provider: null\ndatabase_path: " + json.dumps(str(data / "eliot.db")) + "\n")
        diagnostic = [python, "-I", "-m", "eliot_app", "--config", config, "doctor", "--strict", "--json"]
        if sys.platform.startswith("linux"):
            diagnostic.append("--require-nmap")
        run(diagnostic)
        pointer = data / "installation.json"
        previous = json.loads(pointer.read_text(encoding="utf-8")) if pointer.exists() else {}
        launcher = write_launchers(data, bin_dir)
        state = {"version": release, "python": str(python), "runtime": str(runtime), "config": str(config),
                 "previous_runtime": previous.get("runtime"), "installed_at": datetime.now(timezone.utc).isoformat()}
        atomic_write(pointer, json.dumps(state, indent=2) + "\n")
        if not no_desktop:
            try:
                desktop_entry(launcher)
            except OSError as error:
                print(f"Desktop shortcut was skipped: {error}", file=sys.stderr)
        start_command = "& '" + str(launcher).replace("'", "''") + "'" if os.name == "nt" else shlex.quote(str(launcher))
        print(f"\nEliot is ready. Start it with:\n  {start_command}\nWeb interface: http://127.0.0.1:8765\nConfiguration: {config}")
        if os.name != "nt" and str(bin_dir) not in os.environ.get("PATH", "").split(os.pathsep):
            print(f"For the short eliot command, add {shlex.quote(str(bin_dir))} to PATH or open the Eliot application shortcut.")
        print("Connect your API endpoint, model and key in the web interface. Existing configuration and data were preserved.")
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", help="Keep config, data and launchers below this directory")
    parser.add_argument("--skip-system", action="store_true", help="OS packages were provisioned separately by the administrator")
    parser.add_argument("--no-desktop", action="store_true", help="Do not create an application-menu/desktop shortcut")
    args = parser.parse_args()
    try:
        install(args.prefix, args.no_desktop)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Installation failed: {error}\nThe previously active runtime, if any, is unchanged. Fix the error and rerun the installer.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
