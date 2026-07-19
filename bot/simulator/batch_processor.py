"""
Batch Call Processor - Process full day's call queue with simulator

Reads from call_queue table, processes calls through simulator,
and logs results back to database.
"""

import logging
import psycopg2
import psycopg2.extras
from typing import Dict, List, Optional
from datetime import datetime, date
import os

from .personas import PersonaGenerator, CustomerPersona
from .persona_responses import PersonaResponseEngine
from .simulator import CallSimulator

logger = logging.getLogger(__name__)


class BatchCallProcessor:
    """
    Process a batch of calls from the queue using the simulator
    """

    def __init__(
        self,
        db_host: str = 'localhost',
        db_port: int = 5432,
        db_name: str = 'collectos',
        db_user: str = 'collectos',
        db_password: Optional[str] = None,
    ):
        """
        Initialize batch processor

        Args:
            db_host: PostgreSQL host
            db_port: PostgreSQL port
            db_name: Database name
            db_user: Database user
            db_password: Database password
        """
        self.db_config = {
            'host': db_host,
            'port': db_port,
            'dbname': db_name,
            'user': db_user,
            'password': db_password or os.getenv('POSTGRES_PASSWORD'),
        }

        self.persona_generator = PersonaGenerator(seed=42)
        self.response_engine = PersonaResponseEngine()
        self.simulator = CallSimulator(response_engine=self.response_engine)

    def get_db_connection(self):
        """Create database connection"""
        return psycopg2.connect(**self.db_config)

    def fetch_call_queue(
        self,
        channel: str = 'BOT',
        status: str = 'QUEUED',
        limit: Optional[int] = None,
        target_date: Optional[date] = None,
    ) -> List[Dict]:
        """
        Fetch calls from queue

        Args:
            channel: Channel filter (bot, human, etc.)
            status: Queue status (queued, new, etc.)
            limit: Max calls to fetch
            target_date: Target date filter

        Returns:
            List of queue items with account details
        """
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = """
                    SELECT
                        q.queue_id,
                        q.account_id,
                        q.channel,
                        q.priority_score,
                        q.scheduled_slot,
                        q.campaign_id,
                        a.customer_id,
                        c.name as customer_name,
                        c.lang_pref as language,
                        mad.dpd,
                        mad.overdue_amt,
                        mad.emi_amt,
                        mad.treatment_code,
                        acc.product_type,
                        aa.archetype
                    FROM call_queue q
                    JOIN dim_account a ON q.account_id = a.account_id
                    JOIN dim_customer c ON a.customer_id = c.customer_id
                    LEFT JOIN mart_account_daily mad ON
                        q.account_id = mad.account_id AND
                        mad.date = CURRENT_DATE
                    LEFT JOIN dim_account acc ON q.account_id = acc.account_id
                    LEFT JOIN account_archetypes aa ON q.account_id = aa.account_id
                    WHERE q.channel = %s
                      AND q.status = %s
                """

                params = [channel, status]

                if target_date:
                    query += " AND DATE(q.scheduled_slot) = %s"
                    params.append(target_date)

                query += " ORDER BY q.priority_score DESC, q.scheduled_slot ASC"

                if limit:
                    query += f" LIMIT {limit}"

                cur.execute(query, params)
                return cur.fetchall()

    def process_queue(
        self,
        channel: str = 'BOT',
        limit: Optional[int] = None,
        target_date: Optional[date] = None,
        dry_run: bool = False,
    ) -> Dict:
        """
        Process calls from queue

        Args:
            channel: Channel to process (bot, human)
            limit: Max calls to process
            target_date: Target date (default: today)
            dry_run: If True, don't write results to DB

        Returns:
            Processing summary dict
        """
        logger.info(f"Starting batch processing: channel={channel}, limit={limit}")

        # Fetch queue
        queue_items = self.fetch_call_queue(
            channel=channel,
            status='QUEUED',
            limit=limit,
            target_date=target_date or date.today(),
        )

        logger.info(f"Fetched {len(queue_items)} calls from queue")

        if not queue_items:
            return {
                'total_calls': 0,
                'processed': 0,
                'dispositions': {},
                'ptps_made': 0,
            }

        # Generate personas
        personas = self._generate_personas_for_queue(queue_items)

        # Prepare flow types and contexts
        flow_types = {}
        contexts = {}

        for item in queue_items:
            account_id = item['account_id']
            # Determine flow type based on treatment or campaign
            flow_types[account_id] = self._determine_flow_type(item)
            contexts[account_id] = {
                'product_type': item.get('product_type', 'Auto Loan'),
                'emi_amt': float(item.get('emi_amt', 0)),
                'overdue_amt': float(item.get('overdue_amt', 0)),
            }

        # Run simulations
        logger.info(f"Running simulations for {len(personas)} personas")
        results = self.simulator.simulate_batch(personas, flow_types, contexts)

        # Write results to database
        if not dry_run:
            self._write_results_to_db(results, queue_items)
        else:
            logger.info("Dry run - skipping database writes")

        # Generate summary
        summary = self._generate_summary(results)

        logger.info(f"Batch processing complete: {summary}")

        return summary

    def _generate_personas_for_queue(
        self,
        queue_items: List[Dict],
    ) -> Dict[str, CustomerPersona]:
        """Generate personas for queue items"""
        accounts = []
        for item in queue_items:
            accounts.append({
                'account_id': item['account_id'],
                'customer_name': item['customer_name'],
                'archetype': item.get('archetype', 'PRIME'),
                'language': item.get('language', 'en'),
                'overdue_amt': float(item.get('overdue_amt', 0)),
                'dpd': int(item.get('dpd', 0)),
            })

        return self.persona_generator.generate_batch_personas(accounts)

    def _determine_flow_type(self, queue_item: Dict) -> str:
        """Determine conversation flow type from queue item"""
        treatment = queue_item.get('treatment_code', '')

        # Map treatment codes to flows
        if 'PRE_DUE' in str(treatment):
            return 'pre_due_reminder'
        elif 'PTP' in str(treatment) or 'BOUNCE' in str(treatment):
            return 'post_bounce_ptp'
        else:
            # Default
            return 'post_bounce_ptp'

    def _write_results_to_db(
        self,
        results: List[Dict],
        queue_items: List[Dict],
    ):
        """Write simulation results to database"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                # Update queue status
                self._update_queue_status(cur, results, queue_items)

                # Insert call records
                self._insert_call_records(cur, results)

                # Insert PTP records
                self._insert_ptp_records(cur, results)

                # Insert dispositions
                self._insert_dispositions(cur, results)

                conn.commit()

        logger.info(f"Wrote {len(results)} results to database")

    def _update_queue_status(self, cur, results, queue_items):
        """Update call queue status to 'DONE'"""
        queue_map = {item['account_id']: item['queue_id'] for item in queue_items}

        for result in results:
            queue_id = queue_map.get(result['account_id'])
            if queue_id:
                cur.execute("""
                    UPDATE call_queue
                    SET status = 'DONE',
                        updated_at = NOW()
                    WHERE queue_id = %s
                """, (queue_id,))

    def _insert_call_records(self, cur, results):
        """Insert records into fct_calls"""
        for result in results:
            cur.execute("""
                INSERT INTO fct_calls (
                    account_id, call_date, call_time, channel, call_outcome,
                    disposition, duration_seconds, transcript, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
            """, (
                result['account_id'],
                datetime.now().date(),
                datetime.now().time(),
                'BOT',
                self._map_disposition_to_outcome(result['disposition']),
                result['disposition'],
                result['duration_seconds'],
                self._format_transcript(result['transcript']),
            ))

    def _insert_ptp_records(self, cur, results):
        """Insert PTP records into fct_ptp"""
        for result in results:
            if result.get('ptp'):
                ptp = result['ptp']
                cur.execute("""
                    INSERT INTO fct_ptp (
                        account_id, made_by, channel, made_at,
                        promise_date, promised_amount, promise_mode, status,
                        created_at
                    ) VALUES (
                        %s, 'simulator', %s, NOW(), %s, %s, %s, %s, NOW()
                    )
                """, (
                    result['account_id'],
                    'BOT',
                    ptp['ptp_date'],
                    ptp['ptp_amount'],
                    ptp.get('ptp_mode', 'UPI'),
                    'open',
                ))

    def _insert_dispositions(self, cur, results):
        """Insert records into dispositions table"""
        for result in results:
            cur.execute("""
                INSERT INTO dispositions (
                    account_id, disposition_code, disposition_at,
                    agent_id, channel, notes, created_at
                ) VALUES (
                    %s, %s, NOW(), %s, %s, %s, NOW()
                )
            """, (
                result['account_id'],
                result['disposition'],
                'simulator',
                'BOT',
                f"Simulated call: {result['metadata'].get('persona_type', 'unknown')}",
            ))

    def _map_disposition_to_outcome(self, disposition: str) -> str:
        """Map disposition to call_outcome enum"""
        mapping = {
            'PTP': 'CONNECT_RPC',
            'NO_ANSWER': 'NO_ANSWER',
            'CUSTOMER_HUNG_UP': 'DISCONNECTED',
            'TECHNICAL_ERROR': 'FAILED',
            'COMPLETED': 'CONNECT_RPC',
            'ERROR': 'FAILED',
        }
        return mapping.get(disposition, 'CONNECT_RPC')

    def _format_transcript(self, transcript: List) -> str:
        """Format transcript for database storage"""
        lines = []
        for speaker, message, timestamp in transcript:
            lines.append(f"[{timestamp.strftime('%H:%M:%S')}] {speaker}: {message}")
        return "\n".join(lines)

    def _generate_summary(self, results: List[Dict]) -> Dict:
        """Generate processing summary"""
        dispositions = {}
        ptps_made = 0
        total_duration = 0.0

        for result in results:
            disp = result['disposition']
            dispositions[disp] = dispositions.get(disp, 0) + 1

            if result.get('ptp'):
                ptps_made += 1

            total_duration += result['duration_seconds']

        return {
            'total_calls': len(results),
            'processed': len(results),
            'dispositions': dispositions,
            'ptps_made': ptps_made,
            'total_duration_seconds': total_duration,
            'avg_duration_seconds': total_duration / len(results) if results else 0,
        }
