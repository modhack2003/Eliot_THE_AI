# Durable cybersecurity task core — 2.0.0a2

The terminal and HTTP API now run persistent cybersecurity tasks separately from
ordinary conversation. Work is owned by the backend, not the terminal connection.
The default focus is bug bounty, red teaming, VAPT, OSINT, CTF, cryptography,
AI security, cloud, binary, and Web2/Web3 assessment. The current tool adapters
cover evidence inspection, report artifacts and limited scoped observation;
listing a domain does not mean every tool for that domain is implemented.

## Start a task

Start the backend normally with `eliot serve`, then in another terminal:

```sh
eliot tasks create "Review the supplied assessment evidence, delegate independent checks, and save an evidence-based report" --workspace /path/to/engagement --max-workers 3
eliot tasks list
eliot tasks watch TASK_ID
eliot tasks show TASK_ID
eliot tasks feedback TASK_ID "Prioritize the uploaded API logs and distinguish hypotheses from verified results"
eliot tasks pause TASK_ID
eliot tasks resume TASK_ID
eliot tasks cancel TASK_ID
```

Ctrl+C while **watching** only disconnects the observer. Use pause/cancel to stop
the work. Cancel/pause propagates to the coordinator's children and active tool
requests. The backend must remain running for work to execute. During a clean
shutdown, active tasks are queued and recover on next startup. Following a crash,
the next backend also recovers unfinished root tasks from their last checkpoint.
Environment-backed provider credentials must still be available; temporary keys
do not survive process exit, so those tasks block until a key is restored and
the operator resumes them.

### Scoped network observation

Network tools are disabled unless enabled when the task is created, with exact
authorized host names/IP addresses. No per-step confirmation is requested inside
that declared scope.

```sh
eliot tasks create "Observe the authorized lab service and report what the evidence establishes" --workspace /path/to/lab --network --target lab.example --skill recon-scope-triage --skill triage-validation
```

The initial tools are:

| Tool | Implemented behavior |
|---|---|
| `list_files` | Workspace evidence inventory, capped per call; excluded configuration/secret directories are skipped. |
| `read_file` | Paged UTF-8 evidence with source line numbers. |
| `search_files` | Literal text search across a bounded set of evidence files. |
| `file_info` | File size, SHA256, magic bytes and bounded printable strings, including binary evidence. |
| `write_artifact` | Atomic, idempotent new reports in `.eliot-artifacts/TASK_ID/`; existing different content cannot be overwritten. |
| `read_artifact` | Read artifacts belonging to this task graph, including worker reports. |
| `read_skill` | Paged, integrity-checked installed skill/reference Markdown. |
| `http_observe` | One unauthenticated GET to an explicitly scoped host, with bounded content and no redirect following. |
| `nmap_services` | TCP connect and light service discovery for one scoped host and up to 128 explicit ports; no vulnerability scripts. Requires nmap on the Kali/Linux worker. |

Tool inputs are validated independently of model instructions. No generic shell
tool or implicit execution of imported skill scripts exists. Writes are confined
to task artifacts, and child agents inherit their parent's workspace and network
scope. This is application-level validation, not a kernel/container sandbox.
Real nmap execution and subprocess cancellation still need validation on Kali;
local automated tests use a fake process and do not scan live targets.

## Coordinator, workers, and verification

The selected model returns a validated JSON decision: use a registered tool,
delegate independent subtasks, propose completion, or report a blocker. This
text-JSON protocol works with compatible chat endpoints without requiring native
function-calling support. Invalid responses are recorded and retried a bounded
number of times. A model incapable of reliably producing the schema will block.

The coordinator can delegate up to the configured concurrent worker limit
(1–6). Workers cannot recursively spawn more workers. Each has its own persisted
state, evidence ledger, artifacts and reviewer pass. The coordinator receives
their results and can plan another round. Model calls and tools also have global
concurrency limits to keep the worker process responsive.

Decisions are checkpointed before execution. Finished action results are journaled
under deterministic IDs and reused after recovery rather than executed again.
Read-only actions interrupted before their result was recorded may run again;
the runtime does not promise exactly-once effects across arbitrary OS crashes.
Artifact writes are atomic and content-idempotent.

Completion requires a nonempty result and valid recorded evidence IDs. A separate
reviewer call to the same selected provider sees the proposed conclusion and
the actual cited records. A rejected review returns the task to planning. This
is an additional check, not a guarantee that an LLM's conclusion is correct or
a substitute for a verified vulnerability reproduction.

There is no tiny default task limit: step and token budgets default to **0
(unlimited)**. Optional budgets cover the task graph, including worker usage.
Concurrent in-flight calls can exceed a newly reached budget. Missing provider
usage is estimated and flagged, not represented as measured usage. No dollar
cost is invented for providers with unknown pricing.

```sh
eliot tasks create "Review this evidence" --workspace /path/to/evidence --max-steps 100 --token-budget 200000
eliot tasks resume TASK_ID --max-steps 0 --token-budget 0
```

Persistence is not an instruction to loop forever: repeated actions/results,
invalid decisions and rejected completion claims eventually produce a recorded
blocker instead of another identical attempt. Transient provider failures retry
with backoff and respect Retry-After; invalid keys/requests require configuration
changes. Feedback is included in later planning turns and can inform a resumed
task. It cannot expand permissions. No runtime can prove that an infinite search
space has been exhausted.

## Fixed rules, uploaded persona, and skills

The hierarchy is fixed application rules and runtime permissions → persona →
skills → task/evidence data. Only application-owned rules occupy the system role;
uploaded persona and skill data are subordinate. Human pause/cancel commands are
implemented outside the model. A model's obedience to prose cannot be guaranteed
across arbitrary providers; path, tool and scope restrictions are enforced by code.

```sh
eliot personas --import-file /path/to/persona.md --id custom-eliot --name "Custom Eliot"
eliot personas
eliot chat --persona custom-eliot
eliot tasks create "Review this assessment" --workspace /path/to/engagement --persona custom-eliot
eliot skills
```

Persona uploads are text, not executable plugins. Tasks snapshot their persona,
provider configuration and selected skill IDs, so later edits do not silently
change an active task's instructions or endpoint. Imported text cannot replace
the fixed system rules. The built-in Eliot persona is read-only.

The default installation includes 83 pinned Claude-BugHunter skill modules and
their Markdown references. Selected skills have explicitly marked previews;
the model can read complete relevant sections on demand, keeping context finite.
All knowledge modules are available, but external tools referenced by those
documents are not automatically installed. See THIRD_PARTY_NOTICES.md for source,
revision, attribution, content licensing and exclusions.

## HTTP API

- `GET /api/skills`, `GET /api/skills/ID?start_line=1` (pinned Markdown pages).
- `GET /api/instructions` (read-only rules/hash).
- `GET /api/personas`, `PUT /api/personas/ID` (`name`, `instructions`).
- `POST /api/tasks` (objective, workspace, provider/persona, skills, scope, budgets).
- `GET /api/tasks`, `GET /api/tasks/ID`, `GET /api/tasks/ID/events?after=EVENT_ID`.
- `POST /api/tasks/ID/feedback` (`text`).
- `POST /api/tasks/ID/pause`, `/resume`, `/cancel`.

Use the existing local same-origin token from `/api/bootstrap` for mutations.
The task core is available through CLI/API and the browser mission dashboard.
See [the workspace guide](WORKSPACE.md) for the animated interface, skill reader
and persona controls. Voice, broader Kali adapters, sandbox workers and more
specialized assessment workflows remain future work.
