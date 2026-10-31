"""
Database layer for Brightloop Software Subscription Management System.
Uses Python standard library sqlite3 with robust schema, indexes, and seed data.
"""

import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "brightloop.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def hash_password(password: str) -> str:
    """Hash password with PBKDF2-SHA256."""
    salt = "brightloop_salt_2026"
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password


def init_db():
    """Create all tables and high-performance indexes."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'staff', 'customer')),
        full_name TEXT NOT NULL,
        company TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('software', 'addon', 'service')),
        sales_price REAL NOT NULL,
        cost_price REAL NOT NULL,
        notes TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS product_variants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        attribute_name TEXT NOT NULL,
        attribute_value TEXT NOT NULL,
        price_surcharge REAL DEFAULT 0.0
    );

    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        billing_frequency TEXT NOT NULL CHECK(billing_frequency IN ('daily', 'weekly', 'monthly', 'yearly')),
        base_price REAL NOT NULL,
        min_quantity INTEGER DEFAULT 1,
        valid_from TEXT,
        valid_to TEXT,
        auto_close INTEGER DEFAULT 0,
        allow_early_close INTEGER DEFAULT 1,
        allow_pause INTEGER DEFAULT 1,
        allow_renew INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS quotation_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        default_plan_id INTEGER REFERENCES plans(id) ON DELETE SET NULL,
        validity_days INTEGER DEFAULT 30,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS quotation_template_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL REFERENCES quotation_templates(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        variant_id INTEGER REFERENCES product_variants(id) ON DELETE SET NULL,
        default_quantity INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sub_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
        status TEXT NOT NULL CHECK(status IN ('draft', 'quotation', 'confirmed', 'active', 'paused', 'closed')),
        start_date TEXT NOT NULL,
        expiry_date TEXT,
        next_billing_date TEXT,
        last_billed_date TEXT,
        payment_terms TEXT DEFAULT 'Net 30',
        auto_renew INTEGER DEFAULT 1,
        notes TEXT,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS subscription_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        variant_id INTEGER REFERENCES product_variants(id) ON DELETE SET NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        unit_price REAL NOT NULL,
        tax_id INTEGER REFERENCES taxes(id) ON DELETE SET NULL,
        discount_id INTEGER REFERENCES discounts(id) ON DELETE SET NULL,
        line_amount REAL NOT NULL,
        is_addon INTEGER DEFAULT 0,
        addon_active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS taxes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        rate_percent REAL NOT NULL,
        is_active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS discounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        description TEXT,
        discount_type TEXT NOT NULL CHECK(discount_type IN ('fixed', 'percentage')),
        value REAL NOT NULL,
        min_amount REAL DEFAULT 0,
        min_quantity INTEGER DEFAULT 0,
        start_date TEXT,
        end_date TEXT,
        max_uses INTEGER DEFAULT 100,
        times_used INTEGER DEFAULT 0,
        apply_to TEXT NOT NULL CHECK(apply_to IN ('all', 'product')),
        product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
        is_active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT UNIQUE NOT NULL,
        subscription_id INTEGER REFERENCES subscriptions(id) ON DELETE SET NULL,
        customer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        issue_date TEXT NOT NULL,
        due_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('draft', 'confirmed', 'paid', 'partially_paid', 'overdue', 'cancelled')),
        subtotal REAL NOT NULL,
        tax_amount REAL NOT NULL,
        discount_amount REAL NOT NULL,
        total_amount REAL NOT NULL,
        paid_amount REAL DEFAULT 0,
        notes TEXT,
        billing_period_start TEXT,
        billing_period_end TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS invoice_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
        product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
        product_name TEXT NOT NULL,
        variant_name TEXT,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        tax_percent REAL DEFAULT 0,
        tax_amount REAL DEFAULT 0,
        discount_amount REAL DEFAULT 0,
        total_amount REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_number TEXT UNIQUE NOT NULL,
        invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
        customer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        payment_date TEXT NOT NULL,
        amount REAL NOT NULL,
        method TEXT NOT NULL CHECK(method IN ('credit_card', 'bank_transfer', 'stripe', 'check', 'cash')),
        reference_notes TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        user_email TEXT,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT,
        details TEXT
    );

    -- High-Performance Indexes for sub-2s query latency across thousands of records
    CREATE INDEX IF NOT EXISTS idx_subs_customer_status ON subscriptions(customer_id, status);
    CREATE INDEX IF NOT EXISTS idx_subs_next_billing ON subscriptions(status, next_billing_date);
    CREATE INDEX IF NOT EXISTS idx_invoices_customer_status ON invoices(customer_id, status);
    CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices(due_date, status);
    CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
    CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp DESC);
    """)

    conn.commit()
    conn.close()


