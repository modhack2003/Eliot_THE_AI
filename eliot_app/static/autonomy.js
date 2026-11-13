"use strict";
(function () {
  const el = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const link = (label, href) => {
    const a = el("a", label, "text-button"); a.href = href; a.target = "_blank"; a.rel = "noopener"; return a;
  };
  const section = (title) => {
    const item = el("section", undefined, "autonomy-section"); item.append(el("h3", title)); return item;
  };
  let memoryTask = null;
  document.addEventListener("eliot-task", (event) => {
    const task = event.detail;
    const panel = $("task-autonomy"); panel.replaceChildren();
    const metrics = section("Mission outcomes");
    const data = task.metrics || {};
    metrics.append(el("p", `${data.model_calls || 0} model calls · ${data.tool_calls || 0} tool calls · ${Math.round(data.model_seconds || 0)}s model time · ${data.cost_known ? "$" + data.cost_usd.toFixed(4) : "Cost unavailable for unpriced or unmeasured calls"}`));
    metrics.append(link("Export complete mission", `/api/tasks/${task.id}/export`));
    const repeat = button("Schedule this mission", () => {
      $("schedule-definition").value = JSON.stringify({name:task.objective.slice(0,100),interval_seconds:86400,task:{objective:task.objective,workspace:task.workspace,provider_id:task.provider_id,skills:task.skills,network:task.policy.network,targets:task.policy.targets,options:Object.fromEntries(Object.entries(task.policy).filter(([key]) => !["network","targets","max_steps","token_budget","max_workers"].includes(key))),success_checks:task.state.success_checks||[]}}, null, 2);
      $("schedule-form").closest("details").open = true; $("schedule-definition").focus();
    });
    metrics.append(repeat);
    if (["paused","blocked"].includes(task.status)) metrics.append(button("Rebind current provider and resume", async () => {
      await api(`/api/tasks/${task.id}/resume`, "POST", {rebind_provider:true}); await refreshTask();
    }));
    panel.append(metrics);
    const plan = section("Plan and success checks");
    const steps = task.state.plan_steps || [];
    if (!steps.length) plan.append(el("p", "The agent has not recorded a structured plan yet."));
    const list = el("ol", undefined, "plan-steps");
    for (const step of steps) {
      const row = el("li"); row.dataset.status = step.status;
      row.append(el("strong", step.objective), el("span", step.status, "badge"));
      if (step.depends_on.length) row.append(el("small", "After: " + step.depends_on.join(", ")));
      if (step.expected_output) row.append(el("p", step.expected_output));
      if (step.evidence.length) row.append(el("small", "Evidence: " + step.evidence.join(", ")));
      list.append(row);
    }
    plan.append(list);
    for (const check of task.state.success_checks || []) plan.append(el("p", check.description || `${check.kind}: ${check.path || check.tool}`));
    panel.append(plan);
    const artifacts = section("Artifacts"); artifacts.append(el("p", "Loading artifacts…")); panel.append(artifacts);
    api(`/api/tasks/${task.id}/artifacts`).then(items => {
      if (selectedTask !== task.id) return;
      artifacts.replaceChildren(el("h3", "Artifacts"));
      if (!items.length) artifacts.append(el("p", "No report artifacts recorded yet."));
      for (const item of items) artifacts.append(link(item.path, `/api/tasks/${task.id}/artifact?path=${encodeURIComponent(item.path)}`));
    }).catch(error => { artifacts.append(el("p", error.message)); });
    const memory = section("Project memory");
    const query = el("input"); query.placeholder = "Search source-backed facts"; query.setAttribute("aria-label", "Search project memory");
    const results = el("div"); memory.append(query, button("Search memory", loadMemory), results); panel.append(memory);
    let generation = 0;
    async function loadMemory() {
      const current = ++generation;
      const record = await api(`/api/tasks/${task.id}/memory?query=${encodeURIComponent(query.value)}`);
      if (selectedTask !== task.id || current !== generation) return;
      results.replaceChildren();
      if (!record.memories.length) results.append(el("p", "No matching facts."));
      for (const fact of record.memories) {
        const row = el("article", undefined, "memory-fact");
        row.append(el("p", fact.text), el("small", `Source ${fact.source} · confidence ${fact.confidence}`), button("Forget", async () => {
          await api(`/api/tasks/${task.id}/memory/${fact.id}`, "DELETE"); await loadMemory();
        })); results.append(row);
      }
    }
    loadMemory().catch(error => notice(error.message, true));
  });

  let scheduleLoading = false;
  async function loadSchedules() {
    if (scheduleLoading) return;
    scheduleLoading = true;
    try {
      const [schedules, capabilities] = await Promise.all([api("/api/schedules"), api("/api/capabilities")]);
      $("schedule-list").replaceChildren();
      for (const item of schedules) {
        const row = el("article", undefined, "schedule-card");
        row.append(el("strong", item.name), el("p", `${item.enabled ? "Enabled" : "Disabled"} · ${item.trigger || (item.interval_seconds ? "Every " + item.interval_seconds + " seconds" : "Once")} · ${new Date(item.next_run * 1000).toLocaleString()}`));
        if (item.last_error) row.append(el("p", item.last_error));
        row.append(button(item.enabled ? "Disable" : "Enable", async () => { await api(`/api/schedules/${item.id}/enabled`, "POST", {enabled:!item.enabled}); await loadSchedules(); }), button("Delete", async () => { await api(`/api/schedules/${item.id}`, "DELETE"); await loadSchedules(); }));
        $("schedule-list").append(row);
      }
      $("agent-capabilities").replaceChildren(el("p", capabilities.map(item => `${item.name}${item.available ? "" : " (dependency needed)"}`).join(" · ")));
    } finally { scheduleLoading = false; }
  }
  $("refresh-schedules").onclick = () => loadSchedules().catch(error => notice(error.message, true));
  $("schedule-form").onsubmit = async (event) => {
    event.preventDefault();
    try { await api("/api/schedules", "POST", JSON.parse($("schedule-definition").value)); await loadSchedules(); notice("Schedule created."); }
    catch (error) { notice(error.message, true); }
  };
  document.addEventListener("eliot-view", () => {
    if (!$("missions-view").hidden) loadSchedules().catch(error => notice(error.message, true));
  });
  let historyOffset = 200;
  $("older-missions").onclick = async () => {
    try {
      const page = await api(`/api/tasks?limit=200&offset=${historyOffset}`); historyOffset += page.length;
      const known = new Set(missions.map(item => item.id)); missions.push(...page.filter(item => !known.has(item.id))); renderMissionList();
      $("older-missions").hidden = page.length < 200;
    } catch (error) { notice(error.message, true); }
  };

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  $("voice-input").disabled = !Recognition;
  $("voice-input").title = Recognition ? "Dictate using your browser's speech service" : "Speech recognition is unavailable in this browser";
  $("voice-input").onclick = () => {
    if (recognition) { recognition.stop(); return; }
    recognition = new Recognition(); recognition.lang = navigator.language || "en-IN"; recognition.interimResults = false;
    recognition.onresult = event => { $("message").value += ( $("message").value ? " " : "" ) + event.results[0][0].transcript; $("message").focus(); };
    recognition.onend = () => { recognition = null; $("voice-input").textContent = "Microphone"; };
    recognition.onerror = event => notice("Speech input: " + event.error, true);
    recognition.start(); $("voice-input").textContent = "Stop microphone";
  };
  $("voice-output").disabled = !("speechSynthesis" in window);
  $("voice-output").onclick = () => {
    const messages = document.querySelectorAll(".message.assistant .message-content");
    const text = messages[messages.length - 1]?.textContent;
    if (!text || !window.speechSynthesis) return;
    speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(text); utterance.onend = () => { $("voice-stop").hidden = true; };
    speechSynthesis.speak(utterance); $("voice-stop").hidden = false;
  };
  $("voice-stop").onclick = () => { speechSynthesis.cancel(); recognition?.abort(); $("voice-stop").hidden = true; };
})();
