"""Fail on credential-shaped values in tracked first-party files; never print values."""

import json
import subprocess
import sys

result = subprocess.run(
    [
        sys.executable,
        "-m",
        "detect_secrets",
        "scan",
        "--exclude-files",
        r"(^legacy/|^eliot_app/bundled_skills/)",
    ],
    capture_output=True,
    text=True,
    check=True,
)
findings = json.loads(result.stdout)["results"]
for path, items in findings.items():
    for item in items:
        print(f"{path}:{item['line_number']}: {item['type']}")
raise SystemExit(bool(findings))
