const BACKEND_URL =
  window.location && window.location.origin && window.location.origin !== "null"
    ? window.location.origin
    : "http://127.0.0.1:8000";

const setStatus = (elementId, text) => {
  const el = document.getElementById(elementId);
  if (el) el.textContent = text;
};

const renderTableBody = (tableId, items, rowFormatter) => {
  const tbody = document.querySelector(`#${tableId} tbody`);
  if (!tbody) return;
  tbody.innerHTML = "";
  if (!items || items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color:#9ca3af; padding:2rem;">No data available</td></tr>';
    return;
  }
  items.forEach((item) => {
    const tr = document.createElement("tr");
    tr.innerHTML = rowFormatter(item);
    tbody.appendChild(tr);
  });
};

const fmt = {
  dt(value) {
    if (!value) return "—";
    try {
      return new Date(value).toLocaleString([], { dateStyle: "short", timeStyle: "short" });
    } catch {
      return "—";
    }
  },
  n(value, digits = 2) {
    if (value === null || value === undefined) return "—";
    const num = Number(value);
    if (Number.isNaN(num)) return "—";
    return num.toFixed(digits);
  },
  pct(value) {
    if (value === null || value === undefined) return "—";
    const num = Number(value);
    if (Number.isNaN(num)) return "—";
    return `${Math.round(num * 100)}%`;
  },
  short(text, n = 12) {
    if (!text) return "—";
    return text.length > n ? `${text.slice(0, n)}…` : text;
  },
};

const identityLink = (avid) => {
  if (!avid) return "—";
  const url = `/agents/identity/${encodeURIComponent(avid)}`;
  return `<a href="${url}" target="_blank" rel="noreferrer">open</a>`;
};

const refresh = async () => {
  try {
    const response = await fetch(`${BACKEND_URL}/dashboard/summary`);
    if (!response.ok) {
      throw new Error(`Backend error: ${response.status}`);
    }
    const payload = await response.json();

    // Agents Overview
    setStatus("agents-status", `${payload.total_agents || 0} agents registered`);
    setStatus("active-count", `${payload.active_agent_count || 0} active (last 5 min)`);

    renderTableBody("active-table", payload.active_agents || [], (agent) => {
      return `
        <td>${agent.name || "—"}</td>
        <td>${agent.avid ? `<code>${fmt.short(agent.avid, 18)}</code>` : "—"}</td>
        <td>${fmt.n(agent.reputation_score, 2)}</td>
        <td>${fmt.n(agent.reputation_effective, 4)}</td>
        <td>${agent.tasks_completed ?? 0}</td>
        <td>${fmt.pct(agent.success_rate)}</td>
        <td>${agent.blocked_action_count ?? 0}</td>
        <td>${agent.invalid_signature_count ?? 0}</td>
        <td>${fmt.dt(agent.last_heartbeat)}</td>
      `;
    });

    // Recent Tasks
    setStatus("tasks-status", `${payload.recent_tasks?.length || 0} recent tasks`);
    renderTableBody("tasks-table", payload.recent_tasks || [], (task) => {
      return `
        <td>${task.task_id || '—'}</td>
        <td>${task.avid ? `<code>${fmt.short(task.avid, 18)}</code>` : "—"}</td>
        <td>${task.description || '—'}</td>
        <td>${task.result_status || 'unknown'}</td>
        <td>${task.execution_time ? task.execution_time.toFixed(1) : '—'}</td>
        <td>${fmt.dt(task.logged_at)}</td>
      `;
    });

    // Top Agents
    setStatus("top-status", `Top ${payload.top_agents?.length || 0} by reputation`);
    renderTableBody("top-table", payload.top_agents || [], (agent, index) => {
      return `
        <td>${index + 1}</td>
        <td>${agent.name || "—"}</td>
        <td>${agent.avid ? `<code>${fmt.short(agent.avid, 18)}</code>` : "—"}</td>
        <td><strong>${fmt.n(agent.reputation_effective, 4)}</strong></td>
        <td>${fmt.n(agent.last_30d_delta, 2)}</td>
        <td>${fmt.pct(agent.success_rate)}</td>
        <td>${fmt.dt(agent.last_task_at)}</td>
      `;
    });

    // Blocked Actions
    if (payload.recent_blocked_actions?.length > 0) {
      setStatus("blocked-status", `${payload.recent_blocked_actions.length} recent blocks`);
      renderTableBody("blocked-table", payload.recent_blocked_actions, (log) => {
        return `
          <td>${fmt.dt(log.timestamp)}</td>
          <td>${log.avid ? `<code>${fmt.short(log.avid, 18)}</code>` : "—"}</td>
          <td>${log.attempted_command || log.action_type || '—'}</td>
          <td>${log.blocked_reason || log.reason || 'Policy violation'}</td>
          <td>${log.severity || 'high'}</td>
        `;
      });
    } else {
      setStatus("blocked-status", "No blocked actions in recent logs");
      document.querySelector("#blocked-table tbody").innerHTML = "";
    }

    // Top Blocked Reasons
    const reasons = payload.top_blocked_reasons || [];
    setStatus("blocked-reasons-status", `Top ${reasons.length || 0} reasons`);
    renderTableBody("blocked-reasons-table", reasons, (row) => {
      return `<td>${row.reason || "Unknown"}</td><td>${row.count ?? 0}</td>`;
    });

  } catch (error) {
    console.error("Dashboard refresh failed:", error);
    setStatus("agents-status", "Unable to reach backend");
    setStatus("tasks-status", "Connection issue");
    setStatus("top-status", "Connection issue");
    setStatus("blocked-status", "Connection issue");
    setStatus("verified-status", "Connection issue");
    setStatus("events-status", "Connection issue");
    setStatus("blocked-reasons-status", "Connection issue");
  }
};

