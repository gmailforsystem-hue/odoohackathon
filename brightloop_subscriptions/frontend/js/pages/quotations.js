/*
 * Quotations Page Controller
 * Handles quotation templates, proposal generation, and conversion to active subscription.
 */

const quotationsPage = {
  templates: [],

  async load() {
    try {
      const [subsRes, tempRes] = await Promise.all([
        app.api("/api/subscriptions?status=quotation"),
        app.api("/api/quotations/templates")
      ]);

      this.templates = tempRes.templates || [];
      this.renderTable(subsRes.subscriptions || []);
    } catch (e) {
      console.error("Error loading quotations:", e);
    }
  },

  renderTable(quotes) {
    const tbody = document.getElementById("quotations-table-body");
    if (!tbody) return;

    if (!quotes.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--slate-400); padding: 32px;">No open quotations. Click "+ Create Quotation" to draft one.</td></tr>`;
      return;
    }

    tbody.innerHTML = quotes.map(q => `
      <tr>
        <td style="font-weight: 700; color: #2563eb;">${q.sub_number}</td>
        <td>
          <div style="font-weight: 600;">${q.customer_name}</div>
          <div style="font-size: 11.5px; color: var(--slate-500);">${q.customer_company || ''}</div>
        </td>
        <td>${q.plan_name}</td>
        <td>${q.start_date}</td>
        <td><strong>${q.expiry_date || '—'}</strong></td>
        <td>${q.payment_terms || 'Net 30'}</td>
        <td><span class="status-pill status-${q.status}">${q.status}</span></td>
        <td>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-secondary btn-sm" onclick="subscriptionsPage.viewDetails(${q.id})">Review</button>
            <button class="btn btn-primary btn-sm" onclick="quotationsPage.convertToSub(${q.id})">Convert to Subscription</button>
          </div>
        </td>
      </tr>
    `).join("");
  },

  async convertToSub(quoteId) {
    try {
      const res = await app.api(`/api/quotations/${quoteId}/convert`, "POST");
      app.showToast(`Quotation converted to Active Subscription ${res.subscription_number}!`, "success");
      this.load();
    } catch (e) {
      // Handled
    }
  },

  async openNewQuoteModal() {
    try {
      const [usersRes, plansRes, prodsRes] = await Promise.all([
        app.api("/api/auth/users?role=customer"),
        app.api("/api/plans"),
        app.api("/api/products")
      ]);

      const templateOptions = `<option value="">-- Start from Scratch --</option>` +
        this.templates.map(t => `<option value="${t.id}">${t.name} (Valid ${t.validity_days} days)</option>`).join("");

      const custOptions = (usersRes.users || []).map(u => `<option value="${u.id}">${u.full_name} (${u.company || u.email})</option>`).join("");
      const planOptions = (plansRes.plans || []).map(p => `<option value="${p.id}">${p.name} ($${p.base_price}/${p.billing_frequency})</option>`).join("");

      // Collect product options with variants (e.g. Odoo brand +$560)
      let lineOptions = "";
      (prodsRes.products || []).forEach(p => {
        lineOptions += `<option value="${p.id}" data-price="${p.sales_price}" data-var="">${p.name} - Standard ($${p.sales_price})</option>`;
        (p.variants || []).forEach(v => {
          const tot = p.sales_price + v.price_surcharge;
          lineOptions += `<option value="${p.id}" data-price="${tot}" data-var="${v.id}">${p.name} - ${v.attribute_value} (+$${v.price_surcharge}) - Total $${tot}</option>`;
        });
      });

      const html = `
        <div class="form-group" style="background: #f8fafc; padding: 12px; border: 1px solid var(--slate-200); border-radius: var(--radius-md);">
          <label class="form-label">Quotation Template (Optional Pre-fill):</label>
          <select class="form-control" id="quote-template-select" onchange="quotationsPage.onTemplateSelect(this.value)">
            ${templateOptions}
          </select>
          <div class="form-hint">Templates pre-load recommended plans and product line items.</div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Select Customer:</label>
            <select class="form-control" id="quote-cust-id">${custOptions}</select>
          </div>
          <div class="form-group">
            <label class="form-label">Billing Plan:</label>
            <select class="form-control" id="quote-plan-id">${planOptions}</select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Proposal Validity (Days):</label>
            <input type="number" class="form-control" id="quote-validity-days" value="30" min="1">
          </div>
          <div class="form-group">
            <label class="form-label">Payment Terms:</label>
            <select class="form-control" id="quote-terms">
              <option value="Net 30">Net 30 Days</option>
              <option value="Net 15">Net 15 Days</option>
              <option value="Immediate">Immediate / Card on File</option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Included Product Line:</label>
          <select class="form-control" id="quote-product-select">${lineOptions}</select>
        </div>

        <div class="form-group">
          <label class="form-label">Seat Quantity:</label>
          <input type="number" class="form-control" id="quote-quantity" value="1" min="1">
        </div>

        <div class="form-group">
          <label class="form-label">Internal Proposal Notes:</label>
          <textarea class="form-control" id="quote-notes" rows="2" placeholder="e.g. Special enterprise contract including 5 Odoo seats."></textarea>
        </div>
      `;

      const footer = `
        <button class="btn btn-secondary" onclick="app.closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="quotationsPage.submitQuotation()">Create Quotation</button>
      `;

      app.openModal("Create Sales Quotation", html, footer, true);
    } catch (e) {
      console.error(e);
    }
  },

  onTemplateSelect(templateId) {
    if (!templateId) return;
    const t = this.templates.find(x => x.id == templateId);
    if (!t) return;

    if (t.default_plan_id) {
      const planSelect = document.getElementById("quote-plan-id");
      if (planSelect) planSelect.value = t.default_plan_id;
    }
    if (t.validity_days) {
      const valInput = document.getElementById("quote-validity-days");
      if (valInput) valInput.value = t.validity_days;
    }
    const notesInput = document.getElementById("quote-notes");
    if (notesInput && t.notes) {
      notesInput.value = t.notes;
    }
    app.showToast(`Loaded template "${t.name}" settings!`, "info");
  },

  async submitQuotation() {
    const custId = document.getElementById("quote-cust-id").value;
    const planId = document.getElementById("quote-plan-id").value;
    const validityDays = parseInt(document.getElementById("quote-validity-days").value) || 30;
    const terms = document.getElementById("quote-terms").value;
    const notes = document.getElementById("quote-notes").value;

    const prodSelect = document.getElementById("quote-product-select");
    const selectedOption = prodSelect.options[prodSelect.selectedIndex];
    const prodId = selectedOption.value;
    const varId = selectedOption.getAttribute("data-var") || null;
    const unitPrice = parseFloat(selectedOption.getAttribute("data-price")) || 1200;
    const qty = parseInt(document.getElementById("quote-quantity").value) || 1;

    try {
      const res = await app.api("/api/quotations", "POST", {
        customer_id: custId,
        plan_id: planId,
        validity_days: validityDays,
        notes: `${notes} (Terms: ${terms})`,
        lines: [
          {
            product_id: prodId,
            variant_id: varId,
            quantity: qty,
            unit_price: unitPrice,
            tax_id: 1
          }
        ]
      });

      app.showToast(`Quotation ${res.quotation_number} generated successfully!`, "success");
      app.closeModal();
      this.load();
    } catch (e) {
      // Handled
    }
  }
};

window.quotationsPage = quotationsPage;