def seed_data():
    """Populate database with rich initial Brightloop Software records."""
    conn = get_db()
    cur = conn.cursor()

    # Check if already seeded
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] > 0:
        conn.close()
        return

    now_iso = datetime.now().isoformat()
    today_str = datetime.now().strftime("%Y-%m-%d")
    next_month = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    last_month = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    overdue_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

    # 1. Users (Admin, Staff, Customers)
    users = [
        ("admin@brightloop.com", hash_password("Brightloop@2026"), "admin", "Elena Vance (CEO / Admin)", "Brightloop Software", now_iso),
        ("staff@brightloop.com", hash_password("StaffPass#2026"), "staff", "Marcus Brody (Sales & Billing)", "Brightloop Software", now_iso),
        ("billing@brightloop.com", hash_password("BillingPass#2026"), "staff", "Sarah Chen (Finance Specialist)", "Brightloop Software", now_iso),
        ("customer@apexshop.com", hash_password("ApexShop@2026"), "customer", "David Miller", "Apex Retail Store", now_iso),
        ("client@northtech.io", hash_password("NorthTech@2026"), "customer", "Claire Sterling", "NorthTech Enterprise", now_iso),
        ("info@luminaudio.com", hash_password("LuminAudio@2026"), "customer", "Julian Rossi", "Lumin Audio Labs", now_iso),
        ("ops@greenlogistics.org", hash_password("GreenLog@2026"), "customer", "Anita Patel", "Green Logistics Hub", now_iso)
    ]
    cur.executemany("INSERT INTO users (email, password_hash, role, full_name, company, created_at) VALUES (?, ?, ?, ?, ?, ?)", users)

    # 2. Taxes
    taxes = [
        ("Standard VAT (10%)", 10.0, 1),
        ("State Sales Tax (8%)", 8.0, 1),
        ("Zero Tax (Exempt)", 0.0, 1)
    ]
    cur.executemany("INSERT INTO taxes (name, rate_percent, is_active) VALUES (?, ?, ?)", taxes)

    # 3. Products & Variants (Software, Add-ons, Services)
    products = [
        ("Brightloop ERP Core", "software", 1200.0, 400.0, "Core subscription ERP engine for business operations", 1, now_iso),
        ("Automated Invoicing Engine", "software", 450.0, 100.0, "Automated recurring billing and batch dunning module", 1, now_iso),
        ("Multi-Currency & Treasury Add-on", "addon", 180.0, 30.0, "Customer switchable add-on for international transactions", 1, now_iso),
        ("High-Volume API Connector Add-on", "addon", 250.0, 50.0, "Add-on for up to 100,000 webhook events/mo", 1, now_iso),
        ("Dedicated Account Manager", "service", 600.0, 250.0, "Monthly 1-on-1 enterprise SLA and account oversight", 1, now_iso)
    ]
    cur.executemany("INSERT INTO products (name, type, sales_price, cost_price, notes, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", products)

    # Product Variants (Specifically from PDF: choosing Odoo brand adds 560 to price!)
    variants = [
        (1, "Brand Integration", "Standard Cloud", 0.0),
        (1, "Brand Integration", "Odoo Enterprise Edition", 560.0),
        (1, "Brand Integration", "SAP Bridge Connector", 850.0),
        (2, "Deployment Tier", "Single Region", 0.0),
        (2, "Deployment Tier", "Global Multi-AZ Active", 320.0)
    ]
    cur.executemany("INSERT INTO product_variants (product_id, attribute_name, attribute_value, price_surcharge) VALUES (?, ?, ?, ?)", variants)

    # 4. Plans (Daily, Weekly, Monthly, Yearly)
    plans = [
        ("Monthly Growth Plan", "monthly", 1200.0, 1, today_str, "2027-12-31", 0, 1, 1, 1, now_iso),
        ("Annual Enterprise Contract", "yearly", 12000.0, 5, today_str, "2028-12-31", 0, 1, 1, 1, now_iso),
        ("Weekly Starter Trial", "weekly", 350.0, 1, today_str, "2027-06-30", 1, 1, 0, 0, now_iso),
        ("Daily High-Capacity Burst", "daily", 90.0, 1, today_str, "2027-03-31", 1, 1, 0, 0, now_iso)
    ]
    cur.executemany("INSERT INTO plans (name, billing_frequency, base_price, min_quantity, valid_from, valid_to, auto_close, allow_early_close, allow_pause, allow_renew, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", plans)

    # 5. Quotation Templates
    templates = [
        ("SaaS Standard Growth Quote", 1, 30, "Default template for medium business monthly subscriptions"),
        ("Enterprise Annual Agreement", 2, 45, "Full enterprise template with Odoo variant and add-ons")
    ]
    cur.executemany("INSERT INTO quotation_templates (name, default_plan_id, validity_days, notes) VALUES (?, ?, ?, ?)", templates)

    cur.execute("INSERT INTO quotation_template_lines (template_id, product_id, variant_id, default_quantity) VALUES (1, 1, 1, 1)")
    cur.execute("INSERT INTO quotation_template_lines (template_id, product_id, variant_id, default_quantity) VALUES (1, 3, NULL, 1)")
    cur.execute("INSERT INTO quotation_template_lines (template_id, product_id, variant_id, default_quantity) VALUES (2, 1, 2, 5)")
    cur.execute("INSERT INTO quotation_template_lines (template_id, product_id, variant_id, default_quantity) VALUES (2, 4, NULL, 2)")

    # 6. Discounts & Promotions
    discounts = [
        ("BRIGHT20", "20% off for high-volume seat expansion", "percentage", 20.0, 1000.0, 3, today_str, "2027-12-31", 100, 4, "all", None, 1),
        ("FLAT500", "$500 off on Enterprise contracts", "fixed", 500.0, 5000.0, 1, today_str, "2027-12-31", 50, 12, "all", None, 1),
        ("ADDONFREE", "100% off Multi-Currency Add-on for 1st quarter", "percentage", 100.0, 0.0, 1, today_str, "2027-06-30", 25, 6, "product", 3, 1)
    ]
    cur.executemany("INSERT INTO discounts (code, description, discount_type, value, min_amount, min_quantity, start_date, end_date, max_uses, times_used, apply_to, product_id, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", discounts)

    # 7. Seed Subscriptions
    # SUB-2026-0001 (Active, Apex Retail Store, Monthly Growth)
    cur.execute("""
    INSERT INTO subscriptions (sub_number, customer_id, plan_id, status, start_date, expiry_date, next_billing_date, last_billed_date, payment_terms, auto_renew, notes, created_by, created_at)
    VALUES ('SUB-2026-0001', 4, 1, 'active', ?, ?, ?, ?, 'Net 15', 1, 'Apex Retail regular monthly subscription', 2, ?)
    """, (last_month, next_month, today_str, last_month, now_iso))
    sub1_id = cur.lastrowid

    # Line items: ERP Core (Standard Cloud: 1200) + Multi-Currency Add-on (180, active)
    cur.execute("INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_id, discount_id, line_amount, is_addon, addon_active) VALUES (?, 1, 1, 1, 1200.0, 1, NULL, 1200.0, 0, 1)", (sub1_id,))
    cur.execute("INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_id, discount_id, line_amount, is_addon, addon_active) VALUES (?, 3, NULL, 1, 180.0, 1, NULL, 180.0, 1, 1)", (sub1_id,))

    # SUB-2026-0002 (Active, NorthTech Enterprise, Annual Contract with Odoo variant: 1200 + 560 = 1760 * 5 seats = 8800)
    cur.execute("""
    INSERT INTO subscriptions (sub_number, customer_id, plan_id, status, start_date, expiry_date, next_billing_date, last_billed_date, payment_terms, auto_renew, notes, created_by, created_at)
    VALUES ('SUB-2026-0002', 5, 2, 'active', ?, '2027-10-31', '2027-10-31', ?, 'Net 30', 1, 'Enterprise yearly contract with Odoo variant', 2, ?)
    """, (today_str, today_str, now_iso))
    sub2_id = cur.lastrowid
    cur.execute("INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_id, discount_id, line_amount, is_addon, addon_active) VALUES (?, 1, 2, 5, 1760.0, 2, 1, 8800.0, 0, 1)", (sub2_id,))
    cur.execute("INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_id, discount_id, line_amount, is_addon, addon_active) VALUES (?, 4, NULL, 1, 250.0, 2, NULL, 250.0, 1, 1)", (sub2_id,))

    # SUB-2026-0003 (Quotation stage, Lumin Audio Labs)
    cur.execute("""
    INSERT INTO subscriptions (sub_number, customer_id, plan_id, status, start_date, expiry_date, next_billing_date, last_billed_date, payment_terms, auto_renew, notes, created_by, created_at)
    VALUES ('SUB-2026-0003', 6, 1, 'quotation', ?, ?, ?, NULL, 'Net 30', 1, 'Pending quote review from Lumin Audio', 2, ?)
    """, (today_str, next_month, today_str, now_iso))
    sub3_id = cur.lastrowid
    cur.execute("INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_id, discount_id, line_amount, is_addon, addon_active) VALUES (?, 1, 1, 2, 1200.0, 1, NULL, 2400.0, 0, 1)", (sub3_id,))

    # SUB-2026-0004 (Paused stage, Green Logistics)
    cur.execute("""
    INSERT INTO subscriptions (sub_number, customer_id, plan_id, status, start_date, expiry_date, next_billing_date, last_billed_date, payment_terms, auto_renew, notes, created_by, created_at)
    VALUES ('SUB-2026-0004', 7, 1, 'paused', ?, ?, ?, ?, 'Net 15', 1, 'Temporarily paused for seasonal warehouse re-org', 2, ?)
    """, (last_month, next_month, today_str, last_month, now_iso))
    sub4_id = cur.lastrowid
    cur.execute("INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_id, discount_id, line_amount, is_addon, addon_active) VALUES (?, 1, 1, 1, 1200.0, 1, NULL, 1200.0, 0, 1)", (sub4_id,))

    # 8. Seed Invoices & Payments
    # Invoice 1: Paid invoice for Apex Store
    cur.execute("""
    INSERT INTO invoices (invoice_number, subscription_id, customer_id, issue_date, due_date, status, subtotal, tax_amount, discount_amount, total_amount, paid_amount, notes, billing_period_start, billing_period_end, created_at)
    VALUES ('INV-2026-0001', 1, 4, ?, ?, 'paid', 1380.0, 138.0, 0.0, 1518.0, 1518.0, 'Regular billing for last month cycle', ?, ?, ?)
    """, (last_month, today_str, last_month, today_str, now_iso))
    inv1_id = cur.lastrowid
    cur.execute("INSERT INTO invoice_lines (invoice_id, product_id, product_name, variant_name, quantity, unit_price, tax_percent, tax_amount, discount_amount, total_amount) VALUES (?, 1, 'Brightloop ERP Core', 'Standard Cloud', 1, 1200.0, 10.0, 120.0, 0.0, 1320.0)", (inv1_id,))
    cur.execute("INSERT INTO invoice_lines (invoice_id, product_id, product_name, variant_name, quantity, unit_price, tax_percent, tax_amount, discount_amount, total_amount) VALUES (?, 3, 'Multi-Currency & Treasury Add-on', NULL, 1, 180.0, 10.0, 18.0, 0.0, 198.0)", (inv1_id,))

    # Payment for Invoice 1
    cur.execute("""
    INSERT INTO payments (payment_number, invoice_id, customer_id, payment_date, amount, method, reference_notes, created_at)
    VALUES ('PAY-2026-0001', ?, 4, ?, 1518.0, 'stripe', 'Stripe automatic charge ch_99a8b1c', ?)
    """, (inv1_id, today_str, now_iso))

    # Invoice 2: Overdue invoice for Green Logistics
    cur.execute("""
    INSERT INTO invoices (invoice_number, subscription_id, customer_id, issue_date, due_date, status, subtotal, tax_amount, discount_amount, total_amount, paid_amount, notes, billing_period_start, billing_period_end, created_at)
    VALUES ('INV-2026-0002', 4, 7, ?, ?, 'overdue', 1200.0, 120.0, 0.0, 1320.0, 0.0, 'Invoice payment overdue by 10 days - automated dunning alert triggered', ?, ?, ?)
    """, (last_month, overdue_date, last_month, overdue_date, now_iso))
    inv2_id = cur.lastrowid
    cur.execute("INSERT INTO invoice_lines (invoice_id, product_id, product_name, variant_name, quantity, unit_price, tax_percent, tax_amount, discount_amount, total_amount) VALUES (?, 1, 'Brightloop ERP Core', 'Standard Cloud', 1, 1200.0, 10.0, 120.0, 0.0, 1320.0)", (inv2_id,))

    # Invoice 3: Confirmed (Outstanding) for NorthTech Enterprise
    cur.execute("""
    INSERT INTO invoices (invoice_number, subscription_id, customer_id, issue_date, due_date, status, subtotal, tax_amount, discount_amount, total_amount, paid_amount, notes, billing_period_start, billing_period_end, created_at)
    VALUES ('INV-2026-0003', 2, 5, ?, ?, 'confirmed', 9050.0, 579.2, 1810.0, 7819.2, 0.0, 'Annual enterprise cycle invoice with BRIGHT20 discount', ?, ?, ?)
    """, (today_str, next_month, today_str, next_month, now_iso))
    inv3_id = cur.lastrowid
    cur.execute("INSERT INTO invoice_lines (invoice_id, product_id, product_name, variant_name, quantity, unit_price, tax_percent, tax_amount, discount_amount, total_amount) VALUES (?, 1, 'Brightloop ERP Core', 'Odoo Enterprise Edition (+$560)', 5, 1760.0, 8.0, 563.2, 1760.0, 7603.2)", (inv3_id,))
    cur.execute("INSERT INTO invoice_lines (invoice_id, product_id, product_name, variant_name, quantity, unit_price, tax_percent, tax_amount, discount_amount, total_amount) VALUES (?, 4, 'High-Volume API Connector Add-on', NULL, 1, 250.0, 8.0, 16.0, 50.0, 216.0)", (inv3_id,))

    # 9. Audit Logs
    audit_entries = [
        (now_iso, "admin@brightloop.com", "SYSTEM_INIT", "system", "1", "Brightloop Subscription System initialized successfully"),
        (now_iso, "admin@brightloop.com", "CREATE_PRODUCT", "product", "1", "Created product Brightloop ERP Core with Odoo brand variant"),
        (now_iso, "staff@brightloop.com", "CONVERT_QUOTE", "subscription", "SUB-2026-0001", "Converted quotation to active subscription for Apex Retail Store"),
        (now_iso, "billing@brightloop.com", "RECORD_PAYMENT", "payment", "PAY-2026-0001", "Recorded $1,518.00 payment via Stripe for INV-2026-0001")
    ]
    cur.executemany("INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?, ?)", audit_entries)

    conn.commit()
    conn.close()


