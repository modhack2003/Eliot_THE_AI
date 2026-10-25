"use strict";
const $ = (id) => document.getElementById(id);
let token = "",
  profiles = [],
  currentSession = null,
  currentRun = null,
  source = null,
  sessions = [];
let noticeTimer,
  submitting = false;

async function api(path, method = "GET", body) {
  const options = { method, headers: { "X-Eliot-Token": token } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok)
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : "The request could not be completed.",
    );
  return value;
}
function notice(message, error = false) {
  clearTimeout(noticeTimer);
  $("notice").textContent = message;
  $("notice").classList.toggle("error", error);
  $("notice").hidden = false;
  noticeTimer = setTimeout(
    () => {
      $("notice").hidden = true;
    },
    error ? 15000 : 7000,
  );
}
function showView(name) {
  closeNavigation();
  const labels = {
    chat: "Command",
    missions: "Missions",
    library: "Skills & personas",
    providers: "Connections",
  };
  for (const key of Object.keys(labels)) {
    $(key + "-view").hidden = name !== key;
    $(key + "-nav").classList.toggle("active", name === key);
    if (name === key) $(key + "-nav").setAttribute("aria-current", "page");
    else $(key + "-nav").removeAttribute("aria-current");
  }
  $("page-label").textContent = labels[name];
  document.dispatchEvent(new Event("eliot-view"));
}
function button(label, action) {
  const el = document.createElement("button");
  el.type = "button";
  el.textContent = label;
  el.addEventListener("click", async () => {
    el.disabled = true;
    try {
      await action();
    } catch (e) {
      notice(e.message, true);
    } finally {
      el.disabled = false;
    }
  });
  return el;
}
async function refreshProviders() {
  const previous = $("provider-select").value;
  profiles = await api("/api/providers");
  $("provider-count").textContent = profiles.length;
  $("provider-select").replaceChildren();
  if (!profiles.length)
    $("provider-select").add(new Option("Connect a provider", ""));
  profiles.forEach((p) => $("provider-select").add(new Option(p.name, p.id)));
  $("provider-select").value = profiles.some((p) => p.id === previous)
    ? previous
    : profiles.find((p) => p.is_default)?.id || profiles[0]?.id || "";
  $("connect-provider").hidden = profiles.length > 0;
  modelName();
  renderProviders();
  updateComposer();
}
function modelName() {
  const profile = profiles.find((p) => p.id === $("provider-select").value);
  $("model-name").textContent = profile?.model || "";
  $("rail-model").textContent = profile?.model || "No model connected";
  $("rail-provider").textContent =
    profile?.name || "Choose a connection to begin";
}
async function refreshSessions() {
  sessions = await api("/api/sessions");
  $("session-count").textContent = sessions.length;
  $("sessions").replaceChildren();
  if (!sessions.length) {
    const p = document.createElement("p");
    p.className = "empty-history";
    p.textContent = "Your next investigation starts with a conversation.";
    $("sessions").append(p);
  }
  sessions.forEach((s) => {
    const el = button(s.title, () => loadSession(s.id));
    el.className = "session-item";
    el.classList.toggle("selected", s.id === currentSession);
    el.title = s.title;
    $("sessions").append(el);
  });
}
function detach() {
  if (source) source.close();
  source = null;
  currentRun = null;
}
function newChat() {
  if (submitting) return;
  detach();
  currentSession = null;
  $("messages").replaceChildren();
  $("welcome").hidden = false;
  $("export-session").hidden = true;
  $("delete-session").hidden = true;
  updateComposer();
  showView("chat");
  refreshSessions().catch((e) => notice(e.message, true));
  $("message").focus();
}
function addMessage(role, text, runId) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  if (runId) article.dataset.run = runId;
  const label = document.createElement("div");
  label.className = "message-label";
  const avatar = document.createElement("span");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "↗" : "e.";
  label.append(
    avatar,
    document.createTextNode(role === "user" ? "You" : "Eliot"),
  );
  const content = document.createElement("div");
  content.className = "message-content";
  content.textContent = text;
  article.append(label, content);
  $("messages").append(article);
  return article;
}
function renderRun(run, article) {
  article.querySelector(".message-content").textContent =
    run.text ||
    (run.status === "queued" || run.status === "running"
      ? "Thinking…"
      : "No response text.");
  article.querySelector(".message-error")?.remove();
  const warning =
    run.error ||
    (run.finish_reason === "length"
      ? "The model reached its output limit. You can ask it to continue."
      : run.finish_reason === "content_filter"
        ? "The provider stopped this response through its content filter."
        : "");
  if (warning) {
    const p = document.createElement("p");
    p.className = "message-error";
    p.textContent = warning;
    article.append(p);
  }
}
async function loadSession(id) {
  if (submitting) return;
  detach();
  currentSession = id;
  const session = await api(`/api/sessions/${id}`);
  if (currentSession !== id) return;
  $("welcome").hidden = true;
  $("messages").replaceChildren();
  const byId = new Map(session.runs.map((r) => [r.id, r]));
  session.messages.forEach((m) => {
    addMessage(m.role, m.content);
    if (m.role === "user") {
      const run = byId.get(m.run_id);
      if (run && run.status !== "completed") {
        const article = addMessage("assistant", run.text, run.id);
        renderRun(run, article);
      }
    }
  });
  const active = session.runs.find((r) =>
    ["queued", "running"].includes(r.status),
  );
  if (active) {
    currentRun = active.id;
    watch(active.id, $("messages").querySelector(`[data-run="${active.id}"]`));
  }
  const last = session.runs.at(-1);
  if (last && profiles.some((p) => p.id === last.provider_id))
    $("provider-select").value = last.provider_id;
  $("export-session").href = `/api/sessions/${id}/export`;
  $("export-session").hidden = false;
  $("delete-session").hidden = false;
  modelName();
  updateComposer();
  showView("chat");
  await refreshSessions();
  scrollBottom();
}
function scrollBottom() {
  $("conversation").scrollTop = $("conversation").scrollHeight;
}
function updateComposer() {
  const busy = !!currentRun || submitting;
  $("stop").hidden = !busy;
  $("send").disabled = busy || !profiles.length;
  $("message").disabled = busy;
  $("provider-select").disabled = busy;
  $("delete-session").disabled = busy;
  $("new-chat").disabled = submitting;
  $("chat-persona").disabled = busy;
  updateActivity();
  $("run-status").textContent = busy
    ? "Eliot is responding…"
    : profiles.length
      ? "Ready when you are"
      : "Connect a provider to begin";
}
function watch(id, article) {
  if (source) source.close();
  source = new EventSource(`/api/runs/${id}/events`);
  source.onmessage = (event) => {
    const run = JSON.parse(event.data);
    const nearBottom =
      $("conversation").scrollHeight -
        $("conversation").scrollTop -
        $("conversation").clientHeight <
      150;
    renderRun(run, article);
    if (nearBottom) scrollBottom();
    if (!["queued", "running"].includes(run.status)) {
      detach();
      updateComposer();
      refreshSessions().catch((e) => notice(e.message, true));
      $("message").focus();
    }
  };
  source.onerror = () => {
    source?.close();
    source = null;
    notice(
      "The live connection was interrupted. Refresh this conversation to check its status.",
      true,
    );
    updateComposer();
  };
}
$("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = $("message").value.trim();
  if (!content || currentRun || submitting) return;
  submitting = true;
  updateComposer();
  try {
    if (!currentSession)
      currentSession = (await api("/api/sessions", "POST", {})).id;
    const run = await api(`/api/sessions/${currentSession}/runs`, "POST", {
      content,
      provider_id: $("provider-select").value,
      persona_id: $("chat-persona").value,
    });
    $("message").value = "";
    $("welcome").hidden = true;
    addMessage("user", content);
    const article = addMessage("assistant", "Thinking…", run.id);
    currentRun = run.id;
    $("export-session").href = `/api/sessions/${currentSession}/export`;
    $("export-session").hidden = false;
    $("delete-session").hidden = false;
    updateComposer();
    watch(run.id, article);
    scrollBottom();
    await refreshSessions();
  } catch (e) {
    notice(e.message, true);
  } finally {
    submitting = false;
    updateComposer();
  }
});
$("message").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    $("chat-form").requestSubmit();
  }
});
$("stop").addEventListener("click", async () => {
  if (!currentRun) return;
  $("stop").disabled = true;
  try {
    await api(`/api/runs/${currentRun}/cancel`, "POST");
  } catch (e) {
    notice(e.message, true);
  } finally {
    $("stop").disabled = false;
  }
});
$("delete-session").addEventListener("click", async () => {
  if (
    !currentSession ||
    !(await confirmAction(
      "Delete conversation?",
      "This permanently deletes the conversation and its saved responses.",
      "Delete conversation",
    ))
  )
    return;
  try {
    await api(`/api/sessions/${currentSession}`, "DELETE");
    newChat();
  } catch (e) {
    notice(e.message, true);
  }
});
$("provider-select").addEventListener("change", modelName);
$("new-chat").addEventListener("click", newChat);
$("chat-nav").addEventListener("click", () => showView("chat"));
for (const id of ["providers-nav", "settings-link"])
  $(id).addEventListener("click", () => showView("providers"));
