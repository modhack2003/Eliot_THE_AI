# Changes

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
