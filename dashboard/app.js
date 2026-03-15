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
      const lastSeen = agent.last_heartbeat
        ? new Date(agent.last_heartbeat).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
        : "—";
      return `
        <td>${agent.agent_id}</td>
        <td>${agent.public_key ? agent.public_key.substring(0, 12) + '...' : '—'}</td>
        <td>${agent.reputation_score?.toFixed(2) || '—'}</td>
        <td>${agent.tasks_completed || 0}</td>
        <td>${agent.success_rate ? (agent.success_rate * 100).toFixed(0) + '%' : '—'}</td>
        <td>${lastSeen}</td>
        <td>${agent.status || 'active'}</td>
      `;
    });

    // Recent Tasks
    setStatus("tasks-status", `${payload.recent_tasks?.length || 0} recent tasks`);
    renderTableBody("tasks-table", payload.recent_tasks || [], (task) => {
      const timestamp = task.timestamp
        ? new Date(task.timestamp).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
        : "—";
      return `
        <td>${task.task_id || '—'}</td>
        <td>${task.agent_id}</td>
        <td>${task.description || '—'}</td>
        <td>${task.result_status || 'unknown'}</td>
        <td>${task.execution_time ? task.execution_time.toFixed(1) : '—'}</td>
        <td>${timestamp}</td>
      `;
    });

    // Top Agents
    setStatus("top-status", `Top ${payload.top_agents?.length || 0} by reputation`);
    renderTableBody("top-table", payload.top_agents || [], (agent, index) => {
      return `
        <td>${index + 1}</td>
        <td>${agent.agent_id}</td>
        <td><strong>${agent.reputation_score?.toFixed(2) || '—'}</strong></td>
        <td>${agent.tasks_success || 0} / ${agent.tasks_total || '?'}</td>
        <td>${agent.last_task ? new Date(agent.last_task).toLocaleTimeString() : '—'}</td>
      `;
    });

    // Blocked Actions
    if (payload.recent_blocked_actions?.length > 0) {
      setStatus("blocked-status", `${payload.recent_blocked_actions.length} recent blocks`);
      renderTableBody("blocked-table", payload.recent_blocked_actions, (log) => {
        const time = log.timestamp
          ? new Date(log.timestamp).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
          : "—";
        return `
          <td>${time}</td>
          <td>${log.agent_id}</td>
          <td>${log.attempted_command || log.action_type || '—'}</td>
          <td>${log.blocked_reason || log.reason || 'Policy violation'}</td>
          <td>${log.severity || 'high'}</td>
        `;
      });
    } else {
      setStatus("blocked-status", "No blocked actions in recent logs");
      document.querySelector("#blocked-table tbody").innerHTML = "";
    }

  } catch (error) {
    console.error("Dashboard refresh failed:", error);
    setStatus("agents-status", "Unable to reach backend");
    setStatus("tasks-status", "Connection issue");
    setStatus("top-status", "Connection issue");
    setStatus("blocked-status", "Connection issue");
  }
};

// Carga inicial + refresh cada 15 segundos
refresh();
setInterval(refresh, 15000);
