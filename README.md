# Eliot Remastered

**Your models. Your conversations. One local workspace.**

Eliot now has a shared Python backend, a browser interface and a terminal client.
Connect an OpenAI-compatible Chat Completions endpoint, select its exact model ID,
and use your own API key. Local model servers can run without authentication.
Conversations and run history are stored in SQLite on your machine.

Version **2.0.0a3** adds one-command installation and a clearer project structure
on top of the durable cybersecurity agent core: coordinator/worker
tasks, typed evidence tools, scoped observations, checkpoints, completion review,
uploaded personas and 83 default skill modules. Ordinary conversation remains
separate from task execution. The original broad security-tool integrations
remain in the source tree for migration.

See [the agent core guide](docs/AGENT_CORE.md) for long-running tasks and
[third-party notices](THIRD_PARTY_NOTICES.md) for the bundled skill provenance.

```sh
eliot tasks create "Review the supplied cybersecurity evidence and delegate independent checks" --workspace /path/to/engagement --max-workers 3
eliot tasks watch TASK_ID
```

## Install and start

Download/extract this repository, then run one command in its folder.
Kali Linux, Debian 12+ and Ubuntu 24.04+:

```bash
bash install.sh
```

The installer brings Python, venv/pip, Git, curl, CA certificates and nmap,
installs Eliot and its Python dependencies in an isolated environment, includes
all **83 bundled skills**, verifies the installation and creates an **Eliot**
application-menu shortcut. It requests sudo only for missing OS packages. Run
as your normal user; no global pip installation is used. Internet access is
required for the first installation.

Open **Eliot** from the application menu, or start its installed launcher:

```bash
~/.local/bin/eliot
```

Windows: double-click **install.cmd**, or use PowerShell:

```powershell
.\install.ps1
& "$env:LOCALAPPDATA\Eliot\bin\eliot.cmd"
```

Windows setup installs Python through winget when needed, then installs the same
app and skills. Automatic provisioning of security tools targets Kali/Linux;
on Windows, nmap is detected if already installed and otherwise reported missing.
See [the installation guide](docs/INSTALLATION.md) for custom locations,
troubleshooting, upgrades and the standalone Linux bootstrap command.

Open **http://127.0.0.1:8765**, then connect your endpoint, exact model ID and API
key. No model/key is bundled or purchased by installation. The installed launcher
starts the web/backend when given no arguments; pass `chat` to use its terminal
client while the backend is running. Add the printed launcher directory to PATH
for the short `eliot` command. If the port is occupied, use `eliot serve --port 8876`.
The backend binds to loopback and accepts local clients only. Keep one backend
process per configuration/database. This alpha does not support remote hosting
or multiple server workers.

## Connect a model