def generate_bulk_demo_records(count=1000):
    """
    Scale-up benchmark feature:
    Inserts 1,000+ realistic subscriptions and invoices to stress test and verify
    sub-2-second query performance as required by the Finance Lead.
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE role = 'customer'")
    customer_ids = [r[0] for r in cur.fetchall()]
    if not customer_ids:
        customer_ids = [4, 5, 6, 7]

    cur.execute("SELECT id FROM plans")
    plan_ids = [r[0] for r in cur.fetchall()]
    if not plan_ids:
        plan_ids = [1, 2]

    now = datetime.now()
    cur.execute("SELECT COUNT(*) FROM subscriptions")
    existing_count = cur.fetchone()[0]

    subs_data = []
    invs_data = []

    statuses = ['active', 'active', 'active', 'confirmed', 'paused', 'closed']
    inv_statuses = ['paid', 'paid', 'confirmed', 'overdue', 'partially_paid']

    for i in range(1, count + 1):
        idx = existing_count + i
        sub_num = f"SUB-2026-{idx:05d}"
        inv_num = f"INV-2026-{idx:05d}"
        cust_id = customer_ids[i % len(customer_ids)]
        p_id = plan_ids[i % len(plan_ids)]
        st = statuses[i % len(statuses)]

        days_offset = (i * 3) % 90
        start = (now - timedelta(days=days_offset + 30)).strftime("%Y-%m-%d")
        exp = (now + timedelta(days=180 - days_offset)).strftime("%Y-%m-%d")
        next_b = (now + timedelta(days=(i % 30) - 10)).strftime("%Y-%m-%d")
        last_b = (now - timedelta(days=30)).strftime("%Y-%m-%d")

        subs_data.append((
            sub_num, cust_id, p_id, st, start, exp, next_b, last_b,
            'Net 30', 1, f'Bulk benchmark subscription #{idx}', 2, now.isoformat()
        ))

        inv_st = inv_statuses[i % len(inv_statuses)]
        subtot = round(1200.0 + (i % 5) * 300, 2)
        tax = round(subtot * 0.10, 2)
        disc = 100.0 if i % 4 == 0 else 0.0
        tot = round(subtot + tax - disc, 2)
        paid = tot if inv_st == 'paid' else (tot / 2.0 if inv_st == 'partially_paid' else 0.0)

        issue_d = (now - timedelta(days=(i % 45))).strftime("%Y-%m-%d")
        due_d = (now - timedelta(days=(i % 45) - 15)).strftime("%Y-%m-%d")

        invs_data.append((
            inv_num, None, cust_id, issue_d, due_d, inv_st,
            subtot, tax, disc, tot, paid, f'Automated invoice #{idx}',
            issue_d, due_d, now.isoformat()
        ))

    cur.executemany("""
    INSERT INTO subscriptions (sub_number, customer_id, plan_id, status, start_date, expiry_date, next_billing_date, last_billed_date, payment_terms, auto_renew, notes, created_by, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, subs_data)

    cur.executemany("""
    INSERT INTO invoices (invoice_number, subscription_id, customer_id, issue_date, due_date, status, subtotal, tax_amount, discount_amount, total_amount, paid_amount, notes, billing_period_start, billing_period_end, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, invs_data)

    audit_entry = (now.isoformat(), "admin@brightloop.com", "BULK_BENCHMARK_GEN", "system", str(count), f"Generated {count} high-volume benchmark subscriptions & invoices")
    cur.execute("INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?, ?)", audit_entry)

    conn.commit()
    conn.close()
    return count


if __name__ == "__main__":
    init_db()
    seed_data()
    print("Brightloop database initialized and seeded successfully.")
