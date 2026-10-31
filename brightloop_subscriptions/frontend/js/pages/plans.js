/*
 * Billing Plans Page Controller
 * Manages recurring intervals (daily, weekly, monthly, yearly), minimum commitments,
 * validity dates, and lifecycle policies (auto-close, early close, pause, renew).
 */

const plansPage = {
  async load() {
    try {
      const res = await app.api("/api/plans");
      this.renderTable(res.plans || []);
    } catch (e) {
      console.error("Error loading plans:", e);
    }
  },

  renderTable(plans) {
    const tbody = document.getElementById("plans-table-body");
    if (!tbody) return;

    if (!plans.length) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--slate-400); padding: 32px;">No plans configured.</td></tr>`;
      return;
    }

    tbody.innerHTML = plans.map(p => {
      const policyBadges = [];
      if (p.allow_early_close) policyBadges.push(`<span class="status-pill status-draft" style="font-size: 11px;">Early Close</span>`);
      if (p.allow_pause) policyBadges.push(`<span class="status-pill status-paused" style="font-size: 11px;">Pause / Resume</span>`);
      if (p.allow_renew) policyBadges.push(`<span class="status-pill status-active" style="font-size: 11px;">Renew</span>`);

      const autoCloseBadge = p.auto_close
        ? `<span class="status-pill status-overdue">Auto-Close on End</span>`
        : `<span class="status-pill status-confirmed">Auto-Renews</span>`;

      return `
        <tr>
          <td>
            <div style="font-weight: 700; color: var(--slate-900); font-size: 14px;">${p.name}</div>
          </td>
          <td>
            <span class="status-pill status-confirmed" style="text-transform: capitalize; font-weight: 700;">
              ${p.billing_frequency}
            </span>
          </td>
          <td style="font-weight: 700; font-size: 14px;">$${Number(p.base_price).toFixed(2)}</td>
          <td>${p.min_quantity} seat(s)</td>
          <td style="font-size: 12.5px; color: var(--slate-600);">
            ${p.valid_from || '—'} &rarr; ${p.valid_to || 'Ongoing'}
          </td>
          <td>${autoCloseBadge}</td>
          <td>
            <div style="display: flex; gap: 4px; flex-wrap: wrap;">
              ${policyBadges.join("")}
            </div>
          </td>
        </tr>
      `;
    }).join("");
  },

  openNewPlanModal() {
    const today = new Date().toISOString().split("T")[0];

    const html = `
      <div class="form-group">
        <label class="form-label">Plan Name:</label>
        <input type="text" class="form-control" id="new-plan-name" placeholder="e.g. Quarterly Growth Tier">
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Billing Interval / Frequency:</label>
          <select class="form-control" id="new-plan-freq">
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly" selected>Monthly</option>
            <option value="yearly">Yearly</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Base Cost / Price ($):</label>
          <input type="number" class="form-control" id="new-plan-price" value="1200.00" step="50">
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Minimum Quantity / Commitment:</label>
          <input type="number" class="form-control" id="new-plan-min-qty" value="1" min="1">
        </div>
        <div class="form-group">
          <label class="form-label">Available From Date:</label>
          <input type="date" class="form-control" id="new-plan-valid-from" value="${today}">
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">Available Until Date:</label>
        <input type="date" class="form-control" id="new-plan-valid-to" value="2028-12-31">
      </div>

      <div style="background: var(--slate-50); border: 1px solid var(--slate-200); border-radius: var(--radius-md); padding: 14px; margin-top: 14px;">
        <div style="font-size: 13px; font-weight: 700; margin-bottom: 8px;">Plan Lifecycle Policies (Admin Configured):</div>
        
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <label style="display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer;">
            <input type="checkbox" id="policy-auto-close">
            <span><strong>Auto-close on end:</strong> Subscription ends permanently when expiry date arrives.</span>
          </label>
          <label style="display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer;">
            <input type="checkbox" id="policy-early-close" checked>
            <span>Allow subscribers to close early.</span>
          </label>
          <label style="display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer;">
            <input type="checkbox" id="policy-pause" checked>
            <span>Allow subscription to be paused and resumed.</span>
          </label>
          <label style="display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer;">
            <input type="checkbox" id="policy-renew" checked>
            <span>Allow subscription renewal.</span>
          </label>
        </div>
      </div>
    `;

    const footer = `
      <button class="btn btn-secondary" onclick="app.closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="plansPage.submitPlan()">Create Plan</button>
    `;

    app.openModal("Create Recurring Billing Plan", html, footer);
  },

  async submitPlan() {
    const name = document.getElementById("new-plan-name").value.trim();
    const freq = document.getElementById("new-plan-freq").value;
    const price = parseFloat(document.getElementById("new-plan-price").value) || 0;
    const minQty = parseInt(document.getElementById("new-plan-min-qty").value) || 1;
    const validFrom = document.getElementById("new-plan-valid-from").value;
    const validTo = document.getElementById("new-plan-valid-to").value;

    const autoClose = document.getElementById("policy-auto-close").checked;
    const earlyClose = document.getElementById("policy-early-close").checked;
    const pause = document.getElementById("policy-pause").checked;
    const renew = document.getElementById("policy-renew").checked;

    if (!name) {
      app.showToast("Plan name is required", "error");
      return;
    }

    try {
      await app.api("/api/plans", "POST", {
        name,
        billing_frequency: freq,
        base_price: price,
        min_quantity: minQty,
        valid_from: validFrom,
        valid_to: validTo,
        auto_close: autoClose,
        allow_early_close: earlyClose,
        allow_pause: pause,
        allow_renew: renew
      });

      app.showToast(`Billing plan "${name}" created!`, "success");
      app.closeModal();
      this.load();
    } catch (e) {
      // Handled
    }
  }
};

window.plansPage = plansPage;
