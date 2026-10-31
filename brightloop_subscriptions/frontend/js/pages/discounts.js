/*
 * Discounts & Promotions Page Controller
 * Handles admin discount rules: fixed or percentage, min spend/quantity thresholds,
 * product-specific or subscription-wide scope, validity dates, and usage caps.
 */

const discountsPage = {
  async load() {
    try {
      const res = await app.api("/api/discounts");
      this.renderTable(res.discounts || []);
    } catch (e) {
      console.error("Error loading discounts:", e);
    }
  },

  renderTable(discounts) {
    const tbody = document.getElementById("discounts-table-body");
    if (!tbody) return;

    if (!discounts.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--slate-400); padding: 32px;">No active discount rules.</td></tr>`;
      return;
    }

    tbody.innerHTML = discounts.map(d => {
      const valueLabel = d.discount_type === "percentage" ? `${d.value}% OFF` : `$${Number(d.value).toFixed(2)} OFF`;
      
      const criteriaList = [];
      if (d.min_amount > 0) criteriaList.push(`Min $${d.min_amount}`);
      if (d.min_quantity > 0) criteriaList.push(`Min ${d.min_quantity} seats`);
      const criteriaLabel = criteriaList.length ? criteriaList.join(" &bull; ") : "No minimum";

      const scopeLabel = d.apply_to === "product"
        ? `<span class="status-pill status-paused">Product: ${d.product_name || 'Selected'}</span>`
        : `<span class="status-pill status-confirmed">Whole Subscription</span>`;

      const usageLabel = `${d.times_used} / ${d.max_uses} used`;

      return `
        <tr>
          <td>
            <div style="font-weight: 800; color: #2563eb; font-size: 14px; letter-spacing: 0.05em;">${d.code}</div>
          </td>
          <td style="max-width: 200px;">${d.description || '—'}</td>
          <td style="font-weight: 700; color: #16a34a; font-size: 13.5px;">${valueLabel}</td>
          <td>${criteriaLabel}</td>
          <td>${scopeLabel}</td>
          <td style="font-weight: 600;">${usageLabel}</td>
          <td style="font-size: 12px; color: var(--slate-600);">${d.start_date || '—'} &rarr; ${d.end_date || 'Ongoing'}</td>
          <td><span class="status-pill status-active">Active</span></td>
        </tr>
      `;
    }).join("");
  },

  async openNewDiscountModal() {
    if (app.currentRole !== "admin") {
      app.showToast("Only administrators can create discount rules.", "error");
      return;
    }

    try {
      const prodsRes = await app.api("/api/products");
      const prodOptions = (prodsRes.products || []).map(p => `<option value="${p.id}">${p.name} ($${p.sales_price})</option>`).join("");
      const today = new Date().toISOString().split("T")[0];

      const html = `
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Coupon / Promo Code:</label>
            <input type="text" class="form-control" id="new-disc-code" placeholder="e.g. BRIGHT50" style="text-transform: uppercase;">
          </div>
          <div class="form-group">
            <label class="form-label">Discount Type:</label>
            <select class="form-control" id="new-disc-type">
              <option value="percentage">Percentage (%)</option>
              <option value="fixed">Fixed Dollar Amount ($)</option>
            </select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Discount Value:</label>
            <input type="number" class="form-control" id="new-disc-value" value="15.0" step="1">
            <div class="form-hint">E.g. 20 for 20% or 500 for $500</div>
          </div>
          <div class="form-group">
            <label class="form-label">Max Uses Limit:</label>
            <input type="number" class="form-control" id="new-disc-max-uses" value="100" min="1">
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Min Purchase Amount ($):</label>
            <input type="number" class="form-control" id="new-disc-min-amt" value="1000.0" step="50">
          </div>
          <div class="form-group">
            <label class="form-label">Min Seat Quantity:</label>
            <input type="number" class="form-control" id="new-disc-min-qty" value="3" min="0">
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Start Date:</label>
            <input type="date" class="form-control" id="new-disc-start" value="${today}">
          </div>
          <div class="form-group">
            <label class="form-label">End Date:</label>
            <input type="date" class="form-control" id="new-disc-end" value="2027-12-31">
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Scope Application:</label>
          <select class="form-control" id="new-disc-scope" onchange="discountsPage.onScopeChange(this.value)">
            <option value="all">Whole Subscription</option>
            <option value="product">Specific Product Only</option>
          </select>
        </div>

        <div class="form-group" id="disc-prod-wrapper" style="display: none;">
          <label class="form-label">Target Product:</label>
          <select class="form-control" id="new-disc-prod-id">${prodOptions}</select>
        </div>

        <div class="form-group">
          <label class="form-label">Description / Internal Reason:</label>
          <input type="text" class="form-control" id="new-disc-desc" placeholder="e.g. 15% discount for customers taking 3+ seats">
        </div>
      `;

      const footer = `
        <button class="btn btn-secondary" onclick="app.closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="discountsPage.submitDiscount()">Create Discount Rule</button>
      `;

      app.openModal("Create Promotional Discount Rule", html, footer);
    } catch (e) {
      console.error(e);
    }
  },

  onScopeChange(val) {
    const wrap = document.getElementById("disc-prod-wrapper");
    if (wrap) wrap.style.display = val === "product" ? "block" : "none";
  },

  async submitDiscount() {
    const code = document.getElementById("new-disc-code").value.trim().toUpperCase();
    const type = document.getElementById("new-disc-type").value;
    const value = parseFloat(document.getElementById("new-disc-value").value) || 0;
    const maxUses = parseInt(document.getElementById("new-disc-max-uses").value) || 100;
    const minAmt = parseFloat(document.getElementById("new-disc-min-amt").value) || 0;
    const minQty = parseInt(document.getElementById("new-disc-min-qty").value) || 0;
    const start = document.getElementById("new-disc-start").value;
    const end = document.getElementById("new-disc-end").value;
    const scope = document.getElementById("new-disc-scope").value;
    const prodId = scope === "product" ? document.getElementById("new-disc-prod-id").value : null;
    const desc = document.getElementById("new-disc-desc").value.trim();

    if (!code) {
      app.showToast("Coupon code is required", "error");
      return;
    }

    try {
      await app.api("/api/discounts", "POST", {
        code,
        discount_type: type,
        value,
        max_uses: maxUses,
        min_amount: minAmt,
        min_quantity: minQty,
        start_date: start,
        end_date: end,
        apply_to: scope,
        product_id: prodId,
        description: desc
      });

      app.showToast(`Discount rule "${code}" created successfully!`, "success");
      app.closeModal();
      this.load();
    } catch (e) {
      // Handled
    }
  }
};

window.discountsPage = discountsPage;
