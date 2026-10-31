/**
 * Customers CRM Page Controller
 * Manages customer account directory and customer profile overview.
 */

const customersPage = {
  async load() {
    try {
      const res = await app.api("/api/auth/users?role=customer");
      this.renderTable(res.users || []);
    } catch (e) {
      console.error("Error loading customers:", e);
    }
  },

  renderTable(customers) {
    const tbody = document.getElementById("customers-table-body");
    if (!tbody) return;

    if (!customers.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--slate-400); padding: 32px;">No customers found.</td></tr>`;
      return;
    }

    tbody.innerHTML = customers.map(c => `
      <tr>
        <td>
          <div style="font-weight: 700; color: var(--slate-900);">${c.full_name}</div>
        </td>
        <td>
          <div style="font-weight: 600; color: var(--slate-800);">${c.company || 'Individual'}</div>
        </td>
        <td>${c.email}</td>
        <td><span class="role-tag customer">CUSTOMER</span></td>
        <td>${c.created_at ? c.created_at.split('T')[0] : '2026-10-01'}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="customersPage.viewCustomerPortfolio(${c.id}, '${c.full_name}', '${c.company || ''}')">View Portfolio</button>
        </td>
      </tr>
    `).join("");
  },

  async viewCustomerPortfolio(customerId, customerName, customerCompany) {
    try {
      const [subsRes, invsRes] = await Promise.all([
        app.api(`/api/subscriptions?customer_id=${customerId}`),
        app.api(`/api/invoices?customer_id=${customerId}`)
      ]);

      const subs = subsRes.subscriptions || [];
      const invs = invsRes.invoices || [];

      const subsHtml = subs.length > 0
        ? subs.map(s => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--slate-100);">
              <div>
                <span style="font-weight: 700; color: var(--slate-900);">${s.sub_number}</span> - ${s.plan_name} (${s.billing_frequency})
                <div style="font-size: 11.5px; color: var(--slate-500);">Next Billing: ${s.next_billing_date || '—'}</div>
              </div>
              <span class="status-pill status-${s.status}">${s.status}</span>
            </div>
          `).join("")
        : `<div style="font-size: 12.5px; color: var(--slate-400); padding: 8px 0;">No subscriptions.</div>`;

      const invsHtml = invs.length > 0
        ? invs.map(i => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--slate-100);">
              <div>
                <span style="font-weight: 700; color: #2563eb;">${i.invoice_number}</span> - Issued: ${i.issue_date}
                <div style="font-size: 11.5px; color: var(--slate-500);">Total: $${Number(i.total_amount).toFixed(2)} &bull; Paid: $${Number(i.paid_amount).toFixed(2)}</div>
              </div>
              <span class="status-pill status-${i.status}">${i.status}</span>
            </div>
          `).join("")
        : `<div style="font-size: 12.5px; color: var(--slate-400); padding: 8px 0;">No invoices.</div>`;

      const html = `
        <div style="margin-bottom: 18px; padding-bottom: 12px; border-bottom: 1px solid var(--slate-200);">
          <div style="font-size: 17px; font-weight: 800; color: var(--slate-900);">${customerName}</div>
          <div style="font-size: 13px; color: var(--slate-500);">${customerCompany}</div>
        </div>

        <div style="margin-bottom: 20px;">
          <h4 style="font-size: 13.5px; font-weight: 700; margin-bottom: 8px;">Active Subscriptions (${subs.length})</h4>
          ${subsHtml}
        </div>

        <div>
          <h4 style="font-size: 13.5px; font-weight: 700; margin-bottom: 8px;">Billing Invoices (${invs.length})</h4>
          ${invsHtml}
        </div>
      `;

      app.openModal(`Client Portfolio: ${customerName}`, html, `<button class="btn btn-secondary" onclick="app.closeModal()">Close</button>`);
    } catch (e) {
      console.error(e);
    }
  }
};

window.customersPage = customersPage;
