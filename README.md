# Eliot Remastered

**Your models. Your conversations. One local workspace.**

Eliot now has a shared Python backend, a browser interface and a terminal client.
Connect an OpenAI-compatible Chat Completions endpoint, select its exact model ID,
and use your own API key. Local model servers can run without authentication.
Conversations and run history are stored in SQLite on your machine.

Version **2.0.0a1** is the first working remaster milestone. It provides chat,
provider configuration, persistence and cancellation. The original security-tool
integrations remain in the source tree for migration; this release's chat does
not execute shell commands or run autonomous penetration tests.

## Install and start

Requires Python **3.11 or newer**. Run these commands in the extracted repository.

Linux / Kali:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python main.py serve
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe main.py serve
```

Open **http://127.0.0.1:8765**. If that port is occupied, use `python main.py serve --port 8876`.
After installation, the `eliot` command is equivalent to `python main.py`.
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
every model. Tools, images, custom authentication headers and the Responses API
are not implemented in this alpha. Use a text chat model and the provider's exact
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
the configuration directory. Defaults are `config.yaml` and `data/eliot.db`.
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

Tests use isolated temporary databases, fake transports and selected legacy
definitions; they do not call real providers or run security tools. CI is
configured for Python 3.11/3.13 on Linux and Windows. A workflow being configured
does not mean it has run remotely.

Code is organized under `eliot_app/`: configuration, provider gateway, storage,
run service, HTTP API, terminal client and browser assets. `main.py` is a small
entrypoint. The wheel includes the web assets and the supported remaster package.

## Migration status

The remaster replaces the default launcher; the original main implementation
is retained as `legacy_main.py`. Its heavyweight dependencies are separated in
`requirements-legacy.txt`. `agent/`, `mcp_client.py` and historical installation
scripts remain for reference and future migration. They are not part of the new
shared chat backend, and the old installers are not the supported setup path.

The working source no longer embeds the exposed MongoDB credential. The old
credential must still be revoked by its owner: source edits do not invalidate it
or erase earlier Git history. No exposed credential was used during development.

Legacy repairs also remove MongoDB `_id` before dataclass construction, respect
the chosen config path, reload config after key changes, make tool/key handlers
reachable, respect Gemini cooldowns and stop when the legacy model says COMPLETE.
The legacy workflow persistence stubs, automatic vulnerability labels, generated
code contract, external-session handling and historical packaging still need
migration and validation. This release does not claim those features are fixed.

Next milestones: validated tool registry and evidence records, reliable transport
adapters, scoped jobs, verified findings, bounded workflows, and Linux installation
validation. Keep the original attribution and license when redistributing.