$("connect-provider").addEventListener("click", () => openProvider());
$("add-provider").addEventListener("click", () => openProvider());
$("refresh").addEventListener("click", () => {
  if (currentSession)
    loadSession(currentSession).catch((e) => notice(e.message, true));
  else refreshSessions().catch((e) => notice(e.message, true));
});
document.querySelectorAll("[data-prompt]").forEach((el) =>
  el.addEventListener("click", () => {
    $("message").value = el.dataset.prompt;
    $("message").focus();
  }),
);
document.addEventListener("keydown", (event) => {
  if (
    event.key === "n" &&
    !event.ctrlKey &&
    !event.metaKey &&
    !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) &&
    !document.querySelector("dialog[open]")
  ) {
    event.preventDefault();
    newChat();
  }
});

function renderProviders() {
  $("provider-cards").replaceChildren();
  if (!profiles.length) {
    const empty = document.createElement("div");
    empty.className = "empty-providers";
    empty.textContent =
      "Start with the model you already use. Add its API address, model ID, and key reference — or connect a local server without a key.";
    $("provider-cards").append(empty);
  }
  profiles.forEach((p) => {
    const card = document.createElement("article");
    card.className = "provider-card";
    const name = document.createElement("h3");
    name.textContent = p.name;
    const model = document.createElement("p");
    model.textContent = p.model;
    const endpoint = document.createElement("p");
    endpoint.className = "endpoint";
    endpoint.textContent = p.base_url;
    const badges = document.createElement("div");
    badges.className = "badges";
    [
      p.is_default ? "Default provider" : null,
      p.auth === "none"
        ? "No key required"
        : p.key_configured
          ? p.temporary_key
            ? "Temporary key set"
            : "Environment key set"
          : "Key needed",
      p.streaming ? "Streaming" : "Standard response",
    ]
      .filter(Boolean)
      .forEach((label) => {
        const badge = document.createElement("span");
        badge.className = "badge" + (label === "Key needed" ? " needed" : "");
        badge.textContent = label;
        badges.append(badge);
      });
    const actions = document.createElement("div");
    actions.className = "card-actions";
    actions.append(
      button("Edit", () => openProvider(p)),
      button("Test connection ↗", async () => {
        await api(`/api/providers/${p.id}/test`, "POST");
        notice(p.name + " connected successfully.");
      }),
    );
    if (!p.is_default)
      actions.append(
        button("Make default", async () => {
          await api(`/api/providers/${p.id}/default`, "POST");
          await refreshProviders();
        }),
      );
    if (p.temporary_key)
      actions.append(
        button("Forget temporary key", async () => {
          await api(`/api/providers/${p.id}/key`, "DELETE");
          await refreshProviders();
        }),
      );
    actions.append(
      button("Remove", async () => {
        if (
          !(await confirmAction(
            "Remove connection?",
            `Remove the ${p.name} profile? Conversation history will remain.`,
            "Remove connection",
          ))
        )
          return;
        await api(`/api/providers/${p.id}`, "DELETE");
        await refreshProviders();
      }),
    );
    card.append(name, model, endpoint, badges, actions);
    $("provider-cards").append(card);
  });
}
function openProvider(p) {
  $("provider-form").reset();
  $("p-id").disabled = !!p;
  $("form-error").hidden = true;
  $("dialog-title").textContent = p
    ? "Refine the connection."
    : "Make a connection.";
  $("p-name").value = p?.name || "";
  $("p-id").value = p?.id || "";
  $("p-url").value = p?.base_url || "";
  $("p-model").value = p?.model || "";
  $("p-env").value = p?.api_key_env || "ELIOT_API_KEY";
  $("p-auth").value = p?.auth || "bearer";
  $("p-stream").checked = p?.streaming ?? true;
  $("p-timeout").value = p?.timeout_seconds || 60;
  $("p-retries").value = p?.max_retries ?? 1;
  $("p-parameters").value = JSON.stringify(p?.parameters || {}, null, 2);
  $("provider-dialog").showModal();
}
for (const id of ["close-dialog", "cancel-dialog"])
  $(id).addEventListener("click", () => $("provider-dialog").close());
