/**
 * Subscriptions Page Controller
 * Manages subscription lifecycle transitions, search/filtering, line items, and add-on toggling.
 */

const subscriptionsPage = {
  currentFilter: "",
  searchQuery: "",
  initialized: false,
  searchTimer: null,

  init() {
    if (this.initialized) return;
    this.initialized = true;

    // Setup filter pills
    const container = document.getElementById("sub-status-filters");
    if (container) {
      container.querySelectorAll(".filter-pill").forEach(pill => {
        pill.addEventListener("click", () => {
          container.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
          pill.classList.add("active");
          const nextFilter = pill.getAttribute("data-status") || "";
          if (this.currentFilter !== nextFilter) {
            this.currentFilter = nextFilter;
            this.load();
          }
        });
      });
    }

    // Setup search
    const searchInput = document.getElementById("sub-search-input");
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        clearTimeout(this.searchTimer);
        const val = e.target.value.trim();
        this.searchTimer = setTimeout(() => {
          if (this.searchQuery !== val) {
            this.searchQuery = val;
            this.load();
          }
        }, 350);
      });
    }
  },

  async load() {
    this.init();
    try {
      let url = "/api/subscriptions?limit=100";
      if (this.currentFilter) url += `&status=${this.currentFilter}`;
      if (this.searchQuery) url += `&search=${encodeURIComponent(this.searchQuery)}`;

      const res = await app.api(url);
      this.renderTable(res.subscriptions || []);
    } catch (e) {
      console.error("Error loading subscriptions:", e);
    }
  },

  renderTable(subs) {
    const tbody = document.getElementById("subscriptions-table-body");
    if (!tbody) return;

    if (!subs.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--slate-400); padding: 32px;">No subscriptions match current criteria.</td></tr>`;
      return;
    }

    tbody.innerHTML = subs.map(s => `
      <tr>
        <td style="font-weight: 700; color: var(--slate-900);">${s.sub_number}</td>
        <td>
          <div style="font-weight: 600;">${s.customer_name}</div>
          <div style="font-size: 11.5px; color: var(--slate-500);">${s.customer_company || ''} &bull; ${s.customer_email}</div>
        </td>
        <td>${s.plan_name}</td>
        <td style="text-transform: capitalize;">${s.billing_frequency}</td>
        <td>${s.start_date}</td>
        <td><strong>${s.next_billing_date || '—'}</strong></td>
        <td><span class="status-pill status-${s.status}">${s.status}</span></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="subscriptionsPage.viewDetails(${s.id})">Manage</button>
        </td>
      </tr>
    `).join("");
  },

  async viewDetails(subId) {
    try {
      const res = await app.api(`/api/subscriptions/${subId}`);
      const sub = res.subscription;

      const linesHtml = (sub.lines || []).map(l => {
        const isAddon = l.is_addon === 1;
        const addonToggle = isAddon ? `
          <label class="switch" title="Toggle add-on on/off">
            <input type="checkbox" ${l.addon_active ? 'checked' : ''} onchange="subscriptionsPage.toggleAddon(${sub.id}, ${l.id}, this.checked)">
            <span class="slider"></span>
          </label>
        ` : `<span style="color: var(--slate-400); font-size: 11px;">Core</span>`;

        return `
          <tr>
            <td>
              <div style="font-weight: 600;">${l.product_name}</div>
              ${l.variant_name ? `<div style="font-size: 11.5px; color: #2563eb;">Variant: ${l.variant_name} (+${l.price_surcharge > 0 ? '$' + l.price_surcharge : 'Included'})</div>` : ''}
            </td>
            <td>${l.quantity}</td>
            <td>$${Number(l.unit_price).toFixed(2)}</td>
            <td>${l.tax_name ? `${l.tax_name} (${l.tax_rate}%)` : 'None'}</td>
            <td style="font-weight: 600;">$${Number(l.line_amount).toFixed(2)}</td>
            <td style="text-align: center;">${addonToggle}</td>
          </tr>
        `;
      }).join("");

      const modalHtml = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--slate-200);">
          <div>
            <div style="font-size: 18px; font-weight: 800; color: var(--slate-900);">${sub.sub_number}</div>
            <div style="font-size: 12.5px; color: var(--slate-500);">${sub.customer_name} &bull; ${sub.customer_company || ''}</div>
          </div>
          <span class="status-pill status-${sub.status}" style="font-size: 13px; padding: 4px 12px;">${sub.status.toUpperCase()}</span>
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; background: var(--slate-50); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--slate-200); margin-bottom: 20px;">
          <div><div class="form-hint">Plan</div><div style="font-weight: 600;">${sub.plan_name} (${sub.billing_frequency})</div></div>
          <div><div class="form-hint">Payment Terms</div><div style="font-weight: 600;">${sub.payment_terms || 'Net 30'}</div></div>
          <div><div class="form-hint">Next Billing Day</div><div style="font-weight: 700; color: #2563eb;">${sub.next_billing_date || '—'}</div></div>
          <div><div class="form-hint">Start Date</div><div>${sub.start_date}</div></div>
          <div><div class="form-hint">Expiry Date</div><div>${sub.expiry_date || 'Ongoing'}</div></div>
          <div><div class="form-hint">Auto-Renew Policy</div><div>${sub.auto_renew ? 'Enabled' : 'Manual Close'}</div></div>
        </div>

        <div style="margin-bottom: 16px;">
          <h4 style="font-size: 14px; font-weight: 700; margin-bottom: 8px;">Subscription Lines & Switchable Add-ons</h4>
          <table class="data-table" style="font-size: 12.5px;">
            <thead>
              <tr>
                <th>Item / Variant</th>
                <th>Qty</th>
                <th>Unit Price</th>
                <th>Tax</th>
                <th>Line Total</th>
                <th style="text-align: center;">Add-on Switch</th>
              </tr>
            </thead>
            <tbody>
              ${linesHtml}
            </tbody>
          </table>
        </div>

        <div style="background: var(--blue-bg); border: 1px solid var(--blue-border); padding: 12px; border-radius: var(--radius-sm); font-size: 12px; color: var(--blue-text);">
          <strong>Add-on Proration Note:</strong> Switching add-ons on or off recalculates billing on the fly with pro-rated credit/charge adjustments.
        </div>
      `;

      // Build Action Buttons based on status
      let actionButtons = `<button class="btn btn-secondary" onclick="app.closeModal()">Close</button>`;

      if (sub.status === "quotation" || sub.status === "draft") {
        actionButtons += `
          <button class="btn btn-primary" onclick="subscriptionsPage.transitionStatus(${sub.id}, 'active')">Confirm & Activate</button>
        `;
      } else if (sub.status === "active") {
        actionButtons += `
          <button class="btn btn-secondary" onclick="subscriptionsPage.transitionStatus(${sub.id}, 'paused')">Pause Subscription</button>
          <button class="btn btn-danger" onclick="subscriptionsPage.transitionStatus(${sub.id}, 'closed')">Close Early</button>
        `;
      } else if (sub.status === "paused") {
        actionButtons += `
          <button class="btn btn-success" onclick="subscriptionsPage.transitionStatus(${sub.id}, 'active')">Resume Subscription</button>
          <button class="btn btn-danger" onclick="subscriptionsPage.transitionStatus(${sub.id}, 'closed')">Close Early</button>
        `;
      } else if (sub.status === "closed") {
        actionButtons += `
          <button class="btn btn-primary" onclick="subscriptionsPage.transitionStatus(${sub.id}, 'active')">Renew Subscription</button>
        `;
      }

      app.openModal(`Subscription ${sub.sub_number}`, modalHtml, actionButtons, true);
    } catch (e) {
      console.error("Error opening sub details:", e);
    }
  },

  async transitionStatus(subId, newStatus) {
    try {
      await app.api(`/api/subscriptions/${subId}/transition`, "POST", { status: newStatus });
      app.showToast(`Subscription status updated to ${newStatus.toUpperCase()}`, "success");
      app.closeModal();
      this.load();
    } catch (e) {
      // Handled
    }
  },

  async toggleAddon(subId, lineId, active) {
    try {
      const res = await app.api(`/api/subscriptions/${subId}/toggle-addon`, "POST", {
        line_id: lineId,
        active: active
      });
      const proration = res.proration_impact;
      const statusText = active ? "activated" : "deactivated";
      app.showToast(`Add-on '${res.product_name}' ${statusText}. Prorated adjustment: $${proration.prorated_amount} (${proration.remaining_days}/${proration.total_cycle_days} days).`, "success");
    } catch (e) {
      // Handled
    }
  },

  async openNewSubscriptionModal() {
    try {
      const [usersRes, plansRes, prodsRes] = await Promise.all([
        app.api("/api/auth/users?role=customer"),
        app.api("/api/plans"),
        app.api("/api/products")
      ]);

      const custOptions = (usersRes.users || []).map(u => `<option value="${u.id}">${u.full_name} (${u.company || u.email})</option>`).join("");
      const planOptions = (plansRes.plans || []).map(p => `<option value="${p.id}">${p.name} ($${p.base_price}/${p.billing_frequency})</option>`).join("");
      const prodOptions = (prodsRes.products || []).map(pr => `<option value="${pr.id}">${pr.name} ($${pr.sales_price})</option>`).join("");

      const today = new Date().toISOString().split("T")[0];

      const html = `
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Customer:</label>
            <select class="form-control" id="new-sub-customer">${custOptions}</select>
          </div>
          <div class="form-group">
            <label class="form-label">Billing Plan:</label>
            <select class="form-control" id="new-sub-plan">${planOptions}</select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Primary Product Line:</label>
            <select class="form-control" id="new-sub-prod">${prodOptions}</select>
          </div>
          <div class="form-group">
            <label class="form-label">Quantity / Seats:</label>
            <input type="number" class="form-control" id="new-sub-qty" value="1" min="1">
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Payment Terms:</label>
            <select class="form-control" id="new-sub-terms">
              <option value="Net 30">Net 30 Days</option>
              <option value="Net 15">Net 15 Days</option>
              <option value="Immediate">Immediate / Card on File</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Initial Status:</label>
            <select class="form-control" id="new-sub-status">
              <option value="active">Active (Begin billing immediately)</option>
              <option value="quotation">Quotation (Sales proposal stage)</option>
            </select>
          </div>
        </div>
      `;

      const footer = `
        <button class="btn btn-secondary" onclick="app.closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="subscriptionsPage.createSubscription()">Create Subscription</button>
      `;

      app.openModal("Create New Subscription", html, footer);
    } catch (e) {
      console.error(e);
    }
  },

  async createSubscription() {
    const custId = document.getElementById("new-sub-customer").value;
    const planId = document.getElementById("new-sub-plan").value;
    const prodId = document.getElementById("new-sub-prod").value;
    const qty = parseInt(document.getElementById("new-sub-qty").value) || 1;
    const terms = document.getElementById("new-sub-terms").value;
    const status = document.getElementById("new-sub-status").value;

    try {
      // Create quote and convert if active
      const quoteRes = await app.api("/api/quotations", "POST", {
        customer_id: custId,
        plan_id: planId,
        validity_days: 30,
        notes: `Terms: ${terms}`,
        lines: [{ product_id: prodId, quantity: qty, unit_price: 1200.0 }]
      });

      if (status === "active") {
        await app.api(`/api/quotations/${quoteRes.quotation_id}/convert`, "POST");
        app.showToast("Active subscription generated successfully!", "success");
      } else {
        app.showToast(`Quotation ${quoteRes.quotation_number} generated successfully!`, "success");
      }

      app.closeModal();
      this.load();
    } catch (e) {
      // Handled
    }
  }
};

window.subscriptionsPage = subscriptionsPage;
