/*
 * Products & Variants Page Controller
 * Handles product catalog, variants with surcharges (e.g. Odoo brand +$560), and customer-switchable add-ons.
 */

const productsPage = {
  products: [],

  async load() {
    try {
      const res = await app.api("/api/products");
      this.products = res.products || [];
      this.renderTable(this.products);
    } catch (e) {
      console.error("Error loading products:", e);
    }
  },

  renderTable(products) {
    const tbody = document.getElementById("products-table-body");
    if (!tbody) return;

    if (!products.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--slate-400); padding: 32px;">No products in catalog.</td></tr>`;
      return;
    }

    tbody.innerHTML = products.map(p => {
      const margin = p.sales_price - p.cost_price;
      const marginPct = p.sales_price > 0 ? ((margin / p.sales_price) * 100).toFixed(1) : 0;

      const variantsHtml = (p.variants || []).length > 0
        ? p.variants.map(v => `
            <span style="display: inline-block; font-size: 11px; background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; border-radius: 4px; padding: 2px 6px; margin: 2px;">
              ${v.attribute_value} (+${v.price_surcharge > 0 ? '$' + v.price_surcharge : '$0'})
            </span>
          `).join("")
        : `<span style="color: var(--slate-400); font-size: 11.5px;">Standard only</span>`;

      const typeBadge = p.type === "addon"
        ? `<span class="status-pill status-paused">Customer Add-on</span>`
        : `<span class="status-pill status-confirmed">${p.type}</span>`;

      return `
        <tr>
          <td>
            <div style="font-weight: 700; color: var(--slate-900);">${p.name}</div>
            <div style="font-size: 11.5px; color: var(--slate-500);">${p.notes || ''}</div>
          </td>
          <td>${typeBadge}</td>
          <td style="font-weight: 700;">$${Number(p.sales_price).toFixed(2)}</td>
          <td style="color: var(--slate-500);">$${Number(p.cost_price).toFixed(2)}</td>
          <td>
            <span style="color: #16a34a; font-weight: 600;">$${margin.toFixed(2)} (${marginPct}%)</span>
          </td>
          <td style="max-width: 260px;">
            ${variantsHtml}
          </td>
          <td><span class="status-pill status-active">Active</span></td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="productsPage.openAddVariantModal(${p.id})">+ Variant</button>
          </td>
        </tr>
      `;
    }).join("");
  },

  openNewProductModal() {
    const html = `
      <div class="form-group">
        <label class="form-label">Product Name:</label>
        <input type="text" class="form-control" id="new-prod-name" placeholder="e.g. Brightloop Analytics Suite">
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Product Type:</label>
          <select class="form-control" id="new-prod-type">
            <option value="software">Software (Core SaaS Application)</option>
            <option value="addon">Add-on (Customer Switchable)</option>
            <option value="service">Service (Consulting / Account Management)</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Sales Price ($):</label>
          <input type="number" class="form-control" id="new-prod-sales-price" value="500.00" step="10">
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Cost Price ($):</label>
          <input type="number" class="form-control" id="new-prod-cost-price" value="100.00" step="10">
        </div>
        <div class="form-group">
          <label class="form-label">Initial Variant (Optional):</label>
          <input type="text" class="form-control" id="new-prod-init-variant" placeholder="e.g. Odoo Brand Integration">
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">Variant Price Surcharge ($):</label>
        <input type="number" class="form-control" id="new-prod-surcharge" value="560.00" step="10">
        <div class="form-hint">E.g. Choosing Odoo brand adds $560 to the sales price.</div>
      </div>

      <div class="form-group">
        <label class="form-label">Description / Internal Notes:</label>
        <textarea class="form-control" id="new-prod-notes" rows="2" placeholder="Product details..."></textarea>
      </div>
    `;

    const footer = `
      <button class="btn btn-secondary" onclick="app.closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="productsPage.submitProduct()">Save Product</button>
    `;

    app.openModal("Add Product to Catalog", html, footer);
  },

  async submitProduct() {
    const name = document.getElementById("new-prod-name").value.trim();
    const type = document.getElementById("new-prod-type").value;
    const salesPrice = parseFloat(document.getElementById("new-prod-sales-price").value) || 0;
    const costPrice = parseFloat(document.getElementById("new-prod-cost-price").value) || 0;
    const notes = document.getElementById("new-prod-notes").value;

    const varName = document.getElementById("new-prod-init-variant").value.trim();
    const surcharge = parseFloat(document.getElementById("new-prod-surcharge").value) || 0;

    if (!name) {
      app.showToast("Product name is required", "error");
      return;
    }

    const variants = [];
    if (varName) {
      variants.push({
        attribute_name: "Brand / Edition",
        attribute_value: varName,
        price_surcharge: surcharge
      });
    }

    try {
      await app.api("/api/products", "POST", {
        name,
        type,
        sales_price: salesPrice,
        cost_price: costPrice,
        notes,
        variants
      });

      app.showToast(`Product "${name}" added to catalog!`, "success");
      app.closeModal();
      this.load();
    } catch (e) {
      // Handled
    }
  },

  openAddVariantModal(productId) {
    const p = this.products.find(x => x.id === productId);
    if (!p) return;

    const html = `
      <div style="margin-bottom: 14px; font-weight: 600; color: var(--slate-700);">
        Adding variant to: <span style="color: #2563eb;">${p.name}</span> (Base: $${p.sales_price})
      </div>

      <div class="form-group">
        <label class="form-label">Attribute Category:</label>
        <input type="text" class="form-control" id="variant-attr-name" value="Brand Integration">
      </div>

      <div class="form-group">
        <label class="form-label">Variant Name / Option:</label>
        <input type="text" class="form-control" id="variant-attr-value" placeholder="e.g. Odoo Enterprise Brand">
      </div>

      <div class="form-group">
        <label class="form-label">Price Surcharge ($):</label>
        <input type="number" class="form-control" id="variant-surcharge" value="560.00" step="10">
        <div class="form-hint">Specifies how much extra choosing this variant adds to the price.</div>
      </div>
    `;

    const footer = `
      <button class="btn btn-secondary" onclick="app.closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="productsPage.submitVariant(${productId})">Add Variant</button>
    `;

    app.openModal("Add Product Variant", html, footer);
  },

  async submitVariant(productId) {
    const attrName = document.getElementById("variant-attr-name").value.trim();
    const attrValue = document.getElementById("variant-attr-value").value.trim();
    const surcharge = parseFloat(document.getElementById("variant-surcharge").value) || 0;

    if (!attrValue) {
      app.showToast("Variant option name is required", "error");
      return;
    }

    try {
      await app.api(`/api/products/${productId}/variants`, "POST", {
        attribute_name: attrName,
        attribute_value: attrValue,
        price_surcharge: surcharge
      });

      app.showToast(`Variant "${attrValue}" (+${surcharge}) added!`, "success");
      app.closeModal();
      this.load();
    } catch (e) {
      // Handled
    }
  }
};

window.productsPage = productsPage;
