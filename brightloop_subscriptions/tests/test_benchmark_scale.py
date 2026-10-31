"""
Scale-Up High Volume Benchmark Test.
Generates 1,000 subscriptions and invoices, measures latency,
and proves queries execute well under 2.0 seconds.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import database
import billing_engine


def run_benchmark():
    print("Beginning High-Volume Scale Benchmark (1,000 records)...")
    t0 = time.time()
    count = database.generate_bulk_demo_records(1000)
    gen_time = round((time.time() - t0) * 1000, 2)
    print(f"✓ Injected {count} records in {gen_time} ms")

    # Verify counts in DB
    conn = database.get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM subscriptions")
    total_subs = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM invoices")
    total_invs = cur.fetchone()[0]
    conn.close()

    print(f"✓ Total Subscriptions in DB: {total_subs}")
    print(f"✓ Total Invoices in DB: {total_invs}")

    # Benchmark Summary Aggregations
    t_query = time.time()
    conn = database.get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'active'")
    active_count = cur.fetchone()[0]

    cur.execute("""
    SELECT p.billing_frequency, COALESCE(SUM(sl.line_amount), 0.0) AS total_amount
    FROM subscriptions s
    JOIN plans p ON s.plan_id = p.id
    LEFT JOIN subscription_lines sl ON s.id = sl.subscription_id
    WHERE s.status = 'active'
    GROUP BY p.billing_frequency
    """)
    mrr_rows = cur.fetchall()

    cur.execute("SELECT COUNT(*), COALESCE(SUM(total_amount), 0), COALESCE(SUM(paid_amount), 0) FROM invoices")
    inv_stats = cur.fetchone()

    cur.execute("SELECT COUNT(*), COALESCE(SUM(total_amount - paid_amount), 0) FROM invoices WHERE status = 'overdue'")
    overdue_stats = cur.fetchone()

    conn.close()
    query_latency = round((time.time() - t_query) * 1000, 2)

    print(f"✓ Executed full finance summary over {total_subs} subscriptions and {total_invs} invoices:")
    print(f"  - Active Subscriptions: {active_count}")
    print(f"  - Invoices Count: {inv_stats[0]} (Total Billed: ${inv_stats[1]:,.2f}, Total Paid: ${inv_stats[2]:,.2f})")
    print(f"  - Overdue Invoices: {overdue_stats[0]} (Total Overdue: ${overdue_stats[1]:,.2f})")
    print(f"  - Query Latency: {query_latency} ms")
    print(f"  - Target Requirement: < 2,000 ms")
    print(f"  - Performance Margin: {(2000 - query_latency):.2f} ms headroom ({(query_latency / 2000.0 * 100):.2f}% of SLA limit)")

    assert query_latency < 2000.0, f"Query took {query_latency}ms, exceeding 2000ms SLA!"
    print("\n✓ SLA REQUIREMENT VERIFIED: Under 2.0 seconds achieved!")


if __name__ == "__main__":
    run_benchmark()