const refreshVerified = async () => {
  const capability = document.getElementById("filter-capability")?.value?.trim();
  const minReputationRaw = document.getElementById("filter-min-reputation")?.value?.trim();
  const activeOnly = Boolean(document.getElementById("filter-active-only")?.checked);
  const minReputation = minReputationRaw ? Number(minReputationRaw) : 0;

  try {
    const params = new URLSearchParams();
    if (capability) params.set("capability", capability);
    if (!Number.isNaN(minReputation) && minReputation > 0) params.set("min_reputation", String(minReputation));
    if (activeOnly) params.set("active_only", "true");

    const res = await fetch(`${BACKEND_URL}/agents/verified?${params.toString()}`);
    if (!res.ok) throw new Error(`verified backend error: ${res.status}`);
    const rows = await res.json();
    setStatus("verified-status", `${rows.length || 0} verified agents`);
    renderTableBody("verified-table", rows, (a) => {
      const caps = Array.isArray(a.capabilities) ? a.capabilities.map((c) => c.name || c).join(", ") : "—";
      return `
        <td>${a.agent_name || "—"}</td>
        <td>${a.avid ? `<code>${fmt.short(a.avid, 18)}</code>` : "—"}</td>
        <td>${a.verification_level || "—"}${a.active ? " (active)" : ""}</td>
        <td>${fmt.n(a.reputation_score, 2)}</td>
        <td>${a.tasks_completed ?? 0}</td>
        <td>${fmt.dt(a.last_heartbeat_at)}</td>
        <td>${caps || "—"}</td>
        <td>${identityLink(a.avid)}</td>
      `;
    });
  } catch (e) {
    console.error("Verified refresh failed:", e);
    setStatus("verified-status", "Unable to load verified agents");
  }
};

let _events = [];
const renderEvents = () => {
  renderTableBody("events-table", _events.slice(-200).reverse(), (evt) => {
    const details = evt.data ? `<code>${fmt.short(JSON.stringify(evt.data), 80)}</code>` : "—";
    const avid = evt.data?.avid || evt.data?.from_avid || evt.data?.to_avid || "";
    return `
      <td>${fmt.dt(evt.time)}</td>
      <td>${evt.event || "message"}</td>
      <td>${avid ? `<code>${fmt.short(avid, 18)}</code>` : "—"}</td>
      <td>${details}</td>
    `;
  });
};

const safeJson = (value) => {
  try {
    return typeof value === "string" ? JSON.parse(value) : value;
  } catch {
    return { raw: value };
  }
};

const startSSE = () => {
  const el = document.getElementById("events-status");
  if (!el) return;
  try {
    const es = new EventSource(`${BACKEND_URL}/events`);
    setStatus("events-status", "Connected");
    es.onmessage = (msg) => {
      _events.push({ time: new Date().toISOString(), event: "message", data: safeJson(msg.data) });
      renderEvents();
    };
    es.addEventListener("agent_registered", (e) => {
      _events.push({ time: new Date().toISOString(), event: "agent_registered", data: safeJson(e.data) });
      renderEvents();
    });
    es.addEventListener("task_completed", (e) => {
      _events.push({ time: new Date().toISOString(), event: "task_completed", data: safeJson(e.data) });
      renderEvents();
    });
    es.addEventListener("reputation_updated", (e) => {
      _events.push({ time: new Date().toISOString(), event: "reputation_updated", data: safeJson(e.data) });
      renderEvents();
    });
    es.addEventListener("constitution_event", (e) => {
      _events.push({ time: new Date().toISOString(), event: "constitution_event", data: safeJson(e.data) });
      renderEvents();
    });
    es.addEventListener("a2a_message_sent", (e) => {
      _events.push({ time: new Date().toISOString(), event: "a2a_message_sent", data: safeJson(e.data) });
      renderEvents();
    });
    es.onerror = () => setStatus("events-status", "Disconnected (retrying)...");
  } catch (e) {
    setStatus("events-status", "SSE not available");
  }
};

// Carga inicial + refresh cada 15 segundos
refresh();
refreshVerified();
startSSE();
setInterval(refresh, 15000);

document.getElementById("filter-apply")?.addEventListener("click", refreshVerified);