Start without any configuration file and choose **Connect your first provider**.
Enter a name, API base URL (including the provider's version prefix if required),
and the exact model ID from your provider. Eliot appends `/chat/completions`.

Use an environment variable for a persistent key, or enter a temporary key in
the provider form. A temporary key exists only in backend memory until that
process exits. Saved profiles contain the environment variable name, not its value.
Eliot does not return saved key values to the browser or place them in logs.
Messages are sent to the selected provider; local storage does not make remote
inference offline.

For an environment-backed key, set it **before** starting the backend:

```sh
export ELIOT_API_KEY='your-api-key'
eliot serve
```

```powershell
$env:ELIOT_API_KEY = 'your-api-key'
eliot serve
```

For a local model server, choose **No key**, its loopback API address and the
model loaded by that server. Remote providers require HTTPS. Streaming can be
disabled when an endpoint only supports standard JSON responses. Optional model
parameters are explicit; Eliot does not force a temperature or token-limit field.

**Test connection** sends a short model request and can incur provider charges.
Opening the app, listing providers and running `doctor` make no provider requests.
Tests distinguish missing/invalid keys, denied access, missing models/endpoints,
rate limits, connection failures, invalid responses and timeouts. Retries are
bounded and apply only to rate-limit and selected server-error responses; Eliot
does not silently forward a failed request to another provider.

Compatibility is with the **Chat Completions protocol**, not every feature of
every model. Native function calling, images, custom authentication headers and
the Responses API are not implemented in this alpha. Agent tasks use validated
JSON decisions with registered application tools instead. Use a text chat model and the provider's exact
parameter names. Optional `/models` discovery is not required.

## Use the terminal and browser together

Leave the backend running, then open another terminal in the same environment:

```sh
eliot chat
eliot sessions
eliot chat --session SESSION_ID
eliot chat --provider PROFILE_ID
eliot export SESSION_ID > conversation.json
```

Within chat, `/new` creates a conversation, `/provider PROFILE_ID` changes the
selected profile, and `/exit` exits. Ctrl+C during a response requests cancellation.
The web **Stop** button cancels that same backend run. Stopping a response closes
Eliot's request; the provider may still bill work already performed.

Both interfaces see the same sessions and history. The web client includes a
provider manager, recent conversations, streaming text, export, delete and run
status. Failed/cancelled responses remain visible in run history and are excluded
from future model context. Eliot sends the most recent completed turns, capped
at 41 messages and 80,000 characters; it does not automatically summarize older
history. All stored messages remain available for export.

Provider management is also available in the terminal:

```sh
eliot providers list
eliot providers add primary --base-url https://api.example.com/v1 --model exact-model-id --key-env ELIOT_API_KEY
eliot providers add local --base-url http://127.0.0.1:1234/v1 --model local-model-id --no-auth
eliot providers key primary
eliot providers test primary
eliot providers default primary
eliot providers forget-key primary
eliot providers delete primary
```

The `key` command uses hidden input. `forget-key` removes the temporary backend
key; it cannot unset the environment variable of a running process.

## Configuration and data

See [config.example.yaml](config.example.yaml) for the versioned schema.
Configuration is saved atomically. Relative database paths are resolved against
the configuration directory. The installer uses `~/.config/eliot/config.yaml`
and `~/.local/share/eliot/eliot.db` on Linux (respecting XDG), and
`%LOCALAPPDATA%\Eliot` on Windows. Running directly from source defaults to
`config.yaml` and `data/eliot.db` in the source workspace.
`ELIOT_CONFIG` selects another config file; `CONFIG_FILE` is a fallback for older
deployment environments. A command-line `--config` takes precedence.

```sh
eliot --config remaster-config.yaml serve
eliot --config remaster-config.yaml doctor
eliot --server http://127.0.0.1:8876 chat
```

The original `llm.providers` YAML format is not silently migrated; a clear error
points to the example. Use a new path if you have an older `config.yaml`.
Back up the configuration and database after clean backend shutdown. SQLite
recovery marks unfinished runs interrupted on restart and preserves partial text.
Configuration and session data are ignored by Git. SQLite is sufficient for
this local, single-process release; MongoDB is not required.

The browser uses same-origin mutation tokens, host/origin checks and a restrictive
content policy. Responses are rendered as text, not executable HTML. There is
no network authentication layer for remote operation: do not expose this alpha
through a reverse proxy or network tunnel. Other trusted local programs can
access the backend as the local user.

## Development and verification

```sh
python -m pip install -e '.[test]'
python -m pytest -q
python main.py doctor
python -m pip wheel --no-deps .
```

Unit tests use isolated temporary databases, fake transports and selected legacy
definitions. Installation CI additionally provisions Ubuntu prerequisites,
installs into a path containing spaces, checks the launcher and real web/task
APIs outside the source tree, and verifies reinstall preservation. It runs a
Windows install too. No provider requests or assessment scans are needed.

```text
eliot_app/          Supported app, agent runtime, tools, browser assets and skills
scripts/           Shared installer and installed-app smoke verification
docs/              Installation and agent-core guides
tests/             Supported app and legacy regression checks
legacy/            Historical prototype, tools, scripts and old documentation
install.sh         Kali/Debian/Ubuntu prerequisite bootstrap
install.cmd/.ps1   Windows convenience setup
main.py            Source-development entrypoint
```

The installed app has no dependency on this source folder. The wheel contains
only the supported package, browser assets and skill bundle. The source archive
also includes the installers and preserved historical code.

## Migration status

The remaster replaces the default launcher; the original main implementation
is retained under `legacy/`, including its heavyweight requirements, `agent/`,
old entrypoints, MCP client, deployment scripts and historical docs. They are
not installed or executed by the new setup. Old root installation names forward
to `install.sh`; archived scripts under `legacy/scripts/` are reference only.

The working source no longer embeds the exposed MongoDB credential. The old
credential must still be revoked by its owner: source edits do not invalidate it
or erase earlier Git history. No exposed credential was used during development.

Legacy repairs also remove MongoDB `_id` before dataclass construction, respect
the chosen config path, reload config after key changes, make tool/key handlers
reachable, respect Gemini cooldowns and stop when the legacy model says COMPLETE.
The legacy workflow persistence stubs, automatic vulnerability labels, generated
code contract, external-session handling and historical packaging still need
migration and validation. This release does not claim those features are fixed.

Next milestones: broader Kali tool adapters, stronger workflow-specific finding
validators, isolated worker environments, Linux integration validation and the
new visual interface. Keep the original attribution and third-party notices
when redistributing.
