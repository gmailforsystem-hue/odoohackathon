/**
 * Tax Engine Page Controller
 * Handles admin configuration of tax rules and calculation percentages.
 */

const taxesPage = {
  async load() {
    try {
      const res = await app.api("/api/taxes");
      this.renderTable(res.taxes || []);
    } catch (e) {
      console.error("Error loading taxes:", e);
    }
  },

  renderTable(taxes) {
    const tbody = document.getElementById("taxes-table-body");
    if (!tbody) return;

    if (!taxes.length) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--slate-400); padding: 32px;">No tax rules found.</td></tr>`;
      return;
    }

    tbody.innerHTML = taxes.map(t => `
      <tr>
        <td style="font-weight: 700; color: var(--slate-900);">${t.name}</td>
        <td style="font-weight: 700; color: #2563eb; font-size: 14px;">${Number(t.rate_percent).toFixed(1)}%</td>
        <td><span class="status-pill status-active">Active</span></td>
      </tr>
    `).join("");
  },

  openNewTaxModal() {
    if (app.currentRole !== "admin") {
      app.showToast("Only administrators can configure tax rules.", "error");
      return;
    }

    const html = `
      <div class="form-group">
        <label class="form-label">Tax Rule Name:</label>
        <input type="text" class="form-control" id="new-tax-name" placeholder="e.g. EU Harmonized VAT (15%)">
      </div>

      <div class="form-group">
        <label class="form-label">Tax Rate Percentage (%):</label>
        <input type="number" class="form-control" id="new-tax-rate" value="15.0" step="0.1" min="0">
      </div>
    `;

    const footer = `
      <button class="btn btn-secondary" onclick="app.closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="taxesPage.submitTax()">Save Tax Rule</button>
    `;

    app.openModal("Create Tax Rule", html, footer);
  },

  async submitTax() {
    const name = document.getElementById("new-tax-name").value.trim();
    const rate = parseFloat(document.getElementById("new-tax-rate").value) || 0;

    if (!name) {
      app.showToast("Tax rule name is required", "error");
      return;
    }

    try {
      await app.api("/api/taxes", "POST", { name, rate_percent: rate });
      app.showToast(`Tax rule "${name}" created!`, "success");
      app.closeModal();
      this.load();
    } catch (e) {
      // Handled
    }
  }
};

window.taxesPage = taxesPage;
