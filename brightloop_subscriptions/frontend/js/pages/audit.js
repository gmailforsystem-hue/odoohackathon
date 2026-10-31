/**
 * Audit & Benchmark Page Controller
 * Displays immutable system event audit trail and scale-up stress tester proving sub-2s query latency.
 */

const auditPage = {
  async load() {
    try {
      const res = await app.api("/api/audit/logs");
      this.renderTable(res.audit_logs || []);
    } catch (e) {
      console.error("Error loading audit logs:", e);
    }
  },

  renderTable(logs) {
    const tbody = document.getElementById("audit-table-body");
    if (!tbody) return;

    if (!logs.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--slate-400); padding: 32px;">No audit events recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(l => {
      const dateFormatted = l.timestamp ? l.timestamp.replace("T", " ").substring(0, 19) : "—";
      return `
        <tr>
          <td style="font-size: 12px; color: var(--slate-500); white-space: nowrap;">${dateFormatted}</td>
          <td style="font-weight: 600;">${l.user_email || 'system'}</td>
          <td>
            <span class="status-pill status-confirmed" style="font-size: 11px;">${l.action}</span>
          </td>
          <td style="text-transform: capitalize; font-weight: 600;">${l.entity_type} ${l.entity_id ? `(#${l.entity_id})` : ''}</td>
          <td style="font-size: 13px; color: var(--slate-700);">${l.details || '—'}</td>
        </tr>
      `;
    }).join("");
  }
};

window.auditPage = auditPage;
