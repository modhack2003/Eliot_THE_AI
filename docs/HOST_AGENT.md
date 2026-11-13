# Eliot host agent — 2.0.0a6

Eliot runs tools directly on the computer running its Python backend. The project does not add a container, VM or execution-isolation layer. This is an explicit project requirement recorded in `AGENTS.md`.

## Launch and grant a mission its capabilities once

```sh
eliot serve
eliot tasks create "Create a report from the supplied evidence, then verify its contents" --workspace /path/to/project --host --edit --max-steps 100 --checks '[{"kind":"file_exists","path":"report.md"}]'
```

`--host` enables command and Python execution. `--edit` enables versioned text edits. The mission form exposes those capabilities plus browser/desktop controls, completion checks, time/tool budgets and worker/reviewer model selection. Additional settings are accepted as JSON in the advanced mission form or CLI `--options`.

Permission choices apply to the whole mission and its workers; individual approved steps do not prompt again. Host commands have the operating-system user's authority and can access the host network. Hostname/port/path restrictions apply to the typed HTTP, nmap, browser and robotics adapters; they do not restrict networking performed by arbitrary host commands.

The command tool accepts an argv list and does not implicitly invoke a shell. A task can explicitly invoke a shell if that executable is permitted. An optional `executables` list restricts executable selection, not the authority of the executable or scripts it runs. Output, timeouts and cancellation are bounded. On Windows, subprocess cancellation uses `taskkill /T` to terminate descendants.

## Mission options

| Option | Meaning |
|---|---|
| `host_execution`, `file_edit` | Enable host processes or versioned workspace edits |
| `browser`, `desktop`, `robotics` | Enable optional device adapters |
| `executables` | Optional permitted executable names/paths; empty permits any host executable |
| `ports`, `url_paths` | Typed network adapters' allowed ports and URL path prefixes |
| `expires_at` | Permission expiry as a Unix timestamp |
| `wall_seconds`, `max_tool_calls` | Whole-mission time/tool-call limits; zero disables a limit |
| `cost_budget_usd` | Monetary accounting limit using configured provider prices and measured usage |
| `tool_timeout` | Whole-operation timeout for asynchronous adapters |
| `max_provider_retries`, `outage_seconds` | Bounds for transient provider outages before parking a mission |
| `worker_provider_id`, `reviewer_provider_id` | Explicit role-specific model profiles |
| `routing_mode`, `approved_providers` | Opt-in `fastest`, `lowest_cost`, or `highest_completion` worker routing among approved profiles; default `fixed` |
| `robot_url` | Explicitly scoped HTTP robotics bridge base URL |

Costs cannot be undone after a model call. Concurrent in-flight calls can exceed a newly reached token/cost/tool budget. An enabled monetary budget requires input/output token prices for all routed profiles, and the mission parks if the provider omits measured input/output usage. Unpriced work displays cost as unknown. Routing's historical completion rate is an operational proxy, not a benchmark of vulnerability accuracy. Latency/completion routing uses at least five recorded calls per candidate, otherwise it selects the approved primary or first approved profile.

## Planning and completion

The model can return a `plan` decision containing `plan_steps`: unique step IDs, objectives, dependencies, state, expected outputs and evidence IDs. Cycles, missing dependencies and unsupported completed states are rejected. The model receives the goal contract, current plan, tool schemas and evidence. New observations can revise the plan.

Operator-supplied `success_checks` remain in the task state and cannot be replaced by a model decision:

- `file_exists`: verify an evidence/artifact file exists, including binary output.
- `file_contains`: inspect paged UTF-8 file contents for required text.
- `command_exit`: match a recorded tool return code; `path` optionally binds the executable.
- `http_status`: match a recorded observation's status and optional exact URL in `path`.

For fine-grained command identity or domain-specific correctness, inspect the recorded action and use an appropriate external verifier. These checks are useful predicates, not a universal proof of objective completion. A generated artifact, skill document or remembered claim alone cannot satisfy completion; source observations and a reviewer pass are required. All structured plan steps must be completed too. A separately selected reviewer profile receives a neutral verifier persona.

## Recovery, artifacts and edits

Checkpoint replay reuses committed action results. New file observations include source revisions. Failed observations can be attempted after repair; HTTP observations expose `refresh`. Repeated identical worker objectives reuse children and eventually trigger the no-progress guard. Source paths remain part of evidence novelty.

Artifacts stay in `.eliot-artifacts/TASK_ID`. Symlinks/junctions are rejected. POSIX artifact reads/writes use directory-relative, no-follow operations; Windows uses checked paths and atomic hard-link publication. Windows does not provide the same directory-descriptor protection against concurrent local path replacement.

`edit_file` accepts `expected_sha256` (empty for a new file), `content`, and optional `preview`. A preview returns a diff. An applied edit retains its prior version; `rollback_file` restores it only if the current contents still match that edit. Ordinary local atomic writes settle and are journaled before stop is acknowledged. Arbitrary host commands, browser actions and robot requests can have external effects that cannot be rolled back automatically. Interrupted actions are recorded; inspect actual state before deciding to retry.

