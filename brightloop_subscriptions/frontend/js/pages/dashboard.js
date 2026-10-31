/*
 * Dashboard View Controller
 * Loads executive financial summary, aging schedule, and recent subscriptions.
 */

const dashboardPage = {
  async load() {
    try {
      const [summaryRes, agingRes, subsRes] = await Promise.all([
        app.api("/api/reports/summary"),
        app.api("/api/reports/aging"),
        app.api("/api/subscriptions?limit=6")
      ]);

      this.renderKPIs(summaryRes);
      this.renderAging(agingRes.aging_report);
      this.renderRecentSubs(subsRes.subscriptions || []);

      // Update sidebar badges
      const badgeSubs = document.getElementById("badge-active-subs");
      if (badgeSubs) badgeSubs.textContent = summaryRes.active_subscriptions;

      const badgeOverdue = document.getElementById("badge-overdue-invoices");
      if (badgeOverdue) badgeOverdue.textContent = summaryRes.overdue_invoices_count;
    } catch (e) {
      console.error("Error loading dashboard:", e);
    }
  },

  renderKPIs(data) {
    document.getElementById("kpi-active-subs").textContent = data.active_subscriptions || 0;
    document.getElementById("kpi-mrr").textContent = `$${Number(data.mrr || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    document.getElementById("kpi-arr").textContent = `$${Number(data.arr || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    document.getElementById("kpi-collected").textContent = `$${Number(data.total_revenue_collected || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    document.getElementById("kpi-overdue").textContent = `$${Number(data.overdue_invoices_amount || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    document.getElementById("kpi-overdue-count").textContent = `${data.overdue_invoices_count || 0} overdue invoices`;
  },

  renderAging(aging) {
    if (!aging) return;
    document.getElementById("aging-current").textContent = `$${Number(aging.current || 0).toLocaleString(undefined, {minimumFractionDigits: 2})}`;
    document.getElementById("aging-1-30").textContent = `$${Number(aging["1_to_30_days"] || 0).toLocaleString(undefined, {minimumFractionDigits: 2})}`;
    document.getElementById("aging-31-60").textContent = `$${Number(aging["31_to_60_days"] || 0).toLocaleString(undefined, {minimumFractionDigits: 2})}`;
    document.getElementById("aging-60-plus").textContent = `$${Number(aging["over_60_days"] || 0).toLocaleString(undefined, {minimumFractionDigits: 2})}`;
  },

  renderRecentSubs(subs) {
    const tbody = document.getElementById("dashboard-recent-subs");
    if (!tbody) return;

    if (!subs.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--slate-400); padding: 24px;">No subscriptions recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = subs.map(sub => `
      <tr>
        <td style="font-weight: 600; color: var(--slate-900);">${sub.sub_number}</td>
        <td>
          <div style="font-weight: 600;">${sub.customer_name}</div>
          <div style="font-size: 11.5px; color: var(--slate-500);">${sub.customer_company || ''}</div>
        </td>
        <td>${sub.plan_name}</td>
        <td>${sub.next_billing_date || '—'}</td>
        <td><span class="status-pill status-${sub.status}">${sub.status}</span></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="subscriptionsPage.viewDetails(${sub.id})">Details</button>
        </td>
      </tr>
    `).join("");
  }
};

window.dashboardPage = dashboardPage;
