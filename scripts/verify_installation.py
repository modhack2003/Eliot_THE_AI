"""Smoke-test a real installation from outside the source tree; stdlib only."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.error import URLError
from urllib.request import build_opener, ProxyHandler


def verify(prefix):
    state = json.loads((Path(prefix) / "data/installation.json").read_text(encoding="utf-8"))
    command = [state["python"], "-I", "-m", "eliot_app", "--config", state["config"]]
    with tempfile.TemporaryDirectory(prefix="eliot-smoke-") as outside:
        launcher = Path(prefix).resolve() / "bin" / ("eliot.cmd" if os.name == "nt" else "eliot")
        launched = subprocess.run([str(launcher), "--version"], cwd=outside, check=True, capture_output=True, text=True)
        assert launched.stdout.strip() == state["version"], launched.stderr
        result = subprocess.run([*command, "doctor", "--json", "--strict"], cwd=outside, check=True, capture_output=True, text=True)
        assert json.loads(result.stdout)["ready"]
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        log = Path(outside) / "backend.log"
        with log.open("w+") as stream:
            process = subprocess.Popen([*command, "serve", "--port", str(port)], cwd=outside, stdout=stream, stderr=stream)
            try:
                opener = build_opener(ProxyHandler({}))
                url = f"http://127.0.0.1:{port}"
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("Backend exited: " + log.read_text())
                    try:
                        with opener.open(url + "/api/bootstrap", timeout=1) as response:
                            bootstrap = json.load(response)
                        break
                    except (URLError, TimeoutError):
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Backend did not become ready: " + log.read_text())
                assert bootstrap["version"] == state["version"]
                for resource in ("/", "/static/app.js", "/static/style.css", "/static/workspace.js", "/static/neural.js"):
                    with opener.open(url + resource, timeout=3) as response:
                        assert response.status == 200 and response.read()
                with opener.open(url + "/api/skills", timeout=3) as response:
                    assert len(json.load(response)) == 83
                with opener.open(url + "/api/tasks", timeout=3) as response:
                    assert isinstance(json.load(response), list)
                print("Installed runtime: web assets, API, 83 skills and task database passed; no provider requests or scans.")
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix")
    verify(parser.parse_args().prefix)
