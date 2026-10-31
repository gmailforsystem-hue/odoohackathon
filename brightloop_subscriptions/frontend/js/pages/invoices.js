/*
 * Invoices Page Controller
 * Manages recurring invoice lifecycle, PDF/printable layout, tax/discount display, and status transitions.
 */

const invoicesPage = {
  currentFilter: "",
  initialized: false,

  init() {
    if (this.initialized) return;
    this.initialized = true;

    const container = document.getElementById("invoice-status-filters");
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
  },

  async load() {
    this.init();
    try {
      let url = "/api/invoices?limit=100";
      if (this.currentFilter) url += `&status=${this.currentFilter}`;

      const res = await app.api(url);
      this.renderTable(res.invoices || []);
    } catch (e) {
      console.error("Error loading invoices:", e);
    }
  },

  renderTable(invoices) {
    const tbody = document.getElementById("invoices-table-body");
    if (!tbody) return;

    if (!invoices.length) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--slate-400); padding: 32px;">No invoices match current filter.</td></tr>`;
      return;
    }

    tbody.innerHTML = invoices.map(inv => {
      const balance = Math.max(0, inv.total_amount - inv.paid_amount);
      const isOverdue = inv.status === "overdue";

      return `
        <tr>
          <td style="font-weight: 700; color: #2563eb;">${inv.invoice_number}</td>
          <td>
            <div style="font-weight: 600;">${inv.customer_name}</div>
            <div style="font-size: 11.5px; color: var(--slate-500);">${inv.customer_company || ''}</div>
          </td>
          <td>${inv.sub_number || 'Direct'}</td>
          <td>${inv.issue_date}</td>
          <td>
            <span style="${isOverdue ? 'color: #dc2626; font-weight: 700;' : ''}">${inv.due_date}</span>
          </td>
          <td style="font-weight: 700;">$${Number(inv.total_amount).toFixed(2)}</td>
          <td style="color: #16a34a;">$${Number(inv.paid_amount).toFixed(2)}</td>
          <td style="font-weight: 700; color: ${balance > 0 ? '#dc2626' : 'var(--slate-500)'};">
            $${balance.toFixed(2)}
          </td>
          <td><span class="status-pill status-${inv.status}">${inv.status}</span></td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-secondary btn-sm" onclick="invoicesPage.viewPrintInvoice(${inv.id})">View</button>
              ${balance > 0 ? `<button class="btn btn-primary btn-sm" onclick="paymentsPage.openRecordPaymentModal(${inv.id}, ${balance})">Pay</button>` : ''}
            </div>
          </td>
        </tr>
      `;
    }).join("");
  },

  async viewPrintInvoice(invoiceId) {
    try {
      const res = await app.api(`/api/invoices/${invoiceId}`);
      const inv = res.invoice;
      const balance = Math.max(0, inv.total_amount - inv.paid_amount);

      const linesHtml = (inv.lines || []).map(l => `
        <tr>
          <td>
            <div style="font-weight: 600; color: var(--slate-900);">${l.product_name}</div>
            ${l.variant_name ? `<div style="font-size: 11.5px; color: #2563eb;">${l.variant_name}</div>` : ''}
          </td>
          <td>${l.quantity}</td>
          <td>$${Number(l.unit_price).toFixed(2)}</td>
          <td>${l.tax_percent > 0 ? `${l.tax_percent}% ($${Number(l.tax_amount).toFixed(2)})` : 'Exempt'}</td>
          <td style="text-align: right; font-weight: 700;">$${Number(l.total_amount).toFixed(2)}</td>
        </tr>
      `).join("");

      const paymentsHtml = (inv.payments || []).length > 0
        ? inv.payments.map(p => `
            <div style="display: flex; justify-content: space-between; font-size: 12.5px; padding: 6px 0; border-bottom: 1px dashed var(--slate-200);">
              <span>${p.payment_date} via <strong>${p.method.replace('_', ' ').toUpperCase()}</strong> (${p.payment_number})</span>
              <span style="font-weight: 700; color: #16a34a;">-$${Number(p.amount).toFixed(2)}</span>
            </div>
          `).join("")
        : `<div style="font-size: 12.5px; color: var(--slate-400); padding: 6px 0;">No payments received yet.</div>`;

      const printableHtml = `
        <div class="invoice-paper">
          <div class="invoice-header-row">
            <div>
              <div class="invoice-brand">Brightloop Software</div>
              <div style="font-size: 12px; color: var(--slate-500); margin-top: 4px;">
                Cloud Infrastructure & Subscription Solutions<br>
                100 Innovation Way, Suite 400 &bull; billing@brightloop.com
              </div>
            </div>
            <div>
              <div class="invoice-badge-title">INVOICE</div>
              <div style="font-size: 16px; font-weight: 700; color: var(--slate-900); text-align: right;">${inv.invoice_number}</div>
              <div style="text-align: right; margin-top: 6px;">
                <span class="status-pill status-${inv.status}" style="font-size: 13px;">${inv.status.toUpperCase()}</span>
              </div>
            </div>
          </div>

          <div class="invoice-meta-grid">
            <div>
              <div class="form-hint" style="text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em;">Billed To:</div>
              <div style="font-size: 15px; font-weight: 700; color: var(--slate-900); margin-top: 4px;">${inv.customer_name}</div>
              <div style="font-size: 13px; color: var(--slate-600);">${inv.customer_company || ''}</div>
              <div style="font-size: 12.5px; color: var(--slate-500);">${inv.customer_email}</div>
            </div>
            <div style="text-align: right;">
              <div style="font-size: 13px;"><strong>Issue Date:</strong> ${inv.issue_date}</div>
              <div style="font-size: 13px; margin-top: 4px;"><strong>Payment Due:</strong> ${inv.due_date}</div>
              <div style="font-size: 13px; margin-top: 4px;"><strong>Subscription Ref:</strong> ${inv.sub_number || 'Direct Order'}</div>
              <div style="font-size: 13px; margin-top: 4px;"><strong>Payment Terms:</strong> ${inv.payment_terms || 'Net 30'}</div>
            </div>
          </div>

          <table class="data-table" style="margin-bottom: 20px;">
            <thead>
              <tr>
                <th>Description</th>
                <th>Qty</th>
                <th>Unit Price</th>
                <th>Tax</th>
                <th style="text-align: right;">Amount</th>
              </tr>
            </thead>
            <tbody>
              ${linesHtml}
            </tbody>
          </table>

          <div class="invoice-summary-box">
            <table class="invoice-totals-table">
              <tr>
                <td style="color: var(--slate-500);">Subtotal:</td>
                <td style="text-align: right; font-weight: 600;">$${Number(inv.subtotal).toFixed(2)}</td>
              </tr>
              ${inv.discount_amount > 0 ? `
                <tr>
                  <td style="color: #dc2626;">Promotional Discount:</td>
                  <td style="text-align: right; color: #dc2626; font-weight: 600;">-$${Number(inv.discount_amount).toFixed(2)}</td>
                </tr>
              ` : ''}
              <tr>
                <td style="color: var(--slate-500);">Taxes & Surcharges:</td>
                <td style="text-align: right; font-weight: 600;">+$${Number(inv.tax_amount).toFixed(2)}</td>
              </tr>
              <tr class="grand-total">
                <td>Total Due:</td>
                <td style="text-align: right; color: var(--slate-900);">$${Number(inv.total_amount).toFixed(2)}</td>
              </tr>
              <tr>
                <td style="color: #16a34a;">Amount Paid:</td>
                <td style="text-align: right; color: #16a34a; font-weight: 700;">-$${Number(inv.paid_amount).toFixed(2)}</td>
              </tr>
              <tr style="border-top: 1px solid var(--slate-300);">
                <td style="font-weight: 700; color: ${balance > 0 ? '#dc2626' : 'var(--slate-800)'};">Balance Outstanding:</td>
                <td style="text-align: right; font-weight: 800; color: ${balance > 0 ? '#dc2626' : 'var(--slate-800)'};">$${balance.toFixed(2)}</td>
              </tr>
            </table>
          </div>

          <div style="margin-top: 24px; padding-top: 18px; border-top: 1px solid var(--slate-200);">
            <div style="font-size: 13px; font-weight: 700; color: var(--slate-800); margin-bottom: 6px;">Recorded Transactions:</div>
            ${paymentsHtml}
          </div>
        </div>
      `;

      const footer = `
        <button class="btn btn-secondary" onclick="window.print()">Print Invoice</button>
        <button class="btn btn-secondary" onclick="invoicesPage.simulateSendEmail('${inv.invoice_number}', '${inv.customer_email}')">Email to Customer</button>
        ${balance > 0 ? `<button class="btn btn-primary" onclick="app.closeModal(); paymentsPage.openRecordPaymentModal(${inv.id}, ${balance})">Pay Outstanding Balance</button>` : ''}
      `;

      app.openModal(`Invoice ${inv.invoice_number}`, printableHtml, footer, true);
    } catch (e) {
      console.error(e);
    }
  },

  simulateSendEmail(invNumber, email) {
    app.showToast(`Invoice ${invNumber} dispatched to ${email}!`, "success");
  }
};

window.invoicesPage = invoicesPage;
