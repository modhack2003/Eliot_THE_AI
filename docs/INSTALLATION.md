# Install Eliot

## One-command Kali/Linux setup

Download the source ZIP, extract it, open a terminal in that folder and run:

```bash
bash install.sh
```

Supported automatic provisioning: current Kali, Debian 12+ and Ubuntu 24.04+,
including these distributions inside WSL. Python 3.11+ is required. Older systems
receive a clear version error; the installer does not replace the OS Python
with an unofficial interpreter. Run as your regular account. If you use sudo
for the whole installer, the application is installed for root instead.

The setup automatically:

1. Installs missing `python3`, `python3-venv`, `python3-pip`, `git`, `curl`,
   `ca-certificates` and `nmap` through apt. Sudo may request your password once.
2. Creates a dedicated virtual environment and installs Eliot's declared Python
   dependencies: FastAPI, Pydantic, Uvicorn, HTTPX and PyYAML, plus their dependencies.
3. Includes all 83 pinned Claude-BugHunter Markdown skill modules and references.
4. Creates an empty versioned provider configuration if none exists.
5. Checks imports, SQLite write access, browser assets, every skill file hash and
   nmap availability, without API calls or target scans.
6. Activates the verified runtime, installs a stable launcher and adds an Eliot
   application-menu shortcut. No system service is enabled automatically.

Start **Eliot** from the application menu or run:

```bash
~/.local/bin/eliot
```

The terminal stays open to run the backend. Visit **http://127.0.0.1:8765** in
your browser. Enter your OpenAI-compatible API endpoint, exact model ID and key.
No credentials or model downloads are supplied by the installer. The key may
be temporary in-memory or referenced by an environment variable. For example:

```bash
export ELIOT_API_KEY='your-key'
~/.local/bin/eliot serve
```

In another terminal, use `~/.local/bin/eliot chat` for text conversation.
Put `~/.local/bin` on PATH to use `eliot` as a short command. The installer
prints the full launcher path and does not modify your shell startup files.

## Standalone Linux bootstrap

Once this installer is merged into the default branch, it can also install
from a downloaded copy, automatically fetching the repository:

```bash
curl -fsSL https://raw.githubusercontent.com/modhack2003/Eliot_THE_AI/main/install.sh -o eliot-install.sh && bash eliot-install.sh
```

This needs curl to fetch the initial script. The fetched script installs Git
and the remaining prerequisites. While reviewing an unmerged branch,
download that branch's ZIP instead, or pass `--ref codex/remaster-foundation`
to a standalone copy of its `install.sh`. `--ref` selects the remote checkout
only when the script has no source tree beside it.

## Locations and upgrades

| Item | Linux default | Windows default |
| --- | --- | --- |
| Launcher | `~/.local/bin/eliot` | `%LOCALAPPDATA%\Eliot\bin\eliot.cmd` |
| Configuration | `~/.config/eliot/config.yaml` | `%LOCALAPPDATA%\Eliot\config\config.yaml` |
| Conversations, tasks, personas | `~/.local/share/eliot/eliot.db` | `%LOCALAPPDATA%\Eliot\data\eliot.db` |
| Isolated runtimes and active pointer | `~/.local/share/eliot/` | `%LOCALAPPDATA%\Eliot\data\` |

Linux respects `XDG_CONFIG_HOME` and `XDG_DATA_HOME`. Choose one custom directory
for everything with:

```bash
bash install.sh --prefix "$HOME/Applications/Eliot" --no-desktop
"$HOME/Applications/Eliot/bin/eliot"
```

Reinstall/upgrade by running the same installer against the newer source, using
the same account and prefix. Stop Eliot before upgrading. Each attempt creates
a fresh runtime at its final path. Configuration, database, saved personas and
task history are preserved. The active runtime pointer changes atomically only
after the candidate passes checks. A failed install leaves the old runtime
active. OS package installations performed by apt are not rolled back.

Previous and unsuccessful runtime directories remain under `runtimes/` for
inspection; the installer does not delete them. `installation.json` records
the active and previous runtime. These can use disk space after repeated
installs. Keep the runtime referenced by the active pointer. Back up the
configuration, database and any separate engagement workspaces before cleanup.

The installed runtime does not depend on the original extracted source folder.
It is safe to move the source after installation. Do not move installed venvs;
rerun with a new prefix instead.

## Windows convenience setup

Double-click `install.cmd`, or run `./install.ps1` in PowerShell. With no Python,
setup uses winget to install official Python 3.13 for your account. If winget
is unavailable, install Python 3.11+ from python.org, then rerun setup. The
Python and package downloads require internet access. No automatic WSL/OS
installation is attempted.

```powershell
.\install.ps1 -Prefix "$env:LOCALAPPDATA\My Eliot" -NoDesktop
& "$env:LOCALAPPDATA\My Eliot\bin\eliot.cmd"
```

The convenience installer creates an `Eliot.cmd` desktop shortcut when your
standard Desktop directory exists. Automatic security-tool provisioning is
supported by the Linux installer. Windows supports the shared chat, web UI and
local evidence tools; nmap is available only if installed and on PATH.

## Troubleshooting

```bash
eliot doctor --strict --require-nmap
eliot doctor --json
eliot serve --port 8876
```

`doctor` never sends provider requests. It reports unconfigured providers as a
warning, so installation succeeds before a key is supplied. `--strict` returns
a failing exit status for dependency, storage, configuration or bundle errors;
`--require-nmap` also requires the network adapter's executable. It checks
presence, not a live scan. Other registered evidence tools use Python's runtime.

- **No sudo:** ask an administrator to install the listed OS packages, then use
  `bash install.sh --skip-system`. On another Linux distribution, provision the
  equivalent packages yourself before using this option.
- **Network/package download error:** correct connectivity or package repository
  settings, then rerun the same command. The current runtime remains active.
- **Python too old:** use a supported distribution release with Python 3.11+.
- **Legacy config error:** the old Gemini/MongoDB schema is incompatible. Keep
  the old file as a backup and use a separate prefix for the new app.
- **Install lock left after a crash:** first confirm no installer is running;
  then remove the printed `install.lock` file and retry.
- **Port occupied:** select another port and supply the matching `--server`
  URL for the terminal client.
- **Missing bundle file/hash mismatch:** reinstall from an unmodified source
  checkout. Bundled Markdown is preserved byte-for-byte for integrity checks.

MongoDB, Torch, Gemini SDKs and the historical MCP daemon are not prerequisites
of this version. Skills describe many external security utilities; they do not
register executable adapters. Setup installs the utility used by the current
network adapter (nmap). Broader tool adapters and their installation profiles
remain future work. Installation does not perform an assessment or resume a
task until you start the backend.

## Repository structure

The supported code lives in `eliot_app/`, install helpers in `scripts/`,
documentation in `docs/` and automated checks in `tests/`. `legacy/` preserves
the historical prototype separately; its dependencies and deployment scripts
are excluded from supported installation. Old root installer names forward to
the current installer instead of executing archived deployment behavior.
