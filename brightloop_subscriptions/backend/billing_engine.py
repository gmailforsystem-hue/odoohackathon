"""
Billing Engine for Brightloop Software Subscription Management System.
Handles tax calculation, discount validation, pro-ration, automated recurring billing run,
idempotent invoice generation, dunning status reconciliation, and password policy rules.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import database


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validates password strictly per requirements:
    - More than 8 characters (>= 9 characters)
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 special character
    """
    if len(password) <= 8:
        return False, "Password must be more than 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r"[^a-zA-Z0-9]", password):
        return False, "Password must include at least one special character (e.g. !@#$%^&*)."
    return True, "Password meets security requirements."


def calculate_line_item(unit_price: float, quantity: int, surcharge: float = 0.0,
                        tax_rate: float = 0.0, discount: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """Calculate subtotal, tax amount, discount amount, and total for a line item."""
    base_price = (unit_price + surcharge) * quantity
    discount_amount = 0.0

    if discount and discount.get("is_active"):
        d_type = discount.get("discount_type")
        d_val = float(discount.get("value", 0))
        if d_type == "percentage":
            discount_amount = round(base_price * (d_val / 100.0), 2)
        elif d_type == "fixed":
            discount_amount = min(d_val, base_price)

    after_discount = max(0.0, base_price - discount_amount)
    tax_amount = round(after_discount * (tax_rate / 100.0), 2)
    total_amount = round(after_discount + tax_amount, 2)

    return {
        "subtotal": round(base_price, 2),
        "discount_amount": discount_amount,
        "tax_amount": tax_amount,
        "total_amount": total_amount
    }


def advance_billing_date(current_date_str: str, frequency: str) -> str:
    """Advance billing date based on plan interval."""
    try:
        dt = datetime.strptime(current_date_str, "%Y-%m-%d")
    except Exception:
        dt = datetime.now()

    if frequency == "daily":
        next_dt = dt + timedelta(days=1)
    elif frequency == "weekly":
        next_dt = dt + timedelta(days=7)
    elif frequency == "monthly":
        # Approx 30 days or same day next month
        next_dt = dt + timedelta(days=30)
    elif frequency == "yearly":
        next_dt = dt + timedelta(days=365)
    else:
        next_dt = dt + timedelta(days=30)

    return next_dt.strftime("%Y-%m-%d")


def calculate_proration(addon_price: float, cycle_start_str: str, cycle_end_str: str, change_date_str: str) -> Dict[str, Any]:
    """
    Calculates pro-rated charges when customer adds/removes add-on mid-month.
    """
    try:
        start_dt = datetime.strptime(cycle_start_str, "%Y-%m-%d")
        end_dt = datetime.strptime(cycle_end_str, "%Y-%m-%d")
        change_dt = datetime.strptime(change_date_str, "%Y-%m-%d")

        total_days = max(1, (end_dt - start_dt).days)
        remaining_days = max(0, (end_dt - change_dt).days)
        prorated_amount = round((remaining_days / total_days) * addon_price, 2)

        return {
            "total_cycle_days": total_days,
            "remaining_days": remaining_days,
            "full_price": addon_price,
            "prorated_amount": prorated_amount
        }
    except Exception:
        return {
            "total_cycle_days": 30,
            "remaining_days": 15,
            "full_price": addon_price,
            "prorated_amount": round(addon_price / 2.0, 2)
        }


def reconcile_overdue_invoices():
    """Check all unpaid/partially paid invoices past due date and mark as overdue."""
    conn = database.get_db()
    cur = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")

    cur.execute("""
    UPDATE invoices
    SET status = 'overdue'
    WHERE status IN ('confirmed', 'partially_paid')
      AND due_date < ?
      AND (total_amount - paid_amount) > 0.01
    """, (today_str,))

    conn.commit()
    conn.close()


def run_billing_day(target_date_str: Optional[str] = None, user_email: str = "system") -> Dict[str, Any]:
    """
    Automated Billing Day Engine.
    Executes recurring billing run for all active subscriptions due up to target_date.
    Guarantees idempotency: No subscription is billed twice for the same billing date.
    """
    if not target_date_str:
        target_date_str = datetime.now().strftime("%Y-%m-%d")

    reconcile_overdue_invoices()

    conn = database.get_db()
    cur = conn.cursor()

    # Query active subscriptions that are due for billing
    cur.execute("""
    SELECT s.id, s.sub_number, s.customer_id, s.plan_id, s.status, s.start_date,
           s.expiry_date, s.next_billing_date, s.last_billed_date, s.payment_terms,
           p.name AS plan_name, p.billing_frequency, p.base_price, p.auto_close,
           u.full_name AS customer_name, u.email AS customer_email
    FROM subscriptions s
    JOIN plans p ON s.plan_id = p.id
    JOIN users u ON s.customer_id = u.id
    WHERE s.status = 'active'
      AND (s.next_billing_date IS NULL OR s.next_billing_date <= ?)
      AND (s.last_billed_date IS NULL OR s.last_billed_date < ?)
    """, (target_date_str, target_date_str))
    due_subs = cur.fetchall()

    invoices_generated = []
    skipped_count = 0
    total_billed_amount = 0.0

    cur.execute("SELECT COUNT(*) FROM invoices")
    inv_sequence = cur.fetchone()[0]

    for sub in due_subs:
        sub_id = sub["id"]
        sub_num = sub["sub_number"]
        cust_id = sub["customer_id"]
        next_b_date = sub["next_billing_date"] or target_date_str
        freq = sub["billing_frequency"]

        # 1. Idempotency Check: Was an invoice already generated for this subscription on or covering next_b_date?
        cur.execute("""
        SELECT id, invoice_number FROM invoices
        WHERE subscription_id = ? AND issue_date = ?
        """, (sub_id, next_b_date))
        existing_inv = cur.fetchone()

        if existing_inv:
            skipped_count += 1
            continue

        # 2. Fetch Subscription Lines (software, variants, active add-ons)
        cur.execute("""
        SELECT sl.*, p.name AS product_name, p.sales_price, p.type AS product_type,
               pv.attribute_value AS variant_name, COALESCE(pv.price_surcharge, 0.0) AS surcharge,
               t.rate_percent AS tax_rate,
               d.discount_type, d.value AS discount_val, d.is_active AS discount_active
        FROM subscription_lines sl
        JOIN products p ON sl.product_id = p.id
        LEFT JOIN product_variants pv ON sl.variant_id = pv.id
        LEFT JOIN taxes t ON sl.tax_id = t.id
        LEFT JOIN discounts d ON sl.discount_id = d.id
        WHERE sl.subscription_id = ?
        """, (sub_id,))
        lines = cur.fetchall()

        if not lines:
            # Fallback line using Plan base price
            inv_sequence += 1
            inv_num = f"INV-2026-{inv_sequence:04d}"
            due_days = 30 if sub["payment_terms"] == "Net 30" else (15 if sub["payment_terms"] == "Net 15" else 7)
            due_date = (datetime.strptime(next_b_date, "%Y-%m-%d") + timedelta(days=due_days)).strftime("%Y-%m-%d")
            base_p = float(sub["base_price"])
            tax_amt = round(base_p * 0.10, 2)
            tot_amt = round(base_p + tax_amt, 2)

            cur.execute("""
            INSERT INTO invoices (invoice_number, subscription_id, customer_id, issue_date, due_date, status, subtotal, tax_amount, discount_amount, total_amount, paid_amount, notes, billing_period_start, billing_period_end, created_at)
            VALUES (?, ?, ?, ?, ?, 'confirmed', ?, ?, 0.0, ?, 0.0, ?, ?, ?, ?)
            """, (inv_num, sub_id, cust_id, next_b_date, due_date, base_p, tax_amt, tot_amt, f"Automated billing for plan {sub['plan_name']}", next_b_date, due_date, datetime.now().isoformat()))
            inv_id = cur.lastrowid

            cur.execute("""
            INSERT INTO invoice_lines (invoice_id, product_id, product_name, variant_name, quantity, unit_price, tax_percent, tax_amount, discount_amount, total_amount)
            VALUES (?, NULL, ?, NULL, 1, ?, 10.0, ?, 0.0, ?)
            """, (inv_id, sub["plan_name"], base_p, tax_amt, tot_amt))

            total_billed_amount += tot_amt
            invoices_generated.append({"invoice_number": inv_num, "subscription_number": sub_num, "amount": tot_amt})
        else:
            subtotal = 0.0
            tax_total = 0.0
            discount_total = 0.0
            invoice_lines_to_insert = []

            for line in lines:
                # If it's an add-on and currently deactivated, skip billing it
                if line["is_addon"] and not line["addon_active"]:
                    continue

                qty = line["quantity"]
                unit_p = float(line["sales_price"])
                surcharge = float(line["surcharge"])
                tax_rate = float(line["tax_rate"]) if line["tax_rate"] is not None else 0.0

                disc_dict = None
                if line["discount_active"]:
                    disc_dict = {
                        "discount_type": line["discount_type"],
                        "value": line["discount_val"],
                        "is_active": True
                    }

                calc = calculate_line_item(unit_p, qty, surcharge, tax_rate, disc_dict)
                subtotal += calc["subtotal"]
                tax_total += calc["tax_amount"]
                discount_total += calc["discount_amount"]

                var_label = f"({line['variant_name']})" if line["variant_name"] else None
                invoice_lines_to_insert.append({
                    "product_id": line["product_id"],
                    "product_name": line["product_name"],
                    "variant_name": var_label,
                    "quantity": qty,
                    "unit_price": unit_p + surcharge,
                    "tax_percent": tax_rate,
                    "tax_amount": calc["tax_amount"],
                    "discount_amount": calc["discount_amount"],
                    "total_amount": calc["total_amount"]
                })

            total_inv_amount = round(subtotal - discount_total + tax_total, 2)
            inv_sequence += 1
            inv_num = f"INV-2026-{inv_sequence:04d}"
            due_days = 30 if sub["payment_terms"] == "Net 30" else (15 if sub["payment_terms"] == "Net 15" else 7)
            due_date = (datetime.strptime(next_b_date, "%Y-%m-%d") + timedelta(days=due_days)).strftime("%Y-%m-%d")

            cur.execute("""
            INSERT INTO invoices (invoice_number, subscription_id, customer_id, issue_date, due_date, status, subtotal, tax_amount, discount_amount, total_amount, paid_amount, notes, billing_period_start, billing_period_end, created_at)
            VALUES (?, ?, ?, ?, ?, 'confirmed', ?, ?, ?, ?, 0.0, ?, ?, ?, ?)
            """, (inv_num, sub_id, cust_id, next_b_date, due_date, subtotal, tax_total, discount_total, total_inv_amount, f"Automated billing run for {sub_num}", next_b_date, due_date, datetime.now().isoformat()))
            inv_id = cur.lastrowid

            for il in invoice_lines_to_insert:
                cur.execute("""
                INSERT INTO invoice_lines (invoice_id, product_id, product_name, variant_name, quantity, unit_price, tax_percent, tax_amount, discount_amount, total_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (inv_id, il["product_id"], il["product_name"], il["variant_name"], il["quantity"], il["unit_price"], il["tax_percent"], il["tax_amount"], il["discount_amount"], il["total_amount"]))

            total_billed_amount += total_inv_amount
            invoices_generated.append({"invoice_number": inv_num, "subscription_number": sub_num, "amount": total_inv_amount})

        # 3. Advance Next Billing Date past target_date_str
        new_next_billing = advance_billing_date(next_b_date, freq)
        while new_next_billing <= target_date_str:
            new_next_billing = advance_billing_date(new_next_billing, freq)

        new_status = "active"

        # Check if plan auto-closes when it ends
        if sub["auto_close"] and sub["expiry_date"]:
            if new_next_billing >= sub["expiry_date"]:
                new_status = "closed"

        cur.execute("""
        UPDATE subscriptions
        SET last_billed_date = ?, next_billing_date = ?, status = ?
        WHERE id = ?
        """, (target_date_str, new_next_billing, new_status, sub_id))

    # 4. Audit Log Entry
    audit_msg = f"Billing Day run for {target_date_str}: Generated {len(invoices_generated)} invoices totaling ${total_billed_amount:,.2f}. Skipped {skipped_count} already-billed."
    cur.execute("""
    INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details)
    VALUES (?, ?, 'BILLING_DAY_RUN', 'billing_engine', ?, ?)
    """, (datetime.now().isoformat(), user_email, target_date_str, audit_msg))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "target_date": target_date_str,
        "invoices_generated_count": len(invoices_generated),
        "total_amount_billed": round(total_billed_amount, 2),
        "skipped_already_billed": skipped_count,
        "invoices": invoices_generated
    }


def record_payment_against_invoice(invoice_id: int, amount: float, method: str,
                                   payment_date: str, notes: str, user_email: str) -> Dict[str, Any]:
    """Records a payment against an invoice and recalculates invoice payment status."""
    conn = database.get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    inv = cur.fetchone()
    if not inv:
        conn.close()
        return {"status": "error", "message": "Invoice not found."}

    total_amount = float(inv["total_amount"])
    current_paid = float(inv["paid_amount"])
    balance_remaining = round(total_amount - current_paid, 2)

    if amount <= 0:
        conn.close()
        return {"status": "error", "message": "Payment amount must be greater than zero."}

    if amount > balance_remaining + 0.01:
        conn.close()
        return {"status": "error", "message": f"Payment amount (${amount:,.2f}) exceeds outstanding balance (${balance_remaining:,.2f})."}

    cur.execute("SELECT COUNT(*) FROM payments")
    pay_seq = cur.fetchone()[0] + 1
    pay_num = f"PAY-2026-{pay_seq:04d}"

    now_iso = datetime.now().isoformat()
    cur.execute("""
    INSERT INTO payments (payment_number, invoice_id, customer_id, payment_date, amount, method, reference_notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (pay_num, invoice_id, inv["customer_id"], payment_date, amount, method, notes, now_iso))

    new_paid = round(current_paid + amount, 2)
    if new_paid >= total_amount - 0.01:
        new_status = "paid"
    else:
        new_status = "partially_paid"

    cur.execute("""
    UPDATE invoices
    SET paid_amount = ?, status = ?
    WHERE id = ?
    """, (new_paid, new_status, invoice_id))

    audit_msg = f"Payment {pay_num} of ${amount:,.2f} recorded via {method}. Invoice {inv['invoice_number']} status is now {new_status}."
    cur.execute("""
    INSERT INTO audit_logs (timestamp, user_email, action, entity_type, entity_id, details)
    VALUES (?, ?, 'RECORD_PAYMENT', 'payment', ?, ?)
    """, (now_iso, user_email, pay_num, audit_msg))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "payment_number": pay_num,
        "invoice_status": new_status,
        "new_paid_amount": new_paid,
        "remaining_balance": max(0.0, round(total_amount - new_paid, 2))
    }
