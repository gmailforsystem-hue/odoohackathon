/**
 * Payments Ledger Page Controller
 * Handles recording full and partial payments, method reconciliation, and settlement audit logs.
 */

const paymentsPage = {
  async load() {
    try {
      const res = await app.api("/api/payments");
      this.renderTable(res.payments || []);
    } catch (e) {
      console.error("Error loading payments:", e);
    }
  },

  renderTable(payments) {
    const tbody = document.getElementById("payments-table-body");
    if (!tbody) return;

    if (!payments.length) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--slate-400); padding: 32px;">No payment transactions recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = payments.map(p => {
      const methodLabel = p.method ? p.method.replace("_", " ").toUpperCase() : "CARD";
      return `
        <tr>
          <td style="font-weight: 700; color: #16a34a;">${p.payment_number}</td>
          <td>
            <span style="font-weight: 600; color: #2563eb; cursor: pointer;" onclick="invoicesPage.viewPrintInvoice(${p.invoice_id})">
              ${p.invoice_number}
            </span>
          </td>
          <td>${p.customer_name}</td>
          <td>${p.payment_date}</td>
          <td>
            <span class="status-pill status-confirmed">${methodLabel}</span>
          </td>
          <td style="font-weight: 700; color: #16a34a; font-size: 14px;">
            $${Number(p.amount).toFixed(2)}
          </td>
          <td style="font-size: 12.5px; color: var(--slate-600);">${p.reference_notes || '—'}</td>
        </tr>
      `;
    }).join("");
  },

  async openRecordPaymentModal(prefillInvoiceId = null, prefillAmount = null) {
    try {
      const res = await app.api("/api/invoices?limit=100");
      const unpaidInvoices = (res.invoices || []).filter(i => (i.total_amount - i.paid_amount) > 0.01);

      if (!unpaidInvoices.length) {
        app.showToast("All invoices are currently fully settled! No outstanding dues.", "info");
        return;
      }

      const invOptions = unpaidInvoices.map(i => {
        const bal = (i.total_amount - i.paid_amount).toFixed(2);
        const selected = prefillInvoiceId && i.id === prefillInvoiceId ? "selected" : "";
        return `<option value="${i.id}" data-balance="${bal}" data-total="${i.total_amount}" ${selected}>${i.invoice_number} - ${i.customer_name} (Balance Due: $${bal})</option>`;
      }).join("");

      const initialBal = prefillAmount ? prefillAmount.toFixed(2) : (unpaidInvoices[0].total_amount - unpaidInvoices[0].paid_amount).toFixed(2);
      const today = new Date().toISOString().split("T")[0];

      const html = `
        <div class="form-group">
          <label class="form-label">Select Outstanding Invoice:</label>
          <select class="form-control" id="pay-inv-select" onchange="paymentsPage.onInvoiceSelect(this)">
            ${invOptions}
          </select>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Payment Amount ($):</label>
            <input type="number" class="form-control" id="pay-amount" value="${initialBal}" step="0.01" min="0.01">
            <div class="form-hint" id="pay-balance-hint">Outstanding balance: $${initialBal} (Partial payment supported)</div>
          </div>
          <div class="form-group">
            <label class="form-label">Payment Date:</label>
            <input type="date" class="form-control" id="pay-date" value="${today}">
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Payment Method:</label>
          <select class="form-control" id="pay-method">
            <option value="stripe">Stripe / Credit Card</option>
            <option value="bank_transfer">ACH / Bank Transfer (Direct Deposit)</option>
            <option value="check">Company Check</option>
            <option value="cash">Cash / Other</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Reference / Memo Notes:</label>
          <input type="text" class="form-control" id="pay-notes" placeholder="e.g. Wire confirmation #WX-882914 or Check #4492">
        </div>
      `;

      const footer = `
        <button class="btn btn-secondary" onclick="app.closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="paymentsPage.submitPayment()">Record Payment</button>
      `;

      app.openModal("Record Payment against Invoice", html, footer);
    } catch (e) {
      console.error(e);
    }
  },

  onInvoiceSelect(selectEl) {
    const selectedOption = selectEl.options[selectEl.selectedIndex];
    const balance = selectedOption.getAttribute("data-balance");
    const amountInput = document.getElementById("pay-amount");
    const hint = document.getElementById("pay-balance-hint");

    if (amountInput) amountInput.value = balance;
    if (hint) hint.textContent = `Outstanding balance: $${balance} (Partial payment supported)`;
  },

  async submitPayment() {
    const invId = document.getElementById("pay-inv-select").value;
    const amount = parseFloat(document.getElementById("pay-amount").value) || 0;
    const date = document.getElementById("pay-date").value;
    const method = document.getElementById("pay-method").value;
    const notes = document.getElementById("pay-notes").value.trim();

    if (amount <= 0) {
      app.showToast("Payment amount must be greater than zero", "error");
      return;
    }

    try {
      const res = await app.api("/api/payments", "POST", {
        invoice_id: invId,
        amount: amount,
        method: method,
        payment_date: date,
        reference_notes: notes
      });

      app.showToast(`Payment of $${amount.toFixed(2)} recorded! Invoice status is now ${res.invoice_status.toUpperCase()}.`, "success");
      app.closeModal();
      this.load();
      if (window.invoicesPage) invoicesPage.load();
    } catch (e) {
      // Handled
    }
  }
};

window.paymentsPage = paymentsPage;
