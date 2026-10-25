# Changes

## 2.0.0a5 — 25 October 2026

- Preserved delegation checkpoints when workers pause or exhaust a budget;
  extending the coordinator budget now resumes its existing team.
- Preserved saved memory and plans when a model omits those optional fields.
- Fixed task-start cleanup races and prevented worker resumes under stopped coordinators.
- Added chat stream reconnection with stored-status recovery, bounded backoff,
  missing-record handling and protection against stale stream updates.
- Added automatic refresh of expired local request tokens, request timeouts,
  startup recovery and restoration after browser back/forward navigation.
- Added bundled reference documents to the skill reader and paused/cancelled
  mission filters; reference reads remain restricted to verified bundle files.
- Added mission, API and browser-transport regression tests, including CI coverage.

## 2.0.0a4 — 25 October 2026

- Rebuilt the browser workspace with obsidian glass, cyan/amber accents and a
  procedural animated neural core driven by actual task/chat activity.
- Added mission creation, worker inspection, event journals, feedback, pause,
  resume with budget adjustments and cancellation to the browser.
- Added searchable pinned skills with a paginated reader, persona import/edit
  and persona selection for conversations and new missions.
- Added responsive navigation, keyboard library tabs, reduced-motion support
  and animation throttling when hidden. Kept assets local with no JS build step.
- Added skill-reader API regression coverage and installed-asset checks.

## 2.0.0a3 — 24 October 2026

- Added one-command Kali/Debian/Ubuntu setup with automatic OS prerequisites,
  isolated Python installation, default skills and an application launcher.
- Added Windows double-click/PowerShell setup with Python provisioning through
  winget when needed; security-tool provisioning remains Linux-first.
- Separated installed configuration/data from runtime and source, preserved
  existing state on reinstall, locked concurrent setup and verified a candidate
  before atomically activating it. Old runtimes remain available for inspection.
- Expanded offline doctor checks for dependencies, storage, web assets, skill
  integrity and nmap, with machine-readable reports and strict exit status.
- Moved the historical prototype, agent modules, deployment scripts and old docs
  under legacy/; retained compatibility aliases for the old installer commands.
- Added real Linux/Windows installation CI and outside-source API verification.

## 2.0.0a2 — 24 October 2026

- Added durable cybersecurity tasks with independent coordinator/worker state,
  action journals, factual working memory, feedback, pause/cancel/resume and restart recovery.
- Added typed evidence inspection, atomic task artifacts, scoped HTTP observations
  and a constrained nmap service-observation adapter for Kali/Linux workers.
- Added completion evidence references and a separate reviewer pass, cached-action
  detection and explicit blocked/budget states; no default step/token budget.
- Added text persona import and task snapshots below fixed system instructions.
- Bundled 83 pinned Claude-BugHunter Markdown skill modules with their references,
  source hashes, CC BY 4.0/MIT notices and credits; executable upstream code is excluded.
- Added task/persona/skill CLI commands and local API routes.
- Added regression tests for the task graph, recovery, replay, scoped tools,
  prompt boundaries, artifact access and review rejection.
- Deferred voice and visual redesign; broad legacy security-tool migration is still pending.

## 2.0.0a1 — 24 October 2026

- Added a shared local backend and terminal/browser clients.
- Added independent OpenAI-compatible profiles with custom base URLs, model IDs,
  environment key references, temporary keys and keyless local endpoints.
- Added asynchronous streaming and standard JSON responses, normalized usage and
  finish reasons, bounded retries, timeouts and safe provider error messages.
- Added SQLite conversations and run history, restart recovery, export and deletion.
- Added run cancellation and an atomic guard against overlapping sends per conversation.
- Added responsive provider/chat UI, same-origin controls and plain-text rendering.
- Replaced the default entrypoint and launcher; preserved the prototype as legacy code.
- Removed embedded database credentials from current source.
- Repaired selected legacy MongoDB, key cooldown, command routing, configuration
  reload/path handling, and COMPLETE termination bugs.
- Added automated regression tests, a Linux/Windows CI definition and a buildable wheel.

This is a working chat foundation. Security-tool migration and production remote
hosting are not included. Previously exposed credentials still require revocation.
