"""
High-Performance REST API & Static File Server for Brightloop Subscription Management.
Built exclusively using Python 3.14 standard library (http.server, json, sqlite3, urllib).
Provides all endpoints for RBAC, Catalog, Plans, Quotations, Subscriptions, Invoices,
Payments, Taxes, Discounts, Reports, and High-Volume Scale-Up Benchmarking.
"""

import http.server
import socketserver
import json
import urllib.parse
import os
import sys
import time
import secrets
from datetime import datetime, timedelta

# Path setups
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
sys.path.insert(0, BASE_DIR)

import database
import billing_engine

PORT = 8000


class BrightloopHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def _set_headers(self, status_code=200, content_type="application/json"):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-User-Role, X-User-Email")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def _send_json(self, data, status_code=200, start_time=None):
        if start_time is not None and isinstance(data, dict):
            latency_ms = round((time.time() - start_time) * 1000, 2)
            data["_server_latency_ms"] = latency_ms
        self._set_headers(status_code, "application/json")
        self.wfile.write(json.dumps(data, indent=2, default=str).encode("utf-8"))

    def _send_error(self, message, status_code=400):
        self._set_headers(status_code, "application/json")
        self.wfile.write(json.dumps({"status": "error", "message": message}).encode("utf-8"))

    def _read_body(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len > 0:
                body_bytes = self.rfile.read(content_len)
                return json.loads(body_bytes.decode("utf-8"))
            return {}
        except Exception as e:
            print("Error parsing JSON body:", e)
            return {}

    def _get_user_context(self):
        role = self.headers.get("X-User-Role", "admin")
        email = self.headers.get("X-User-Email", "admin@brightloop.com")
        return {"role": role, "email": email}

    # ==========================================
    # GET ROUTES
    # ==========================================
    def do_GET(self):
        start_time = time.time()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # Serve Frontend Static Assets if not an API request
        if not path.startswith("/api/"):
            return super().do_GET()

        try:
            conn = database.get_db()
            cur = conn.cursor()

            # 1. Auth & Users
            if path == "/api/auth/users":
                role_filter = params.get("role", [None])[0]
                if role_filter:
                    cur.execute("SELECT id, email, role, full_name, company, created_at FROM users WHERE role = ? ORDER BY id DESC", (role_filter,))
                else:
                    cur.execute("SELECT id, email, role, full_name, company, created_at FROM users ORDER BY id DESC")
                users = [dict(r) for r in cur.fetchall()]
                conn.close()
                return self._send_json({"status": "success", "users": users}, start_time=start_time)

            # 2. Products & Variants
            elif path == "/api/products":
                cur.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY id ASC")
                products = [dict(r) for r in cur.fetchall()]
                for p in products:
                    cur.execute("SELECT * FROM product_variants WHERE product_id = ?", (p["id"],))
                    p["variants"] = [dict(v) for v in cur.fetchall()]
                conn.close()
                return self._send_json({"status": "success", "products": products}, start_time=start_time)

            # 3. Plans
            elif path == "/api/plans":
                cur.execute("SELECT * FROM plans ORDER BY id ASC")
                plans = [dict(r) for r in cur.fetchall()]
                conn.close()
                return self._send_json({"status": "success", "plans": plans}, start_time=start_time)

            # 4. Quotation Templates
            elif path == "/api/quotations/templates":
                cur.execute("""
                SELECT qt.*, p.name AS default_plan_name, p.billing_frequency, p.base_price
                FROM quotation_templates qt
                LEFT JOIN plans p ON qt.default_plan_id = p.id
                ORDER BY qt.id ASC
                """)
                templates = [dict(r) for r in cur.fetchall()]
                for t in templates:
                    cur.execute("""
                    SELECT qtl.*, pr.name AS product_name, pr.sales_price, pv.attribute_value AS variant_name, pv.price_surcharge
                    FROM quotation_template_lines qtl
                    JOIN products pr ON qtl.product_id = pr.id
                    LEFT JOIN product_variants pv ON qtl.variant_id = pv.id
                    WHERE qtl.template_id = ?
                    """, (t["id"],))
                    t["lines"] = [dict(l) for l in cur.fetchall()]
                conn.close()
                return self._send_json({"status": "success", "templates": templates}, start_time=start_time)

            # 5. Subscriptions (with fast pagination and filtering)
            elif path == "/api/subscriptions":
                status = params.get("status", [None])[0]
                customer_id = params.get("customer_id", [None])[0]
                search = params.get("search", [None])[0]
                limit = int(params.get("limit", [50])[0])
                offset = int(params.get("offset", [0])[0])

                query = """
                SELECT s.*, u.full_name AS customer_name, u.email AS customer_email, u.company AS customer_company,
                       p.name AS plan_name, p.billing_frequency, p.base_price, p.allow_pause, p.allow_early_close, p.allow_renew
                FROM subscriptions s
                JOIN users u ON s.customer_id = u.id
                JOIN plans p ON s.plan_id = p.id
                WHERE 1=1
                """
                query_params = []

                if status:
                    query += " AND s.status = ?"
                    query_params.append(status)
                if customer_id:
                    query += " AND s.customer_id = ?"
                    query_params.append(customer_id)
                if search:
                    query += " AND (s.sub_number LIKE ? OR u.full_name LIKE ? OR u.company LIKE ?)"
                    s_wild = f"%{search}%"
                    query_params.extend([s_wild, s_wild, s_wild])

                # Get total count
                count_query = "SELECT COUNT(*) FROM (" + query + ")"
                cur.execute(count_query, query_params)
                total_count = cur.fetchone()[0]

                query += " ORDER BY s.id DESC LIMIT ? OFFSET ?"
                query_params.extend([limit, offset])

                cur.execute(query, query_params)
                subs = [dict(r) for r in cur.fetchall()]
                conn.close()
                return self._send_json({"status": "success", "total": total_count, "limit": limit, "offset": offset, "subscriptions": subs}, start_time=start_time)

            elif path.startswith("/api/subscriptions/"):
                sub_id = int(path.split("/")[3])
                cur.execute("""
                SELECT s.*, u.full_name AS customer_name, u.email AS customer_email, u.company AS customer_company,
                       p.name AS plan_name, p.billing_frequency, p.base_price, p.allow_pause, p.allow_early_close, p.allow_renew
                FROM subscriptions s
                JOIN users u ON s.customer_id = u.id
                JOIN plans p ON s.plan_id = p.id
                WHERE s.id = ?
                """, (sub_id,))
                sub = cur.fetchone()
                if not sub:
                    conn.close()
                    return self._send_error("Subscription not found", 404)

                sub_data = dict(sub)
                cur.execute("""
                SELECT sl.*, pr.name AS product_name, pr.sales_price, pr.type AS product_type,
                       pv.attribute_value AS variant_name, COALESCE(pv.price_surcharge, 0.0) AS price_surcharge,
                       t.name AS tax_name, t.rate_percent AS tax_rate,
                       d.code AS discount_code, d.value AS discount_value, d.discount_type
                FROM subscription_lines sl
                JOIN products pr ON sl.product_id = pr.id
                LEFT JOIN product_variants pv ON sl.variant_id = pv.id
                LEFT JOIN taxes t ON sl.tax_id = t.id
                LEFT JOIN discounts d ON sl.discount_id = d.id
                WHERE sl.subscription_id = ?
                """, (sub_id,))
                sub_data["lines"] = [dict(l) for l in cur.fetchall()]

                # Related invoices
                cur.execute("SELECT * FROM invoices WHERE subscription_id = ? ORDER BY id DESC", (sub_id,))
                sub_data["invoices"] = [dict(i) for r in cur.fetchall()]

                conn.close()
                return self._send_json({"status": "success", "subscription": sub_data}, start_time=start_time)

            # 6. Taxes & Discounts
            elif path == "/api/taxes":
                cur.execute("SELECT * FROM taxes ORDER BY id ASC")
                taxes = [dict(r) for r in cur.fetchall()]
                conn.close()
                return self._send_json({"status": "success", "taxes": taxes}, start_time=start_time)

            elif path == "/api/discounts":
                cur.execute("""
                SELECT d.*, p.name AS product_name
                FROM discounts d
                LEFT JOIN products p ON d.product_id = p.id
                ORDER BY d.id DESC
                """)
                discounts = [dict(r) for r in cur.fetchall()]
                conn.close()
                return self._send_json({"status": "success", "discounts": discounts}, start_time=start_time)

            # 7. Invoices
            elif path == "/api/invoices":
                status = params.get("status", [None])[0]
                customer_id = params.get("customer_id", [None])[0]
                limit = int(params.get("limit", [50])[0])
                offset = int(params.get("offset", [0])[0])

                # Run quick reconcile
                billing_engine.reconcile_overdue_invoices()

                query = """
                SELECT i.*, u.full_name AS customer_name, u.email AS customer_email, u.company AS customer_company,
                       s.sub_number
                FROM invoices i
                JOIN users u ON i.customer_id = u.id
                LEFT JOIN subscriptions s ON i.subscription_id = s.id
                WHERE 1=1
                """
                query_params = []
                if status:
                    query += " AND i.status = ?"
                    query_params.append(status)
                if customer_id:
                    query += " AND i.customer_id = ?"
                    query_params.append(customer_id)

                count_query = "SELECT COUNT(*) FROM (" + query + ")"
                cur.execute(count_query, query_params)
                total_count = cur.fetchone()[0]

                query += " ORDER BY i.id DESC LIMIT ? OFFSET ?"
                query_params.extend([limit, offset])

                cur.execute(query, query_params)
                invoices = [dict(r) for r in cur.fetchall()]
                conn.close()
                return self._send_json({"status": "success", "total": total_count, "invoices": invoices}, start_time=start_time)

            elif path.startswith("/api/invoices/"):
                inv_id = int(path.split("/")[3])
                cur.execute("""
                SELECT i.*, u.full_name AS customer_name, u.email AS customer_email, u.company AS customer_company,
                       s.sub_number, s.payment_terms
                FROM invoices i
                JOIN users u ON i.customer_id = u.id
                LEFT JOIN subscriptions s ON i.subscription_id = s.id
                WHERE i.id = ?
                """, (inv_id,))
                inv = cur.fetchone()
                if not inv:
                    conn.close()
                    return self._send_error("Invoice not found", 404)

                inv_data = dict(inv)
                cur.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?", (inv_id,))
                inv_data["lines"] = [dict(l) for l in cur.fetchall()]

                cur.execute("SELECT * FROM payments WHERE invoice_id = ? ORDER BY id DESC", (inv_id,))
                inv_data["payments"] = [dict(p) for p in cur.fetchall()]

                conn.close()
                return self._send_json({"status": "success", "invoice": inv_data}, start_time=start_time)

            # 8. Payments
            elif path == "/api/payments":
                customer_id = params.get("customer_id", [None])[0]
                query = """
                SELECT p.*, i.invoice_number, i.total_amount AS invoice_total, u.full_name AS customer_name
                FROM payments p
                JOIN invoices i ON p.invoice_id = i.id
                JOIN users u ON p.customer_id = u.id
                """
                query_params = []
                if customer_id:
                    query += " WHERE p.customer_id = ?"
                    query_params.append(customer_id)
                query += " ORDER BY p.id DESC LIMIT 100"

                cur.execute(query, query_params)
                payments = [dict(r) for r in cur.fetchall()]
                conn.close()
                return self._send_json({"status": "success", "payments": payments}, start_time=start_time)

            # 9. Finance & Reports (The Finance Lead requirements)
            elif path == "/api/reports/summary":
                billing_engine.reconcile_overdue_invoices()

                # Active subscriptions count
                cur.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'active'")
                active_subs_count = cur.fetchone()[0]

                # MRR Calculation (Normalizes Monthly, Yearly, Weekly, Daily to monthly equivalent)
                cur.execute("""
                SELECT p.billing_frequency, COALESCE(SUM(sl.line_amount), 0.0) AS total_amount
                FROM subscriptions s
                JOIN plans p ON s.plan_id = p.id
                LEFT JOIN subscription_lines sl ON s.id = sl.subscription_id AND (sl.is_addon = 0 OR sl.addon_active = 1)
                WHERE s.status = 'active'
                GROUP BY p.billing_frequency
                """)
                mrr = 0.0
                for row in cur.fetchall():
                    freq = row["billing_frequency"]
                    amt = float(row["total_amount"])
                    if freq == "monthly":
                        mrr += amt
                    elif freq == "yearly":
                        mrr += amt / 12.0
                    elif freq == "weekly":
                        mrr += amt * 4.33
                    elif freq == "daily":
                        mrr += amt * 30.0

                arr = mrr * 12.0

                # Revenue Collected
                cur.execute("SELECT COALESCE(SUM(amount), 0.0) FROM payments")
                total_revenue_collected = float(cur.fetchone()[0])

                # Outstanding Balance Owed
                cur.execute("SELECT COALESCE(SUM(total_amount - paid_amount), 0.0) FROM invoices WHERE status IN ('confirmed', 'overdue', 'partially_paid')")
                total_outstanding = float(cur.fetchone()[0])

                # Overdue Invoices
                cur.execute("SELECT COUNT(*), COALESCE(SUM(total_amount - paid_amount), 0.0) FROM invoices WHERE status = 'overdue'")
                overdue_row = cur.fetchone()
                overdue_count = overdue_row[0]
                overdue_amount = float(overdue_row[1])

                conn.close()
                return self._send_json({
                    "status": "success",
                    "active_subscriptions": active_subs_count,
                    "mrr": round(mrr, 2),
                    "arr": round(arr, 2),
                    "total_revenue_collected": round(total_revenue_collected, 2),
                    "total_outstanding_owed": round(total_outstanding, 2),
                    "overdue_invoices_count": overdue_count,
                    "overdue_invoices_amount": round(overdue_amount, 2)
                }, start_time=start_time)

            elif path == "/api/reports/aging":
                billing_engine.reconcile_overdue_invoices()
                today_dt = datetime.now()

                cur.execute("SELECT id, invoice_number, customer_id, due_date, total_amount, paid_amount FROM invoices WHERE status IN ('confirmed', 'overdue', 'partially_paid')")
                unpaid = cur.fetchall()

                current_bucket = 0.0
                bucket_1_30 = 0.0
                bucket_31_60 = 0.0
                bucket_60_plus = 0.0

                for inv in unpaid:
                    balance = float(inv["total_amount"]) - float(inv["paid_amount"])
                    try:
                        due_dt = datetime.strptime(inv["due_date"], "%Y-%m-%d")
                        diff_days = (today_dt - due_dt).days
                    except Exception:
                        diff_days = 0

                    if diff_days <= 0:
                        current_bucket += balance
                    elif diff_days <= 30:
                        bucket_1_30 += balance
                    elif diff_days <= 60:
                        bucket_31_60 += balance
                    else:
                        bucket_60_plus += balance

                conn.close()
                return self._send_json({
                    "status": "success",
                    "aging_report": {
                        "current": round(current_bucket, 2),
                        "1_to_30_days": round(bucket_1_30, 2),
                        "31_to_60_days": round(bucket_31_60, 2),
                        "over_60_days": round(bucket_60_plus, 2)
                    }
                }, start_time=start_time)

            # 10. Audit Logs
            elif path == "/api/audit/logs":
                cur.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 50")
                logs = [dict(r) for r in cur.fetchall()]
                conn.close()
                return self._send_json({"status": "success", "audit_logs": logs}, start_time=start_time)

            else:
                conn.close()
                return self._send_error("Endpoint not found", 404)

        except Exception as e:
            print("GET Error:", e)
            return self._send_error(str(e), 500)

    # ==========================================
    # POST ROUTES
    # ==========================================
    def do_POST(self):
        start_time = time.time()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_body()
        user_ctx = self._get_user_context()

        try:
            conn = database.get_db()
            cur = conn.cursor()

            # 1. User Registration & Auth
            if path == "/api/auth/register":
                email = body.get("email", "").strip().lower()
                password = body.get("password", "")
                full_name = body.get("full_name", "").strip()
                company = body.get("company", "").strip()
                role = body.get("role", "customer")

                if not email or not password or not full_name:
                    conn.close()
                    return self._send_error("Email, password, and full name are required.")

                # Unique email constraint check
                cur.execute("SELECT id FROM users WHERE email = ?", (email,))
                if cur.fetchone():
                    conn.close()
                    return self._send_error("An account with this email address already exists.")

                # Password policy check (>8 chars, uppercase, lowercase, special char)
                is_valid, msg = billing_engine.validate_password_strength(password)
                if not is_valid:
                    conn.close()
                    return self._send_error(msg)

                pw_hash = database.hash_password(password)
                now_iso = datetime.now().isoformat()

                cur.execute("""
                INSERT INTO users (email, password_hash, role, full_name, company, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (email, pw_hash, role, full_name, company, now_iso))
                new_id = cur.lastrowid

                # Audit log
                cur.execute("INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details) VALUES (?, ?, 'REGISTER_USER', 'user', ?, ?)",
                            (now_iso, email, str(new_id), f"User registered as {role}: {full_name} ({company})"))

                conn.commit()
                conn.close()
                return self._send_json({
                    "status": "success",
                    "message": "Account created successfully.",
                    "user": {"id": new_id, "email": email, "role": role, "full_name": full_name, "company": company}
                }, start_time=start_time)

            elif path == "/api/auth/login":
                email = body.get("email", "").strip().lower()
                password = body.get("password", "")

                cur.execute("SELECT * FROM users WHERE email = ?", (email,))
                user = cur.fetchone()
                if not user or not database.verify_password(password, user["password_hash"]):
                    conn.close()
                    return self._send_error("Invalid email or password.")

                user_data = {
                    "id": user["id"],
                    "email": user["email"],
                    "role": user["role"],
                    "full_name": user["full_name"],
                    "company": user["company"]
                }
                conn.close()
                return self._send_json({"status": "success", "user": user_data}, start_time=start_time)

            elif path == "/api/auth/forgot-password":
                email = body.get("email", "").strip().lower()
                cur.execute("SELECT id FROM users WHERE email = ?", (email,))
                user = cur.fetchone()
                if not user:
                    conn.close()
                    # Generic response for security
                    return self._send_json({"status": "success", "message": "If an account exists with that email, a password reset link has been dispatched."})

                token = secrets.token_urlsafe(32)
                expires = (datetime.now() + timedelta(hours=2)).isoformat()
                cur.execute("INSERT INTO reset_tokens (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user["id"], expires))

                # Audit log
                cur.execute("INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details) VALUES (?, ?, 'PASSWORD_RESET_REQ', 'user', ?, ?)",
                            (datetime.now().isoformat(), email, str(user["id"]), f"Password reset requested. Simulated token: {token[:8]}..."))

                conn.commit()
                conn.close()
                return self._send_json({
                    "status": "success",
                    "message": f"Password reset link generated for {email}.",
                    "reset_token": token,
                    "simulated_reset_url": f"/#reset-password?token={token}"
                }, start_time=start_time)

            elif path == "/api/auth/reset-password":
                token = body.get("token", "")
                new_password = body.get("new_password", "")

                cur.execute("SELECT * FROM reset_tokens WHERE token = ? AND used = 0", (token,))
                tok_row = cur.fetchone()
                if not tok_row:
                    conn.close()
                    return self._send_error("Invalid or expired password reset token.")

                is_valid, msg = billing_engine.validate_password_strength(new_password)
                if not is_valid:
                    conn.close()
                    return self._send_error(msg)

                pw_hash = database.hash_password(new_password)
                cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, tok_row["user_id"]))
                cur.execute("UPDATE reset_tokens SET used = 1 WHERE id = ?", (tok_row["id"],))

                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "message": "Password has been successfully reset. You may now log in."}, start_time=start_time)

            elif path == "/api/team/invite":
                if user_ctx["role"] != "admin":
                    conn.close()
                    return self._send_error("Forbidden: Only administrators can add or invite new staff members.", 403)

                email = body.get("email", "").strip().lower()
                full_name = body.get("full_name", "").strip()
                role = body.get("role", "staff")
                password = body.get("password", "Brightloop#2026")

                is_valid, msg = billing_engine.validate_password_strength(password)
                if not is_valid:
                    conn.close()
                    return self._send_error(msg)

                pw_hash = database.hash_password(password)
                now_iso = datetime.now().isoformat()
                cur.execute("""
                INSERT INTO users (email, password_hash, role, full_name, company, created_at)
                VALUES (?, ?, ?, ?, 'Brightloop Software', ?)
                """, (email, pw_hash, role, full_name, now_iso))
                new_staff_id = cur.lastrowid

                cur.execute("INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details) VALUES (?, ?, 'INVITE_STAFF', 'team', ?, ?)",
                            (now_iso, user_ctx["email"], str(new_staff_id), f"Added new staff member {full_name} ({email}) with role {role}"))

                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "message": f"Staff member {full_name} created successfully."}, start_time=start_time)

            # 2. Products & Variants Management
            elif path == "/api/products":
                name = body.get("name", "").strip()
                p_type = body.get("type", "software")
                sales_p = float(body.get("sales_price", 0))
                cost_p = float(body.get("cost_price", 0))
                notes = body.get("notes", "")

                now_iso = datetime.now().isoformat()
                cur.execute("""
                INSERT INTO products (name, type, sales_price, cost_price, notes, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """, (name, p_type, sales_p, cost_p, notes, now_iso))
                prod_id = cur.lastrowid

                # Optional initial variant
                variants_list = body.get("variants", [])
                for v in variants_list:
                    cur.execute("""
                    INSERT INTO product_variants (product_id, attribute_name, attribute_value, price_surcharge)
                    VALUES (?, ?, ?, ?)
                    """, (prod_id, v.get("attribute_name", "Brand"), v.get("attribute_value", ""), float(v.get("price_surcharge", 0))))

                cur.execute("INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details) VALUES (?, ?, 'CREATE_PRODUCT', 'product', ?, ?)",
                            (now_iso, user_ctx["email"], str(prod_id), f"Created product: {name} (${sales_p})"))

                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "product_id": prod_id}, start_time=start_time)

            elif path.startswith("/api/products/") and path.endswith("/variants"):
                prod_id = int(path.split("/")[3])
                attr_name = body.get("attribute_name", "Brand")
                attr_val = body.get("attribute_value", "")
                surcharge = float(body.get("price_surcharge", 0.0))

                cur.execute("""
                INSERT INTO product_variants (product_id, attribute_name, attribute_value, price_surcharge)
                VALUES (?, ?, ?, ?)
                """, (prod_id, attr_name, attr_val, surcharge))
                var_id = cur.lastrowid

                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "variant_id": var_id}, start_time=start_time)

            # 3. Plans
            elif path == "/api/plans":
                name = body.get("name", "").strip()
                freq = body.get("billing_frequency", "monthly")
                base_price = float(body.get("base_price", 0))
                min_qty = int(body.get("min_quantity", 1))
                valid_from = body.get("valid_from", datetime.now().strftime("%Y-%m-%d"))
                valid_to = body.get("valid_to", "2028-12-31")
                auto_close = 1 if body.get("auto_close") else 0
                allow_early_close = 1 if body.get("allow_early_close", True) else 0
                allow_pause = 1 if body.get("allow_pause", True) else 0
                allow_renew = 1 if body.get("allow_renew", True) else 0

                now_iso = datetime.now().isoformat()
                cur.execute("""
                INSERT INTO plans (name, billing_frequency, base_price, min_quantity, valid_from, valid_to, auto_close, allow_early_close, allow_pause, allow_renew, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, freq, base_price, min_qty, valid_from, valid_to, auto_close, allow_early_close, allow_pause, allow_renew, now_iso))
                plan_id = cur.lastrowid

                cur.execute("INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details) VALUES (?, ?, 'CREATE_PLAN', 'plan', ?, ?)",
                            (now_iso, user_ctx["email"], str(plan_id), f"Created plan {name} ({freq}) at ${base_price}"))

                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "plan_id": plan_id}, start_time=start_time)

            # 4. Quotations
            elif path == "/api/quotations":
                cust_id = int(body.get("customer_id"))
                plan_id = int(body.get("plan_id"))
                valid_days = int(body.get("validity_days", 30))
                notes = body.get("notes", "")

                today = datetime.now()
                start_date = today.strftime("%Y-%m-%d")
                exp_date = (today + timedelta(days=valid_days)).strftime("%Y-%m-%d")

                cur.execute("SELECT COUNT(*) FROM subscriptions")
                sub_seq = cur.fetchone()[0] + 1
                sub_num = f"QT-2026-{sub_seq:04d}"

                cur.execute("""
                INSERT INTO subscriptions (sub_number, customer_id, plan_id, status, start_date, expiry_date, next_billing_date, payment_terms, auto_renew, notes, created_by, created_at)
                VALUES (?, ?, ?, 'quotation', ?, ?, ?, 'Net 30', 1, ?, 1, ?)
                """, (sub_num, cust_id, plan_id, start_date, exp_date, start_date, notes, today.isoformat()))
                new_sub_id = cur.lastrowid

                # Add lines
                lines = body.get("lines", [])
                for line in lines:
                    p_id = int(line.get("product_id"))
                    v_id = line.get("variant_id")
                    qty = int(line.get("quantity", 1))
                    unit_p = float(line.get("unit_price", 0))
                    tax_id = line.get("tax_id")
                    disc_id = line.get("discount_id")
                    is_addon = 1 if line.get("is_addon") else 0
                    line_amt = qty * unit_p

                    cur.execute("""
                    INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_id, discount_id, line_amount, is_addon, addon_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (new_sub_id, p_id, v_id, qty, unit_p, tax_id, disc_id, line_amt, is_addon))

                cur.execute("INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details) VALUES (?, ?, 'CREATE_QUOTE', 'quotation', ?, ?)",
                            (today.isoformat(), user_ctx["email"], sub_num, f"Generated sales quotation {sub_num}"))

                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "quotation_id": new_sub_id, "quotation_number": sub_num}, start_time=start_time)

            elif path.startswith("/api/quotations/") and path.endswith("/convert"):
                quote_id = int(path.split("/")[3])
                cur.execute("SELECT * FROM subscriptions WHERE id = ?", (quote_id,))
                q = cur.fetchone()
                if not q:
                    conn.close()
                    return self._send_error("Quotation not found", 404)

                cur.execute("SELECT COUNT(*) FROM subscriptions WHERE sub_number LIKE 'SUB-%'")
                seq = cur.fetchone()[0] + 1
                new_sub_num = f"SUB-2026-{seq:04d}"

                cur.execute("""
                UPDATE subscriptions
                SET status = 'active', sub_number = ?
                WHERE id = ?
                """, (new_sub_num, quote_id))

                cur.execute("INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details) VALUES (?, ?, 'CONVERT_QUOTE', 'subscription', ?, ?)",
                            (datetime.now().isoformat(), user_ctx["email"], new_sub_num, f"Converted quote {q['sub_number']} to active subscription {new_sub_num}"))

                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "subscription_number": new_sub_num, "status_label": "active"}, start_time=start_time)

            # 5. Subscription Lifecycle Transition & Add-on Switcher
            elif path.startswith("/api/subscriptions/") and path.endswith("/transition"):
                sub_id = int(path.split("/")[3])
                target_status = body.get("status")
                valid_transitions = ['draft', 'quotation', 'confirmed', 'active', 'paused', 'closed']

                if target_status not in valid_transitions:
                    conn.close()
                    return self._send_error(f"Invalid transition status: {target_status}")

                cur.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
                sub = cur.fetchone()
                if not sub:
                    conn.close()
                    return self._send_error("Subscription not found", 404)

                now_iso = datetime.now().isoformat()
                cur.execute("UPDATE subscriptions SET status = ? WHERE id = ?", (target_status, sub_id))

                cur.execute("INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details) VALUES (?, ?, 'TRANSITION_SUB', 'subscription', ?, ?)",
                            (now_iso, user_ctx["email"], sub["sub_number"], f"Moved subscription from {sub['status']} to {target_status}"))

                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "new_status": target_status}, start_time=start_time)

            elif path.startswith("/api/subscriptions/") and path.endswith("/toggle-addon"):
                sub_id = int(path.split("/")[3])
                line_id = int(body.get("line_id"))
                active_state = 1 if body.get("active") else 0

                cur.execute("""
                SELECT sl.*, p.name AS product_name, p.sales_price, s.sub_number, s.start_date, s.next_billing_date
                FROM subscription_lines sl
                JOIN products p ON sl.product_id = p.id
                JOIN subscriptions s ON sl.subscription_id = s.id
                WHERE sl.id = ? AND sl.subscription_id = ?
                """, (line_id, sub_id))
                line = cur.fetchone()
                if not line:
                    conn.close()
                    return self._send_error("Add-on line not found", 404)

                cur.execute("UPDATE subscription_lines SET addon_active = ? WHERE id = ?", (active_state, line_id))

                # Calculate proration feedback
                today_str = datetime.now().strftime("%Y-%m-%d")
                cycle_end = line["next_billing_date"] or (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                proration = billing_engine.calculate_proration(float(line["sales_price"]), line["start_date"], cycle_end, today_str)

                action_verb = "activated" if active_state else "switched off"
                cur.execute("INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details) VALUES (?, ?, 'TOGGLE_ADDON', 'addon', ?, ?)",
                            (datetime.now().isoformat(), user_ctx["email"], line["sub_number"], f"Add-on '{line['product_name']}' {action_verb}. Prorated impact: ${proration['prorated_amount']}"))

                conn.commit()
                conn.close()
                return self._send_json({
                    "status": "success",
                    "addon_active": bool(active_state),
                    "product_name": line["product_name"],
                    "proration_impact": proration
                }, start_time=start_time)

            # 6. Taxes & Discounts
            elif path == "/api/taxes":
                name = body.get("name", "").strip()
                rate = float(body.get("rate_percent", 0.0))
                cur.execute("INSERT INTO taxes (name, rate_percent, is_active) VALUES (?, ?, 1)", (name, rate))
                t_id = cur.lastrowid
                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "tax_id": t_id}, start_time=start_time)

            elif path == "/api/discounts":
                code = body.get("code", "").strip().upper()
                desc = body.get("description", "")
                d_type = body.get("discount_type", "percentage")
                val = float(body.get("value", 0))
                min_amt = float(body.get("min_amount", 0))
                min_qty = int(body.get("min_quantity", 0))
                start_d = body.get("start_date", datetime.now().strftime("%Y-%m-%d"))
                end_d = body.get("end_date", "2027-12-31")
                max_u = int(body.get("max_uses", 100))
                apply_to = body.get("apply_to", "all")
                prod_id = body.get("product_id")

                cur.execute("""
                INSERT INTO discounts (code, description, discount_type, value, min_amount, min_quantity, start_date, end_date, max_uses, times_used, apply_to, product_id, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 1)
                """, (code, desc, d_type, val, min_amt, min_qty, start_d, end_d, max_u, apply_to, prod_id))
                disc_id = cur.lastrowid
                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "discount_id": disc_id}, start_time=start_time)

            # 7. Automated Billing Day Execution
            elif path == "/api/billing/run-day":
                target_date = body.get("target_date")
                conn.close()
                result = billing_engine.run_billing_day(target_date, user_ctx["email"])
                return self._send_json(result, start_time=start_time)

            # 8. Record Payment against Invoice
            elif path == "/api/payments":
                inv_id = int(body.get("invoice_id"))
                amount = float(body.get("amount", 0.0))
                method = body.get("method", "credit_card")
                pay_date = body.get("payment_date", datetime.now().strftime("%Y-%m-%d"))
                notes = body.get("reference_notes", "")

                conn.close()
                result = billing_engine.record_payment_against_invoice(inv_id, amount, method, pay_date, notes, user_ctx["email"])
                if result.get("status") == "error":
                    return self._send_error(result["message"])
                return self._send_json(result, start_time=start_time)

            # 9. Invoice State Transitions
            elif path.startswith("/api/invoices/") and path.endswith("/confirm"):
                inv_id = int(path.split("/")[3])
                cur.execute("UPDATE invoices SET status = 'confirmed' WHERE id = ? AND status = 'draft'", (inv_id,))
                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "invoice_status": "confirmed"}, start_time=start_time)

            elif path.startswith("/api/invoices/") and path.endswith("/cancel"):
                inv_id = int(path.split("/")[3])
                cur.execute("UPDATE invoices SET status = 'cancelled' WHERE id = ?", (inv_id,))
                conn.commit()
                conn.close()
                return self._send_json({"status": "success", "invoice_status": "cancelled"}, start_time=start_time)

            # 10. High-Volume Scale Benchmark Data Generator
            elif path == "/api/demo/generate-bulk":
                count = int(body.get("count", 1000))
                conn.close()
                t0 = time.time()
                total_inserted = database.generate_bulk_demo_records(count)
                dur_ms = round((time.time() - t0) * 1000, 2)
                return self._send_json({
                    "status": "success",
                    "inserted_records_count": total_inserted,
                    "generation_time_ms": dur_ms,
                    "message": f"Successfully injected {total_inserted} high-volume subscriptions and invoices to stress test latency."
                }, start_time=start_time)

            else:
                conn.close()
                return self._send_error("Endpoint not found", 404)

        except Exception as e:
            print("POST Error:", e)
            return self._send_error(str(e), 500)


def run_server():
    database.init_db()
    database.seed_data()

    # Re-use socket address to avoid TIME_WAIT blocks
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), BrightloopHandler) as httpd:
        print(f"================================================================")
        print(f"Brightloop Subscription Platform running at http://localhost:{PORT}")
        print(f"Serving static frontend files from {FRONTEND_DIR}")
        print(f"================================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Brightloop server.")
            httpd.server_close()


if __name__ == "__main__":
    run_server()