$("p-name").addEventListener("input", () => {
  if (!$("p-id").disabled)
    $("p-id").value = $("p-name")
      .value.toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 64);
});
$("provider-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("save-provider").disabled = true;
  $("form-error").hidden = true;
  try {
    let parameters;
    try {
      parameters = JSON.parse($("p-parameters").value || "{}");
    } catch {
      throw new Error("Generation parameters must be a valid JSON object.");
    }
    const id = $("p-id").value;
    await api(`/api/providers/${id}`, "PUT", {
      id,
      name: $("p-name").value.trim(),
      base_url: $("p-url").value.trim(),
      model: $("p-model").value.trim(),
      api_key_env: $("p-env").value.trim(),
      auth: $("p-auth").value,
      streaming: $("p-stream").checked,
      timeout_seconds: Number($("p-timeout").value),
      max_retries: Number($("p-retries").value),
      parameters,
    });
    if ($("p-key").value.trim())
      await api(`/api/providers/${id}/key`, "PUT", {
        api_key: $("p-key").value.trim(),
      });
    $("p-key").value = "";
    $("provider-dialog").close();
    await refreshProviders();
    notice(
      "Provider saved. Use Test connection when you’re ready to send a short test request.",
    );
  } catch (e) {
    $("form-error").textContent = e.message;
    $("form-error").hidden = false;
  } finally {
    $("save-provider").disabled = false;
  }
});
$("provider-dialog").addEventListener("close", () => {
  $("p-key").value = "";
});
async function init() {
  try {
    const state = await api("/api/bootstrap");
    token = state.token;
    $("version").textContent = "Eliot " + state.version;
    await refreshProviders();
    await refreshSessions();
    await initWorkspace();
  } catch (e) {
    setConnection(false);
    notice("Could not open the workspace. " + e.message, true);
  }
}
// workspace.js starts initialization after registering the mission and library controls.
