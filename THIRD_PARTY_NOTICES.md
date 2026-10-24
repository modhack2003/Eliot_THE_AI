# Bundled cybersecurity skills

Eliot includes Markdown skill content and references from
[elementalsouls/Claude-BugHunter](https://github.com/elementalsouls/Claude-BugHunter),
revision `98076cf3ce86651fbdc66798555fae817a5b875c`.

The reviewed snapshot contains 83 skill directories. The upstream author is
Sachin Sharma, with additional contributors and MIT-derived components identified
in the preserved upstream credits. Upstream code is MIT licensed; upstream
documentation and skill content are licensed under **CC BY 4.0**, as stated in
the upstream NOTICE. The original MIT license, full CC BY 4.0 license, NOTICE,
and upstream contributor/source credits are preserved in
`eliot_app/bundled_skills/claude_bughunter/`.

Markdown files are copied without content changes. Eliot adds a provenance and
SHA256 manifest and its own catalog/paging adapter. Executable scripts, fonts,
hooks, runtime engines and community-skill installation scripts are not copied
or executed. External references in a skill do not imply those tools are installed.

The bundle is available by default in source and wheel installations. It is loaded
as subordinate guidance under Eliot's fixed system rules and persona, and does
not grant execution or network permissions. Updating the bundle requires an
explicit source update and manifest regeneration; there is no background update.

The comparison also inspected
[awarexone/Agentic-Bug-Hunter](https://github.com/awarexone/Agentic-Bug-Hunter) at
`16dabf0cea8a43ad9d42733283e0fd8ed74313c0`. That snapshot has 19 skill directories
and a substantial independent runtime. It is not bundled; Eliot retains its own
provider-independent durable runtime and uses the more granular Claude-BugHunter
knowledge modules.
