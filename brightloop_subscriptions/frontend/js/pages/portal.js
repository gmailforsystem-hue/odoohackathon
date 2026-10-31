/*
 * Customer Self-Service Portal Controller
 * Dedicated portal for customers to manage their own subscriptions, toggle add-ons
 * without contacting support, and view/settle invoices.
 */

const portalPage = {
  async load() {
    const container = document.getElementById("customer-portal-container");
    if (!container) return;

    // Use current persona's user id (defaults to David Miller, ID: 4, Apex Store)
    const custId = app.currentRole === "customer" ? app.currentUserId : 4;

    try {
      const [subsRes, invsRes, prodsRes] = await Promise.all([
        app.api(`/api/subscriptions?customer_id=${custId}`),
        app.api(`/api/invoices?customer_id=${custId}`),
        app.api("/api/products")
      ]);

      const subs = subsRes.subscriptions || [];
      const invs = invsRes.invoices || [];
      const addOnProducts = (prodsRes.products || []).filter(p => p.type === "addon");

      const primarySub = subs[0] || null;

      let subLines = [];
      if (primarySub) {
        const fullSub = await app.api(`/api/subscriptions/${primarySub.id}`);
        subLines = fullSub.subscription.lines || [];
      }

      this.renderPortal(container, primarySub, subLines, addOnProducts, invs);
    } catch (e) {
      console.error("Error loading customer portal:", e);
    }
  },

  renderPortal(container, sub, lines, availableAddons, invoices) {
    if (!sub) {
      container.innerHTML = `
        <div class="card">
          <div class="card-body" style="text-align: center; padding: 48px;">
            <h3 style="font-size: 16px; font-weight: 700; margin-bottom: 6px;">Brightloop Customer Portal</h3>
            <p style="color: var(--slate-500); margin-bottom: 20px;">No active subscriptions found for this client account.</p>
            <button class="btn btn-primary" onclick="app.navigateTo('subscriptions')">Browse Available SaaS Plans</button>
          </div>
        </div>
      `;
      return;
    }

    // Render active and available add-ons
    const addonListHtml = lines.filter(l => l.is_addon === 1).map(l => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 14px; background: var(--slate-50); border: 1px solid var(--slate-200); border-radius: var(--radius-md); margin-bottom: 10px;">
        <div>
          <div style="font-weight: 700; color: var(--slate-900); font-size: 14px;">${l.product_name}</div>
          <div style="font-size: 12px; color: var(--slate-500);">$${Number(l.sales_price || l.unit_price).toFixed(2)}/mo &bull; Self-service add-on</div>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="font-size: 12.5px; font-weight: 600; color: ${l.addon_active ? '#16a34a' : 'var(--slate-400)'};">
            ${l.addon_active ? 'ENABLED' : 'DISABLED'}
          </span>
          <label class="switch">
            <input type="checkbox" ${l.addon_active ? 'checked' : ''} onchange="portalPage.toggleCustomerAddon(${sub.id}, ${l.id}, this.checked)">
            <span class="slider"></span>
          </label>
        </div>
      </div>
    `).join("");

    // Invoices table
    const invoiceRows = invoices.map(i => {
      const bal = Math.max(0, i.total_amount - i.paid_amount);
      return `
        <tr>
          <td style="font-weight: 700; color: #2563eb;">${i.invoice_number}</td>
          <td>${i.issue_date}</td>
          <td>${i.due_date}</td>
          <td style="font-weight: 700;">$${Number(i.total_amount).toFixed(2)}</td>
          <td style="color: #16a34a;">$${Number(i.paid_amount).toFixed(2)}</td>
          <td style="font-weight: 700; color: ${bal > 0 ? '#dc2626' : 'var(--slate-500)'};">$${bal.toFixed(2)}</td>
          <td><span class="status-pill status-${i.status}">${i.status}</span></td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-secondary btn-sm" onclick="invoicesPage.viewPrintInvoice(${i.id})">Receipt</button>
              ${bal > 0 ? `<button class="btn btn-primary btn-sm" onclick="paymentsPage.openRecordPaymentModal(${i.id}, ${bal})">Pay Now</button>` : ''}
            </div>
          </td>
        </tr>
      `;
    }).join("");

    container.innerHTML = `
      <!-- Customer Welcome Card -->
      <div class="card" style="margin-bottom: 24px;">
        <div class="card-body">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
            <div>
              <div style="font-size: 11.5px; font-weight: 700; color: #2563eb; text-transform: uppercase; letter-spacing: 0.05em;">Customer Self-Service Hub</div>
              <h2 style="font-size: 20px; font-weight: 700; color: var(--slate-900); margin-top: 4px;">Welcome back, ${sub.customer_name}</h2>
              <div style="font-size: 13px; color: var(--slate-600); margin-top: 2px;">Managing services for <strong>${sub.customer_company || 'Your Account'}</strong> (${sub.customer_email})</div>
            </div>
            <div style="display: flex; gap: 12px;">
              <button class="btn btn-secondary" onclick="portalPage.load()">Refresh Status</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Plan Status & Self-Service Add-ons Grid -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 22px;">
        <!-- Active Subscription Summary -->
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Current Active Subscription</div>
              <div class="card-subtitle">Ref: ${sub.sub_number}</div>
            </div>
            <span class="status-pill status-${sub.status}">${sub.status}</span>
          </div>
          <div class="card-body">
            <div style="margin-bottom: 16px;">
              <div style="font-size: 11.5px; color: var(--slate-500);">Subscribed Plan</div>
              <div style="font-size: 17px; font-weight: 700; color: var(--slate-900);">${sub.plan_name}</div>
              <div style="font-size: 12.5px; color: var(--slate-600); margin-top: 2px;">Billing Frequency: <strong style="text-transform: capitalize;">${sub.billing_frequency}</strong> ($${sub.base_price})</div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 12px; background: var(--slate-50); border: 1px solid var(--slate-200); border-radius: var(--radius-sm); font-size: 12px;">
              <div><strong>Next Billing Date:</strong><br><span style="color: #2563eb; font-weight: 600;">${sub.next_billing_date || '—'}</span></div>
              <div><strong>Renewal Terms:</strong><br>${sub.payment_terms || 'Net 30'}</div>
              <div><strong>Contract Start:</strong><br>${sub.start_date}</div>
              <div><strong>Expiry Date:</strong><br>${sub.expiry_date || 'Ongoing'}</div>
            </div>
          </div>
        </div>

        <!-- Add-on Switcher Center -->
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Manage Subscription Add-ons</div>
              <div class="card-subtitle">Switch features on and off anytime. Changes take effect immediately.</div>
            </div>
          </div>
          <div class="card-body">
            ${addonListHtml || '<div style="color: var(--slate-400); font-size: 12.5px;">No switchable add-ons attached to this plan.</div>'}

            <div style="background: var(--blue-bg); border: 1px solid var(--blue-border); border-radius: var(--radius-sm); padding: 12px; font-size: 12px; color: var(--blue-text); margin-top: 14px;">
              <strong>Self-Service Billing:</strong> When you switch on an add-on mid-month, Brightloop automatically calculates pro-rated days remaining in your billing cycle.
            </div>
          </div>
        </div>
      </div>

      <!-- Invoices & Statement History -->
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Billing History & Invoices</div>
            <div class="card-subtitle">View and settle past statements</div>
          </div>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Invoice #</th>
                <th>Issued</th>
                <th>Due Date</th>
                <th>Total</th>
                <th>Paid</th>
                <th>Balance Due</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${invoiceRows || '<tr><td colspan="8" style="text-align: center; color: var(--slate-400); padding: 24px;">No statements generated yet.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    `;
  },

  async toggleCustomerAddon(subId, lineId, active) {
    try {
      const res = await app.api(`/api/subscriptions/${subId}/toggle-addon`, "POST", {
        line_id: lineId,
        active: active
      });
      const proration = res.proration_impact;
      const verb = active ? "activated" : "switched off";
      app.showToast(`Add-on '${res.product_name}' ${verb}! Pro-rated cost adjustment: $${proration.prorated_amount}`, "success");
      this.load();
    } catch (e) {
      // Handled
    }
  }
};

window.portalPage = portalPage;
