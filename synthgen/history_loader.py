"""
History Database Loader
Loads behavioral history data into PostgreSQL fact tables
"""
import psycopg2
from psycopg2.extras import execute_batch
from typing import List
import logging

logger = logging.getLogger(__name__)


class HistoryLoader:
    """Loads history events into database"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None

    def connect(self):
        """Connect to database"""
        self.conn = psycopg2.connect(self.database_url)
        self.conn.autocommit = False

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def load_presentations(self, presentations: List):
        """Load presentation events"""
        if not presentations:
            return

        logger.info(f"Loading {len(presentations)} presentation events...")

        sql = """
            INSERT INTO fct_presentations (
                account_id, present_date, amount, status, bounce_reason, inst_no
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        data = [
            (p.account_id, p.present_date, p.amount, p.status, p.bounce_reason, p.inst_no)
            for p in presentations
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, data, page_size=5000)
            self.conn.commit()

        logger.info(f"✓ Loaded {len(presentations)} presentations")

    def load_payments(self, payments: List):
        """Load payment events"""
        if not payments:
            return

        logger.info(f"Loading {len(payments)} payment events...")

        sql = """
            INSERT INTO fct_payments (
                account_id, pay_date, amount, mode, alloc_to_inst, collected_by
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        data = [
            (p.account_id, p.pay_date, p.amount, p.mode, p.alloc_to_inst, p.collected_by)
            for p in payments
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, data, page_size=5000)
            self.conn.commit()

        logger.info(f"✓ Loaded {len(payments)} payments")

    def load_calls(self, calls: List):
        """Load call events"""
        if not calls:
            return

        logger.info(f"Loading {len(calls)} call events...")

        sql = """
            INSERT INTO fct_calls (
                account_id, customer_id, phone, channel, agent_id,
                call_start_time, call_end_time, duration_sec, outcome, disposition
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        data = [
            (
                c.account_id, c.customer_id, c.phone, c.channel, c.agent_id,
                c.call_start_time,
                c.call_start_time if c.duration_sec else None,  # Simplified
                c.duration_sec, c.outcome, c.disposition
            )
            for c in calls
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, data, page_size=5000)
            self.conn.commit()

        logger.info(f"✓ Loaded {len(calls)} calls")

    def load_visits(self, visits: List):
        """Load visit events"""
        if not visits:
            return

        logger.info(f"Loading {len(visits)} visit events...")

        sql = """
            INSERT INTO fct_visits (
                account_id, customer_id, agent_id, visit_date, visit_time,
                disposition, amount_collected, payment_mode
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        data = [
            (
                v.account_id, v.customer_id, v.agent_id, v.visit_date, v.visit_date,  # visit_time = visit_date for now
                v.disposition, v.amount_collected, v.payment_mode
            )
            for v in visits
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, data, page_size=5000)
            self.conn.commit()

        logger.info(f"✓ Loaded {len(visits)} visits")

    def load_ptps(self, ptps: List):
        """Load PTP events"""
        if not ptps:
            return

        logger.info(f"Loading {len(ptps)} PTP events...")

        sql = """
            INSERT INTO fct_ptp (
                account_id, customer_id, made_by, channel,
                promise_date, promise_amount, payment_mode, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        data = [
            (
                p.account_id, p.customer_id, p.made_by, p.channel,
                p.promise_date, p.promise_amount, p.payment_mode, p.status
            )
            for p in ptps
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, data, page_size=5000)
            self.conn.commit()

        logger.info(f"✓ Loaded {len(ptps)} PTPs")

    def load_sms(self, sms_list: List):
        """Load SMS events"""
        if not sms_list:
            return

        logger.info(f"Loading {len(sms_list)} SMS events...")

        sql = """
            INSERT INTO fct_sms (
                account_id, customer_id, phone, message_text, scheduled_at, sent_at, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        data = [
            (s.account_id, s.customer_id, s.phone, s.message_text, s.scheduled_at, s.scheduled_at, s.status)
            for s in sms_list
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, data, page_size=5000)
            self.conn.commit()

        logger.info(f"✓ Loaded {len(sms_list)} SMS")

    def load_mart_snapshots(self, snapshots: List):
        """Load mart_account_daily snapshots"""
        if not snapshots:
            return

        logger.info(f"Loading {len(snapshots)} mart snapshots...")

        sql = """
            INSERT INTO mart_account_daily (
                account_id, date, dpd, bucket, overdue_amt, pos, total_dues, emi_amt, cycle_day,
                last_contact_date, last_contact_channel, last_payment_date, has_open_ptp
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (account_id, date) DO UPDATE SET
                dpd = EXCLUDED.dpd,
                bucket = EXCLUDED.bucket,
                overdue_amt = EXCLUDED.overdue_amt,
                pos = EXCLUDED.pos,
                total_dues = EXCLUDED.total_dues,
                last_contact_date = EXCLUDED.last_contact_date,
                last_contact_channel = EXCLUDED.last_contact_channel,
                last_payment_date = EXCLUDED.last_payment_date,
                has_open_ptp = EXCLUDED.has_open_ptp
        """

        data = [
            (
                s.account_id, s.date, s.dpd, s.bucket, s.overdue_amt, s.pos, s.total_dues,
                s.emi_amt, s.cycle_day, s.last_contact_date, s.last_contact_channel,
                s.last_payment_date, s.has_open_ptp
            )
            for s in snapshots
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, data, page_size=5000)
            self.conn.commit()

        logger.info(f"✓ Loaded {len(snapshots)} mart snapshots")

    def get_stats(self) -> dict:
        """Get fact table statistics"""
        stats = {}

        with self.conn.cursor() as cur:
            tables = [
                "fct_presentations",
                "fct_payments",
                "fct_calls",
                "fct_visits",
                "fct_ptp",
                "fct_sms",
                "mart_account_daily",
            ]

            for table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                stats[table] = count

        return stats