## Evidence and memory

`read_evidence` retrieves older action/worker records within a task graph. File inventory, literal search and long text pages expose continuation positions. Repeating inventory/search while files change may require restarting pagination; source revision hashes record the inputs observed.

`remember`, `recall`, and `forget_memory` manage facts in task, project and local-user scopes. A new fact needs a recorded successful evidence ID and retains source/confidence metadata. The API supports listing, correction and deletion; the dashboard supports project search/deletion. Memory is data, not execution authority. Known configured keys and credential-shaped text are redacted at model/result boundaries. Redaction is best effort, and it does not make arbitrary imported data safe to execute.

The following optional inputs produce normalized, deduplicated **unverified observations** through `import_findings`: SARIF, nuclei JSON/JSONL, nmap XML, HAR and JSON dependency manifests. Importing a scanner result does not independently establish exploitability. XML uses defusedxml.

## Browser, desktop, voice and vision

```sh
python -m pip install '.[browser]'
python -m playwright install chromium
python -m pip install '.[desktop]'
```

The browser adapter uses host Chromium/Chrome when installed, or Playwright's browser otherwise. It supports a persistent profile, DOM inspection, navigation, filling, clicking, key input and screenshots. Browser requests are checked against mission scope; redirects/subresources outside the declared scope are blocked. Downloads and service workers are disabled. Browser profiles live with Eliot's local data. Scope changes require a new mission/profile. PyAutoGUI provides host desktop screenshots, clicks, text entry, keys and scrolling, with its failsafe enabled. Desktop input targets the actual logged-in desktop and requires that desktop to be available; fixture coverage is not live desktop validation.

The provider form can explicitly mark a model as accepting images. `inspect_image` and screenshot tools attach up to two recent PNG/JPEG observations to subsequent vision-enabled requests. Text-only profiles receive image metadata only. Native multimodal behavior must be checked against the chosen provider. JSON response mode is optional for compatible Chat Completions endpoints; validated text-JSON decisions remain the fallback. Native provider function-call responses are not implemented and remain rejected.

The microphone and read-latest buttons use the browser's speech APIs. Availability depends on the browser, device permissions and speech service. Dictation populates the composer; it does not send a message automatically. Stop voice interrupts playback/listening. Voice recognition may use the browser vendor's remote speech service.

## Scheduler and separate host worker

By default the web backend supervises mission execution and scheduling. A database lease prevents a second execution worker from running concurrently. For a separate worker:

```sh
eliot worker
eliot serve --external-worker
eliot schedules create --file schedule.json
eliot schedules list
```

Example `schedule.json`:

```json
{
  "name": "Daily evidence review",
  "interval_seconds": 86400,
  "task": {
    "objective": "Review new evidence and produce a source-backed report",
    "workspace": "/path/to/project",
    "options": {"host_execution": true}
  }
}
```

`next_run` is a Unix timestamp; the dashboard displays it in the browser's timezone. An interval of zero runs once. Missed interval runs coalesce after downtime. A nonempty `trigger` creates an event-driven schedule; call `eliot schedules trigger ID EVENT_ID` with a stable event identifier. Repeated IDs reuse the same task. Enable/disable/delete are available in CLI/API/dashboard. Configuration failures disable the schedule with a recorded error; repair and re-enable it. There is no external webhook receiver or device-specific event producer bundled; existing software can call the authenticated loopback API.

Use your normal host service manager to restart a separate worker. The supervisor renews its lease, recovers queued work and propagates database pause/cancel commands to its local execution tasks. Keep only one execution worker per database. Ordinary conversation runs still belong to the web process.

## Optional robotics bridge

A mission with `robotics`, `network`, explicit targets and `robot_url` may call:

- `GET BASE/status`
- `POST BASE/command` with `{"command": {...}}`
- `POST BASE/emergency-stop` with `{}`

The bridge/controller must independently enforce physical bounds, command authorization, a watchdog timeout and an emergency stop. Eliot records bridge responses and explicitly marks physical state unverified. This adapter does not provide a motor controller, hard real-time control or proof that a physical stop occurred. No physical hardware was available during this implementation.

## APIs and validation

`GET /api/capabilities` returns schema/effect/permission/dependency metadata. `GET /api/model-performance` exposes recorded routing measurements. Mission lists are compact and paginated; details carry plans and metrics. Mission export includes actions/events across workers, and artifact download is limited to the task graph.

Run `python -m pytest -q` and `node --test tests/javascript/transport.test.cjs`. Optional browser end-to-end coverage requires Playwright and Chromium/Chrome and fails normally in CI; the local execution environment's native-socket denial is reported as a skip. The scripted browser model verifies wiring and host effects, not live model reasoning quality. GitHub security checks run dependency auditing, first-party secret scanning, static analysis and agent regression evaluations. See `review_and_roadmap.md` for implementation status and remaining live validation.
