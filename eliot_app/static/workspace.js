"use strict";
let missions = [],
  personas = [],
  skills = [],
  selectedTask = null,
  eventCursor = 0,
  detailSignature = "",
  missionSignature = "",
  polling = false,
  pollTimer;
let currentSkill = null,
  nextSkillLine = 1,
  skillResource = "SKILL.md",
  skillGeneration = 0;
const activeStatuses = ["queued", "running", "retrying"];
const attentionStatuses = ["blocked", "budget_exhausted"];
const statusLabel = (value) =>
  ({ budget_exhausted: "Budget reached", retrying: "Retrying connection" })[
    value
  ] || value.replaceAll("_", " ");
const node = (tag, className, text) => {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
};
const badge = (status) => node("span", "badge " + status, statusLabel(status));
function confirmAction(title, message, label) {
  const dialog = $("confirm-dialog");
  $("confirm-title").textContent = title;
  $("confirm-message").textContent = message;
  $("confirm-accept").textContent = label;
  dialog.returnValue = "cancel";
  return new Promise((resolve) => {
    dialog.addEventListener(
      "close",
      () => resolve(dialog.returnValue === "accept"),
      { once: true },
    );
    dialog.showModal();
  });
}
function closeNavigation() {
  const wasOpen = document.body.classList.contains("mobile-sidebar");
  $("main-content").inert = false;
  document.body.classList.remove("mobile-sidebar");
  $("sidebar-backdrop").hidden = true;
  $("menu-toggle").setAttribute("aria-expanded", "false");
  if (wasOpen) $("menu-toggle").focus();
}
$("sidebar-backdrop").onclick = closeNavigation;
$("menu-toggle").onclick = () => {
  document.body.classList.add("mobile-sidebar");
  $("sidebar-backdrop").hidden = false;
  $("menu-toggle").setAttribute("aria-expanded", "true");
  $("main-content").inert = true;
  $("new-chat").focus();
};
matchMedia("(min-width:741px)").addEventListener("change", closeNavigation);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeNavigation();
  if (e.key === "Tab" && document.body.classList.contains("mobile-sidebar")) {
    const focusable = [
      ...document.querySelectorAll(
        ".sidebar a, .sidebar button:not(:disabled)",
      ),
    ].filter((el) => el.getClientRects().length);
    const first = focusable[0],
      last = focusable.at(-1);
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    }
    if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
});
function setConnection(connected) {
  $("connection-label").textContent = connected
    ? "Local connection"
    : "Reconnecting";
  $("connection-indicator").classList.toggle("offline", !connected);
}
function updateActivity() {
  const working =
    !!currentRun ||
    submitting ||
    missions.some((m) => activeStatuses.includes(m.status));
  const attention = missions.some((m) => attentionStatuses.includes(m.status));
  document.body.dataset.activity = working
    ? "working"
    : attention
      ? "attention"
      : "idle";
  $("hero-status").textContent = working
    ? "Investigation in progress"
    : attention
      ? "A mission needs your attention"
      : "Standing by";
  $("inspector-state").textContent = working
    ? "PROCESSING"
    : attention
      ? "NEEDS ATTENTION"
      : "STANDING BY";
  // The core's own state label is owned by the emotion renderer, which has a
  // finer grained view (thinking and talking) than mission activity alone.
  document.dispatchEvent(new Event("eliot-emotion"));
  if (!document.getElementById("neural-canvas"))
    $("core-state").textContent = working
    ? "ACTIVE · PROCESSING SIGNALS"
    : attention
      ? "PAUSED · INPUT REQUIRED"
      : "IDLE · AWAITING INPUT";
}
function emptyState(title, description, action, label) {
  const el = node("div", "empty-state");
  el.append(node("h3", "", title), node("p", "", description));
  if (action) {
    const b = button(label, action);
    b.className = "secondary-button";
    el.append(b);
  }
  return el;
}
function fillSelect(id, values, selected) {
  const el = $(id),
    previous = selected || el.value;
  el.replaceChildren(...values.map((p) => new Option(p.name, p.id)));
  if (values.some((p) => p.id === previous)) el.value = previous;
}
function renderMissionList() {
  const query = $("mission-search").value.toLowerCase(),
    filter = $("mission-filter").value;
  const shown = missions.filter(
    (m) =>
      m.objective.toLowerCase().includes(query) &&
      (filter === "all" ||
        (filter === "active" && activeStatuses.includes(m.status)) ||
        (filter === "attention" && attentionStatuses.includes(m.status)) ||
        filter === m.status),
  );
  $("mission-list").replaceChildren();
  if (!shown.length) {
    $("mission-list").append(
      emptyState(
        missions.length ? "No matching missions" : "The next lead is yours.",
        missions.length
          ? "Try another search or status filter."
          : "Give Eliot an objective and an evidence workspace. Follow its workers, decisions and results here.",
        missions.length ? null : openMission,
        "Create your first mission ↗",
      ),
    );
    return;
  }
  for (const m of shown) {
    const card = button("", () => selectTask(m.id));
    card.className = "mission-card";
    card.classList.toggle("selected", selectedTask === m.id);
    const copy = node("div");
    copy.append(
      node("strong", "", m.objective),
      node(
        "small",
        "",
        `${m.persona.name} · ${m.steps} steps · ${new Date(m.updated * 1000).toLocaleDateString()}`,
      ),
    );
    card.append(copy, badge(m.status));
    $("mission-list").append(card);
  }
}
function renderOverview() {
  $("mission-count").textContent = missions.length;
  $("active-count").textContent = missions.filter((m) =>
    activeStatuses.includes(m.status),
  ).length;
  $("done-count").textContent = missions.filter(
    (m) => m.status === "completed",
  ).length;
  const attention = missions.filter((m) =>
    attentionStatuses.includes(m.status),
  ).length;
  $("attention-count").textContent = attention;
  $("attention-button").hidden = !attention;
  $("recent-missions").replaceChildren();
  if (!missions.length)
    $("recent-missions").append(
      node(
        "p",
        "rail-empty",
        "No missions yet. Your ongoing investigations will appear here.",
      ),
    );
  for (const m of missions.slice(0, 3)) {
    const b = button("", () => {
      showView("missions");
      return selectTask(m.id);
    });
    b.className = "rail-mission";
    b.append(
      node("strong", "", m.objective),
      node("small", "", statusLabel(m.status)),
    );
    $("recent-missions").append(b);
  }
  updateActivity();
}
async function refreshMissions() {
  const items = await api("/api/tasks");
  const signature = JSON.stringify(items);
  missions = items;
  if (signature !== missionSignature) {
    missionSignature = signature;
    renderMissionList();
    renderOverview();
  }
}
async function selectTask(id) {
  selectedTask = id;
  eventCursor = 0;
  detailSignature = "";
  $("task-events").replaceChildren();
  $("task-children").replaceChildren();
  $("task-actions").replaceChildren();
  $("task-objective").textContent = "Loading mission…";
  $("task-meta").replaceChildren();
  $("task-reason").hidden = true;
  $("task-result").hidden = true;
  $("task-status").textContent = "";
  $("task-feedback").value = "";
  $("mission-detail").hidden = false;
  renderMissionList();
  await refreshTask();
  if (selectedTask === id)
    $("mission-detail").scrollIntoView({ behavior: "smooth", block: "start" });
}
async function refreshTask() {
  if (!selectedTask) return;
  const id = selectedTask;
  const [task, events] = await Promise.all([
    api(`/api/tasks/${id}`),
    api(`/api/tasks/${id}/events?after=${eventCursor}`),
  ]);
  if (selectedTask !== id) return;
  const signature = JSON.stringify(task);
  if (signature !== detailSignature) {
    detailSignature = signature;
    renderTask(task);
  }
  for (const event of events) {
    if (event.id <= eventCursor) continue;
    renderEvent(event);
    eventCursor = event.id;
  }
}
function renderTask(task) {
  $("task-objective").textContent = task.objective;
  $("task-status").className = "badge " + task.status;
  $("task-status").textContent = statusLabel(task.status);
  $("task-meta").replaceChildren(
    ...[
      task.persona.name,
      `${task.totals.steps || 0} steps across team`,
      `${task.totals.estimated_usage ? "~" : ""}${(task.totals.tokens || 0).toLocaleString()} tokens`,
      task.policy.network
        ? `Targets: ${task.policy.targets.join(", ")}`
        : "Local evidence only",
      task.workspace,
    ].map((t) => node("span", "", t)),
  );
  $("task-actions").replaceChildren();
  const action = (label, name) => {
    const b = button(label, async () => {
      if (
        name === "cancel" &&
        !(await confirmAction(
          "Cancel this mission?",
          "The mission and its unfinished workers will stop. Saved evidence will remain.",
          "Cancel mission",
        ))
      )
        return;
      if (name === "resume") {
        openResume(task);
        return;
      }
      await api(`/api/tasks/${task.id}/${name}`, "POST");
      await refreshTask();
      await refreshMissions();
    });
    b.className = "secondary-button";
    $("task-actions").append(b);
  };
  if (activeStatuses.includes(task.status)) action("Pause mission", "pause");
  if (["paused", "blocked", "budget_exhausted"].includes(task.status))
    action("Resume mission ↗", "resume");
  if (!["completed", "cancelled"].includes(task.status))
    action("Cancel mission", "cancel");
  if (task.parent_id) {
    const back = button("↑ Coordinator", () => selectTask(task.root_id));
    back.className = "secondary-button";
    $("task-actions").append(back);
  }
  $("task-reason").textContent = task.reason;
  $("task-reason").hidden = !task.reason;
  $("task-result").textContent = task.result;
  $("task-result").hidden = !task.result;
  $("task-children").replaceChildren();
  if (!task.children.length)
    $("task-children").append(
      node(
        "p",
        "rail-empty",
        task.parent_id
          ? "Independent worker · scope inherited from coordinator"
          : "Coordinator · no workers delegated yet",
      ),
    );
  for (const child of task.children) {
    const row = node("div", "worker");
    const inspect = button("Inspect ↗", () => selectTask(child.id));
    inspect.className = "text-button";
    row.append(node("span", "", child.objective), badge(child.status), inspect);
    $("task-children").append(row);
  }
  $("feedback-form").hidden = ["completed", "cancelled"].includes(task.status);
}
function renderEvent(event) {
  const item = node("article", "event-item"),
    heading = node("div", "event-title");
  const time = node(
    "time",
    "",
    new Date(event.created * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }),
  );
  time.dateTime = new Date(event.created * 1000).toISOString();
  heading.append(node("span", "", event.kind.replaceAll("_", " ")), time);
  item.append(heading);
  const data = event.data;
  const summary =
    data.summary ||
    data.reason ||
    data.text ||
    data.objective ||
    (data.tool
      ? `${data.tool} · ${data.ok ? "recorded" : "returned an error"}`
      : data.action ||
        (data.children
          ? `${data.children.length} worker records`
          : "Checkpoint recorded"));
  item.append(node("p", "", summary));
  const details = node("details");
  details.append(
    node("summary", "", "View recorded data"),
    node("pre", "", JSON.stringify(data, null, 2)),
  );
  item.append(details);
  $("task-events").append(item);
  // Keep the visible journal bounded; complete history remains in SQLite.
  if ($("task-events").children.length > 300)
    $("task-events").firstElementChild.remove();
}
function openMission() {
  if (!profiles.length) {
    notice("Connect a model before launching your first mission.");
    showView("providers");
    openProvider();
    return;
  }
  $("mission-form").reset();
  $("mission-form-error").hidden = true;
  $("targets-field").hidden = true;
  $("m-targets").required = false;
  fillSelect("m-provider", profiles, $("provider-select").value);
  fillSelect("m-persona", personas, $("chat-persona").value);
  $("m-skills").replaceChildren(
    ...skills.map(
      (s) =>
        new Option(
          s.id,
          s.id,
          false,
          ["recon-scope-triage", "triage-validation"].includes(s.id),
        ),
    ),
  );
  $("mission-dialog").showModal();
}
$("m-network").onchange = () => {
  $("targets-field").hidden = !$("m-network").checked;
  $("m-targets").required = $("m-network").checked;
};
$("mission-form").onsubmit = async (event) => {
  event.preventDefault();
  $("launch-mission").disabled = true;
  $("mission-form-error").hidden = true;
  try {
    const selected = [...$("m-skills").selectedOptions].map((o) => o.value);
    if (selected.length > 12)
      throw new Error("Choose at most 12 skill modules.");
    const task = await api("/api/tasks", "POST", {
      objective: $("m-objective").value.trim(),
      workspace: $("m-workspace").value.trim(),
      provider_id: $("m-provider").value,
      persona_id: $("m-persona").value,
      skills: selected,
      network: $("m-network").checked,
      targets: $("m-network").checked
        ? $("m-targets")
            .value.split(/[\n,]+/)
            .map((t) => t.trim())
            .filter(Boolean)
        : [],
      max_workers: Number($("m-workers").value),
      max_steps: Number($("m-steps").value),
      token_budget: Number($("m-tokens").value),
    });
    $("mission-dialog").close();
    showView("missions");
    await refreshMissions();
    await selectTask(task.id);
    notice(
      "Mission launched. Eliot will keep working while this page is closed.",
    );
  } catch (e) {
    $("mission-form-error").textContent = e.message;
    $("mission-form-error").hidden = false;
  } finally {
    $("launch-mission").disabled = false;
  }
};
$("feedback-form").onsubmit = async (event) => {
  event.preventDefault();
  const text = $("task-feedback").value.trim(),
    id = selectedTask;
  if (!text || !id) return;
  const submit = event.submitter;
  submit.disabled = true;
  try {
    await api(`/api/tasks/${id}/feedback`, "POST", { text });
    if (selectedTask === id) $("task-feedback").value = "";
    await refreshTask();
    notice("Direction added to the mission record.");
  } catch (e) {
    notice(e.message, true);
  } finally {
    submit.disabled = false;
  }
};
for (const id of ["hero-mission", "new-mission"]) $(id).onclick = openMission;
for (const name of ["missions", "library"])
  $(name + "-nav").onclick = () => showView(name);
