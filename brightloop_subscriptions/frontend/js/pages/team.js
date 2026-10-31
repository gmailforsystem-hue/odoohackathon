/*
 * Team & RBAC Page Controller
 * Handles staff management, role permissions (Admin, Staff, Customer),
 * and password policy verification (>8 chars, uppercase, lowercase, special char).
 */

const teamPage = {
  async load() {
    try {
      const res = await app.api("/api/auth/users");
      this.renderTable(res.users || []);
    } catch (e) {
      console.error("Error loading team:", e);
    }
  },

  renderTable(users) {
    const tbody = document.getElementById("team-table-body");
    if (!tbody) return;

    if (!users.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--slate-400); padding: 32px;">No users found.</td></tr>`;
      return;
    }

    tbody.innerHTML = users.map(u => {
      const roleBadge = `<span class="role-tag ${u.role}">${u.role.toUpperCase()}</span>`;
      return `
        <tr>
          <td>
            <div style="font-weight: 700; color: var(--slate-900);">${u.full_name}</div>
          </td>
          <td>${u.email}</td>
          <td>${roleBadge}</td>
          <td>${u.company || 'Brightloop Internal'}</td>
          <td style="font-size: 12.5px; color: var(--slate-500);">${u.created_at ? u.created_at.split('T')[0] : '2026-10-01'}</td>
        </tr>
      `;
    }).join("");
  },

  openInviteStaffModal() {
    if (app.currentRole !== "admin") {
      app.showToast("Forbidden: Only administrators can add staff members.", "error");
      return;
    }

    const html = `
      <div class="form-group">
        <label class="form-label">Full Name:</label>
        <input type="text" class="form-control" id="staff-name" placeholder="e.g. Rachel Adams">
      </div>

      <div class="form-group">
        <label class="form-label">Email Address:</label>
        <input type="email" class="form-control" id="staff-email" placeholder="rachel@brightloop.com">
      </div>

      <div class="form-group">
        <label class="form-label">System Role:</label>
        <select class="form-control" id="staff-role">
          <option value="staff">Internal Staff (Sales & Invoicing day-to-day operations)</option>
          <option value="admin">Administrator (Full control, staff invites & global settings)</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label">Temporary Password:</label>
        <input type="text" class="form-control" id="staff-password" value="Brightloop#2026" oninput="teamPage.onPasswordInput(this.value)">
        <div id="staff-pwd-feedback" style="font-size: 12px; margin-top: 4px; font-weight: 600; color: #15803d;">
          Password meets all requirements (>8 chars, 1 uppercase, 1 lowercase, 1 special character).
        </div>
      </div>
    `;

    const footer = `
      <button class="btn btn-secondary" onclick="app.closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="teamPage.submitStaff()">Add Staff Member</button>
    `;

    app.openModal("Add New Internal Staff Member", html, footer);
  },

  onPasswordInput(pwd) {
    const feedback = document.getElementById("staff-pwd-feedback");
    if (!feedback) return;

    const errors = [];
    if (pwd.length <= 8) errors.push(">8 characters");
    if (!/[A-Z]/.test(pwd)) errors.push("1 uppercase letter");
    if (!/[a-z]/.test(pwd)) errors.push("1 lowercase letter");
    if (!/[^a-zA-Z0-9]/.test(pwd)) errors.push("1 special character");

    if (errors.length === 0) {
      feedback.textContent = "Password meets all security requirements.";
      feedback.style.color = "#15803d";
    } else {
      feedback.textContent = "Missing requirements: " + errors.join(", ");
      feedback.style.color = "#b91c1c";
    }
  },

  async submitStaff() {
    const name = document.getElementById("staff-name").value.trim();
    const email = document.getElementById("staff-email").value.trim();
    const role = document.getElementById("staff-role").value;
    const password = document.getElementById("staff-password").value;

    if (!name || !email) {
      app.showToast("Full name and email are required", "error");
      return;
    }

    try {
      await app.api("/api/team/invite", "POST", {
        full_name: name,
        email: email,
        role: role,
        password: password
      });

      app.showToast(`Staff member "${name}" added successfully!`, "success");
      app.closeModal();
      this.load();
    } catch (e) {
      // Handled
    }
  }
};

window.teamPage = teamPage;
