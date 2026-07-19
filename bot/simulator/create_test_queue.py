"""
Create Test Queue - Populate call_queue with sample calls for testing

Usage:
    python bot/simulator/create_test_queue.py --count 20
"""

import psycopg2
import psycopg2.extras
import argparse
from datetime import datetime, timedelta
import os
import random

def create_test_queue(count=20):
    """
    Create a test call queue with sample accounts

    Args:
        count: Number of queue items to create
    """
    # Database connection
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        dbname='collectos',
        user='collectos',
        password=os.getenv('POSTGRES_PASSWORD', 'collectos_dev_password_change_in_production'),
    )

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get sample accounts with overdue amounts
            cur.execute("""
                SELECT
                    a.account_id,
                    a.customer_id,
                    c.phone as primary_phone,
                    mad.dpd,
                    mad.overdue_amt,
                    mad.treatment_code
                FROM dim_account a
                JOIN dim_customer c ON a.customer_id = c.customer_id
                JOIN mart_account_daily mad ON a.account_id = mad.account_id
                WHERE mad.date = (SELECT MAX(date) FROM mart_account_daily)
                  AND mad.dpd > 0
                  AND mad.overdue_amt > 0
                  AND c.phone IS NOT NULL
                ORDER BY RANDOM()
                LIMIT %s
            """, (count,))

            accounts = cur.fetchall()

            if not accounts:
                print("No accounts found with overdue amounts.")
                print("Run 'make seed' or 'make daily' first to populate data.")
                return 0

            print(f"Found {len(accounts)} accounts with overdue amounts")

            # Clear existing test queue (campaign_id IS NULL = test queue)
            cur.execute("DELETE FROM call_queue WHERE campaign_id IS NULL AND channel = 'BOT'")
            conn.commit()

            # Insert test queue items
            now = datetime.now()

            inserted = 0
            for i, account in enumerate(accounts):
                # Schedule slot (spread over next 4 hours)
                slot_offset = timedelta(minutes=random.randint(0, 240))
                scheduled_slot = now + slot_offset

                # Priority score (0-100, higher = more important)
                # Based on DPD and overdue amount
                priority_score = min(100.0, float(account['dpd']) * 2.0 + float(account['overdue_amt']) / 1000.0)

                cur.execute("""
                    INSERT INTO call_queue (
                        account_id,
                        customer_id,
                        phone,
                        campaign_id,
                        channel,
                        priority_score,
                        status,
                        scheduled_slot,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    account['account_id'],
                    account['customer_id'],
                    account['primary_phone'],
                    None,  # NULL campaign_id for test queue
                    'BOT',
                    priority_score,
                    'QUEUED',
                    scheduled_slot,
                ))

                inserted += 1

            conn.commit()

            print(f"\nCreated {inserted} test queue items")
            print("Campaign ID: NULL (test queue)")
            print("Channel: BOT")
            print("Status: QUEUED")
            print(f"Scheduled slots: {now.strftime('%H:%M')} - {(now + timedelta(hours=4)).strftime('%H:%M')}")

            # Show distribution
            cur.execute("""
                SELECT
                    CASE
                        WHEN priority_score >= 70 THEN 'HIGH'
                        WHEN priority_score >= 40 THEN 'MEDIUM'
                        ELSE 'LOW'
                    END as priority,
                    COUNT(*) as count
                FROM call_queue
                WHERE campaign_id IS NULL AND channel = 'BOT'
                GROUP BY 1
            """)

            print("\nPriority distribution:")
            for row in cur.fetchall():
                print(f"  {row['priority']}: {row['count']}")

            return inserted

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Create test call queue')
    parser.add_argument('--count', type=int, default=20, help='Number of queue items (default: 20)')

    args = parser.parse_args()

    print("=" * 60)
    print("CREATE TEST CALL QUEUE")
    print("=" * 60)

    count = create_test_queue(args.count)

    if count > 0:
        print("\n" + "=" * 60)
        print("TEST QUEUE READY")
        print("=" * 60)
        print("\nRun simulator with:")
        print("  python -m bot.simulator --limit 10 --dry-run")
        print()

    return 0 if count > 0 else 1


if __name__ == '__main__':
    exit(main())