$("explore-skills").onclick = $("rail-skills").onclick = () => {
  showView("library");
  libraryTab("skills");
};
$("attention-button").onclick = () => {
  showView("missions");
  $("mission-filter").value = "attention";
  renderMissionList();
};
$("mission-search").oninput = renderMissionList;
$("mission-filter").onchange = renderMissionList;
$("refresh-missions").onclick = () =>
  refreshMissions().catch((e) => notice(e.message, true));
$("close-mission").onclick = () => {
  selectedTask = null;
  $("mission-detail").hidden = true;
  renderMissionList();
};
for (const b of document.querySelectorAll("[data-close]"))
  b.onclick = () => $(b.dataset.close).close();

function libraryTab(name) {
  for (const key of ["skills", "personas"]) {
    $(key + "-panel").hidden = key !== name;
    $(key + "-tab").classList.toggle("active", key === name);
    $(key + "-tab").setAttribute("aria-selected", String(key === name));
    $(key + "-tab").tabIndex = key === name ? 0 : -1;
  }
}
for (const name of ["skills", "personas"]) {
  $(name + "-tab").onclick = () => libraryTab(name);
  $(name + "-tab").onkeydown = (e) => {
    if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
      e.preventDefault();
      const next =
        e.key === "Home"
          ? "skills"
          : e.key === "End"
            ? "personas"
            : name === "skills"
              ? "personas"
              : "skills";
      libraryTab(next);
      $(next + "-tab").focus();
    }
  };
}
function renderSkills() {
  const q = $("skill-search").value.toLowerCase().replaceAll("-", " ").trim();
  const filtered = skills.filter((s) =>
    (s.id + " " + s.description).toLowerCase().replaceAll("-", " ").includes(q),
  );
  $("skill-results").textContent =
    `${filtered.length} of ${skills.length} installed modules · Claude-BugHunter`;
  $("skill-list").replaceChildren();
  if (!filtered.length) {
    $("skill-list").append(
      emptyState(
        "No matching skills",
        "Try a platform, vulnerability class or a shorter search.",
      ),
    );
    return;
  }
  for (const skill of filtered) {
    const card = button("", () => openSkill(skill));
    card.className = "skill-card";
    card.append(
      node("strong", "", skill.id.replaceAll("-", " ")),
      node("small", "", skill.description),
    );
    const footer = node("span");
    footer.append(node("span", "", "VERIFIED MODULE"), node("span", "", "↗"));
    card.append(footer);
    $("skill-list").append(card);
  }
}
$("skill-search").oninput = renderSkills;
async function openSkill(skill) {
  currentSkill = skill;
  $("skill-about").open = false;
  skillResource = "SKILL.md";
  $("skill-resource").replaceChildren();
  $("skill-resource-label").hidden = true;
  nextSkillLine = 1;
  skillGeneration++;
  $("skill-title").textContent = skill.id.replaceAll("-", " ");
  $("skill-description").textContent = skill.description;
  $("skill-revision").textContent = "PINNED / " + skill.revision.slice(0, 12);
  $("skill-source").href = skill.source;
  $("skill-content").textContent = "Loading verified guidance…";
  $("skill-more").hidden = true;
  $("skill-dialog").showModal();
  await loadSkillPage(true);
}
async function loadSkillPage(first = false) {
  const generation = skillGeneration;
  $("skill-more").disabled = true;
  try {
    const page = await api(
      `/api/skills/${encodeURIComponent(currentSkill.id)}?start_line=${nextSkillLine}&resource=${encodeURIComponent(skillResource)}`,
    );
    if (generation !== skillGeneration) return;
    if (first) {
      $("skill-content").textContent = page.text;
      $("skill-resource").replaceChildren(
        ...page.resources.map((resource) => {
          const option = node(
            "option",
            "",
            resource === "SKILL.md" ? "Main guide" : resource,
          );
          option.value = resource;
          return option;
        }),
      );
      $("skill-resource").value = skillResource;
      $("skill-resource-label").hidden = page.resources.length < 2;
      $("skill-content").scrollTop = 0;
    } else $("skill-content").textContent += "\n" + page.text;
    nextSkillLine = page.end_line + 1;
    $("skill-more").hidden = !page.has_more;
  } catch (e) {
    if (generation === skillGeneration) {
      if (first) $("skill-content").textContent = e.message;
      notice(e.message, true);
    }
  } finally {
    if (generation === skillGeneration) $("skill-more").disabled = false;
  }
}
$("skill-more").onclick = () => loadSkillPage();
$("skill-resource").onchange = () => {
  skillResource = $("skill-resource").value;
  nextSkillLine = 1;
  skillGeneration++;
  $("skill-content").textContent = "Loading verified guidance…";
  $("skill-more").hidden = true;
  loadSkillPage(true);
};
$("skill-dialog").addEventListener("close", () => skillGeneration++);
async function refreshPersonas() {
  personas = await api("/api/personas");
  $("persona-count").textContent = personas.length;
  fillSelect("chat-persona", personas);
  $("persona-list").replaceChildren();
  for (const p of personas) {
    const card = node("article", "provider-card");
    card.append(
      node("h3", "", p.name),
      node("p", "persona-excerpt", p.instructions),
    );
    const actions = node("div", "card-actions");
    actions.append(
      button("Use in conversation", () => {
        $("chat-persona").value = p.id;
        newChat();
        notice(p.name + " selected for new responses.");
      }),
    );
    if (p.id !== "eliot")
      actions.append(button("Edit persona", () => openPersona(p)));
    else actions.append(node("span", "badge", "Built-in · read-only"));
    card.append(actions);
    $("persona-list").append(card);
  }
}
function openPersona(p) {
  $("persona-form").reset();
  $("persona-id").disabled = !!p;
  $("persona-id").value = p?.id || "";
  $("persona-name").value = p?.name || "";
  $("persona-text").value = p?.instructions || "";
  $("persona-error").hidden = true;
  $("persona-dialog-title").textContent = p
    ? "Refine your persona."
    : "Make Eliot your own.";
  $("persona-dialog").showModal();
}
$("import-persona").onclick = () => openPersona();
$("persona-file").onchange = async () => {
  const file = $("persona-file").files[0];
  if (!file) return;
  try {
    if (file.size > 48000)
      throw new Error("Choose a text file smaller than 48 KB.");
    const text = await file.text();
    if (text.length > 12000)
      throw new Error("Persona text must be at most 12,000 characters.");
    $("persona-text").value = text;
  } catch (e) {
    $("persona-error").textContent = e.message;
    $("persona-error").hidden = false;
  }
};
$("persona-name").oninput = () => {
  if (!$("persona-id").disabled)
    $("persona-id").value = $("persona-name")
      .value.toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 64);
};
$("persona-form").onsubmit = async (event) => {
  event.preventDefault();
  $("save-persona").disabled = true;
  $("persona-error").hidden = true;
  try {
    await api(
      `/api/personas/${encodeURIComponent($("persona-id").value)}`,
      "PUT",
      { name: $("persona-name").value, instructions: $("persona-text").value },
    );
    $("persona-dialog").close();
    await refreshPersonas();
    libraryTab("personas");
    notice(
      "Persona saved. It is available for new conversations and missions.",
    );
  } catch (e) {
    $("persona-error").textContent = e.message;
    $("persona-error").hidden = false;
  } finally {
    $("save-persona").disabled = false;
  }
};
async function pollWorkspace() {
  if (polling || document.hidden) return;
  polling = true;
  try {
    if (!workspaceReady) {
      await init();
      return;
    }
    await refreshMissions();
    if (!$("missions-view").hidden) await refreshTask();
    setConnection(true);
  } catch (e) {
    setConnection(false);
  } finally {
    polling = false;
  }
}
async function initWorkspace() {
  skills = await api("/api/skills");
  $("skill-count").textContent = skills.length;
  $("rail-skill-count").textContent = skills.length;
  renderSkills();
  await refreshPersonas();
  await refreshMissions();
  setConnection(true);
}
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) pollWorkspace();
});
window.addEventListener("pagehide", () => {
  clearInterval(pollTimer);
  source?.close();
});
let resumeTask = null;
function openResume(task) {
  resumeTask = task;
  $("resume-steps").value = task.policy.max_steps;
  $("resume-tokens").value = task.policy.token_budget;
  $("resume-steps").disabled = $("resume-tokens").disabled = !!task.parent_id;
  $("resume-worker-note").hidden = !task.parent_id;
  $("resume-error").hidden = true;
  $("resume-dialog").showModal();
}
$("resume-form").onsubmit = async (event) => {
  event.preventDefault();
  $("resume-submit").disabled = true;
  $("resume-error").hidden = true;
  try {
    const body = resumeTask.parent_id
      ? {}
      : {
          max_steps: Number($("resume-steps").value),
          token_budget: Number($("resume-tokens").value),
        };
    await api(`/api/tasks/${resumeTask.id}/resume`, "POST", body);
    $("resume-dialog").close();
    await refreshTask();
    await refreshMissions();
    notice("Mission resumed from its saved context.");
  } catch (e) {
    $("resume-error").textContent = e.message;
    $("resume-error").hidden = false;
  } finally {
    $("resume-submit").disabled = false;
  }
};
function startWorkspacePolling() {
  clearInterval(pollTimer);
  pollTimer = setInterval(pollWorkspace, 3000);
}
window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  startWorkspacePolling();
  pollWorkspace();
  if (currentRun) {
    const article = $("messages").querySelector(`[data-run="${currentRun}"]`);
    if (article) watch(currentRun, article);
  }
});
startWorkspacePolling();
init();
