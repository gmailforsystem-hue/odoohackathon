"""
Automated unit & integration tests for Brightloop Subscription Management System.
Verifies password policy rules, tax computation, discount logic, billing day idempotency,
proration calculation, and sub-2-second query performance.
"""

import unittest
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import database
import billing_engine


class TestBrightloopBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db()
        database.seed_data()

    def test_password_policy(self):
        """Test strict password policy: >8 chars, uppercase, lowercase, special char."""
        # Too short (<= 8)
        valid, msg = billing_engine.validate_password_strength("Short1!")
        self.assertFalse(valid)

        # Missing uppercase
        valid, msg = billing_engine.validate_password_strength("lowercase123!")
        self.assertFalse(valid)

        # Missing lowercase
        valid, msg = billing_engine.validate_password_strength("UPPERCASE123!")
        self.assertFalse(valid)

        # Missing special character
        valid, msg = billing_engine.validate_password_strength("NoSpecialChar123")
        self.assertFalse(valid)

        # Valid password (>8 chars, uppercase, lowercase, special char)
        valid, msg = billing_engine.validate_password_strength("Brightloop#2026")
        self.assertTrue(valid)

    def test_tax_and_line_calculation(self):
        """Test calculation of line items with variant surcharge, discount, and tax."""
        # Base: $1,200, Odoo variant surcharge: $560 => unit $1,760, qty: 2 => $3,520
        # Discount: 10% => $352.00 => taxable: $3,168.00
        # Tax: 10% Standard VAT => $316.80 => Total: $3,484.80
        calc = billing_engine.calculate_line_item(
            unit_price=1200.0,
            quantity=2,
            surcharge=560.0,
            tax_rate=10.0,
            discount={"discount_type": "percentage", "value": 10.0, "is_active": True}
        )
        self.assertEqual(calc["subtotal"], 3520.0)
        self.assertEqual(calc["discount_amount"], 352.0)
        self.assertEqual(calc["tax_amount"], 316.80)
        self.assertEqual(calc["total_amount"], 3484.80)

    def test_proration_calculator(self):
        """Test mid-cycle add-on proration calculations."""
        # $180 add-on, 30 days cycle, 15 days remaining => $90
        res = billing_engine.calculate_proration(180.0, "2026-10-01", "2026-10-31", "2026-10-16")
        self.assertEqual(res["total_cycle_days"], 30)
        self.assertEqual(res["remaining_days"], 15)
        self.assertEqual(res["prorated_amount"], 90.0)

    def test_billing_day_and_idempotency(self):
        """Test recurring billing day generation and verify nothing is billed twice."""
        target_date = "2026-10-31"

        # First billing run
        res1 = billing_engine.run_billing_day(target_date, user_email="test@brightloop.com")
        self.assertEqual(res1["status"], "success")

        # Second billing run on the exact same target date -> must be idempotent (zero new invoices)
        res2 = billing_engine.run_billing_day(target_date, user_email="test@brightloop.com")
        self.assertEqual(res2["status"], "success")
        self.assertEqual(res2["invoices_generated_count"], 0)
        self.assertGreaterEqual(res2["skipped_already_billed"], 0)

    def test_query_performance_under_two_seconds(self):
        """Verify report summary execution completes in under 2.0 seconds (finance lead requirement)."""
        t0 = time.time()
        conn = database.get_db()
        cur = conn.cursor()

        # Run summary aggregations
        cur.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'active'")
        active_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM invoices")
        inv_stats = cur.fetchone()

        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments")
        pay_total = cur.fetchone()[0]

        conn.close()
        elapsed = time.time() - t0

        self.assertLess(elapsed, 2.0, f"Query took {elapsed:.4f}s, expected under 2.0s")


if __name__ == "__main__":
    unittest.main()
