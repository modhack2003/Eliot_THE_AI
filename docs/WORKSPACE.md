# Intelligence workspace

Eliot 2.0.0a5 brings conversations, durable security missions, skills and personas into one local browser workspace.

## Start

Run the installed Eliot launcher and open the address it prints. Existing installations can be upgraded by rerunning the installer from the updated source. Restart the backend after upgrading, then refresh the browser.

Open **Connections → Add connection**. Enter an OpenAI-compatible Chat Completions base URL and exact model ID. Use an environment-backed key or a temporary in-memory key. Choose **No key** for a local model server. **Test connection** makes a real provider request.

## Command

Select your model and persona above/below the message composer. Enter sends; Shift+Enter adds a line. Stop cancels the current response. Recent conversations, export and deletion remain available. If the live connection drops, Eliot checks the stored response and reconnects automatically. Backend restarts refresh the browser connection token on the next rejected request; accepted messages are not automatically resent.

The neural core is decorative geometry. Its speed and labels follow actual activity; it does not display private reasoning or invented telemetry. **Pause motion** freezes decorative motion. Reduced-motion preferences are honored, and rendering pauses when the core or browser is hidden.

## Missions

1. Choose **New mission**, describe the objective and enter an existing evidence folder on the backend machine.
2. Choose a connection, persona and parallel-worker limit. Zero step/token budgets mean unlimited usage, not unlimited context or guaranteed completion.
3. Local evidence is the default. For network observations, explicitly enable them and list exact target hosts or IP addresses within your assessment scope.
4. Launch and inspect the agent team, recorded activity and results. Worker **Inspect** opens the worker's own journal; **Coordinator** returns to its root task.
5. Send feedback to add direction. Pause or cancel when needed. Resume uses saved context and can adjust root mission budgets. If a worker pauses or exhausts a budget, the coordinator retains its delegation checkpoint. Resume the coordinator to continue the same workers. Filter missions by active, paused, cancelled, completed or attention status.

Closing the browser does not stop a task while the backend remains running. A backend interruption is handled by the existing recovery mechanism. Blocked tasks show why external input/change is needed. Task results and tool capabilities remain limited to the registered core adapters documented in AGENT_CORE.md.

## Skills and personas

Search the 83 bundled Claude-BugHunter modules by name or description. Open a module to read its pinned, integrity-checked Markdown and source revision; use **Read next page** for longer guides. The **Guide or reference** selector opens bundled reference documents, with the same integrity checks and pagination. Skill content is shown as plain text and does not execute in the browser.

Open **Personas** or **Import persona** to paste instructions or load a `.txt`/`.md` file (up to 12,000 characters). Imported personas can be edited and selected for new conversations or missions. Existing missions retain their persona snapshot. Fixed system rules take precedence over persona and skill guidance.

## Responsive controls

On narrower screens, use the top-left menu to navigate. Escape closes navigation and dialogs. The library supports arrow-key tab switching. All assets and the procedural canvas are served locally; no font CDN, image service or JavaScript build tool is needed to run Eliot.
