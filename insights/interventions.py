"""
Interventions Engine - Rule-based sensors and intervention triggers

Detects accounts needing special intervention and assigns ownership.
Monitors intervention execution and effectiveness.
"""

import psycopg2
import psycopg2.extras
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import os
import json


class InterventionType(Enum):
    """Types of interventions"""
    TL_CALL = 'tl_call'  # Team Lead personal call
    ACM_ESCALATION = 'acm_escalation'  # Area Collection Manager intervention
    FIELD_URGENT = 'field_urgent'  # Urgent field visit
    HARDSHIP_REVIEW = 'hardship_review'  # Special hardship committee
    LEGAL_NOTICE = 'legal_notice'  # Legal notice preparation
    SETTLEMENT_OFFER = 'settlement_offer'  # Settlement negotiation
    ACCOUNT_FREEZE = 'account_freeze'  # Freeze regular collections


class InterventionPriority(Enum):
    """Intervention priority levels"""
    CRITICAL = 'critical'  # Within 24 hours
    HIGH = 'high'  # Within 3 days
    MEDIUM = 'medium'  # Within 7 days
    LOW = 'low'  # Within 14 days


@dataclass
class InterventionTrigger:
    """Intervention trigger result"""
    account_id: str
    intervention_type: InterventionType
    priority: InterventionPriority
    reason: str
    assigned_to: Optional[str]
    triggered_at: datetime
    due_by: date
    context: Dict  # Additional context for intervention


class InterventionEngine:
    """
    Rule-based intervention detection and assignment

    Rule Sensors:
    1. Broken PTP Streak (3+ broken PTPs) → TL Call
    2. High Value Stuck (₹50K+, 30+ DPD, no payment 14 days) → ACM Escalation
    3. Dispute Escalation (2+ dispute dispositions) → Hardship Review
    4. Self-Cure Risk (high bounce_p, low selfcure_p, B3) → Field Urgent
    5. Legal Trigger (90+ DPD, ₹100K+, no contact 30 days) → Legal Notice
    6. Settlement Opportunity (60+ DPD, consistent partial payments) → Settlement Offer
    """

    def __init__(
        self,
        db_host: str = 'localhost',
        db_port: int = 5432,
        db_name: str = 'collectos',
        db_user: str = 'collectos',
        db_password: Optional[str] = None,
    ):
        self.db_config = {
            'host': db_host,
            'port': db_port,
            'dbname': db_name,
            'user': db_user,
            'password': db_password or os.getenv('POSTGRES_PASSWORD'),
        }

    def get_db_connection(self):
        """Create database connection"""
        return psycopg2.connect(**self.db_config)

    def detect_broken_ptp_streak(
        self,
        target_date: date,
        min_broken: int = 3,
    ) -> List[InterventionTrigger]:
        """
        Detect accounts with repeated broken PTPs

        Rule: 3+ broken PTPs in last 30 days → TL personal call
        """
        triggers = []

        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        ptp.account_id,
                        COUNT(*) as broken_count,
                        STRING_AGG(TO_CHAR(ptp.promise_date, 'YYYY-MM-DD'), ', '
                            ORDER BY ptp.promise_date DESC) as broken_dates,
                        mad.owner_agent_id,
                        ag.team_id,
                        t.tl_agent_id,
                        mad.overdue_amt,
                        mad.dpd
                    FROM fct_ptp ptp
                    JOIN mart_account_daily mad ON
                        ptp.account_id = mad.account_id AND
                        mad.date = %s
                    LEFT JOIN dim_agent ag ON mad.owner_agent_id = ag.agent_id
                    LEFT JOIN dim_team t ON ag.team_id = t.team_id
                    WHERE ptp.status = 'broken'
                      AND ptp.promise_date >= %s - INTERVAL '30 days'
                    GROUP BY ptp.account_id, mad.owner_agent_id, ag.team_id,
                             t.tl_agent_id, mad.overdue_amt, mad.dpd
                    HAVING COUNT(*) >= %s
                    ORDER BY COUNT(*) DESC
                """, (target_date, target_date, min_broken))

                accounts = cur.fetchall()

        for acc in accounts:
            triggers.append(InterventionTrigger(
                account_id=acc['account_id'],
                intervention_type=InterventionType.TL_CALL,
                priority=InterventionPriority.HIGH,
                reason=f"Broken PTP streak: {acc['broken_count']} broken promises in 30 days",
                assigned_to=acc['tl_agent_id'],
                triggered_at=datetime.now(),
                due_by=target_date + timedelta(days=3),
                context={
                    'broken_count': acc['broken_count'],
                    'broken_dates': acc['broken_dates'],
                    'owner_agent_id': acc['owner_agent_id'],
                    'overdue_amt': float(acc['overdue_amt']),
                    'dpd': acc['dpd'],
                }
            ))

        return triggers

    def detect_high_value_stuck(
        self,
        target_date: date,
        min_overdue: float = 50000,
        min_dpd: int = 30,
        no_payment_days: int = 14,
    ) -> List[InterventionTrigger]:
        """
        Detect high-value accounts stuck with no recent payment

        Rule: ₹50K+ overdue, 30+ DPD, no payment in 14 days → ACM Escalation
        """
        triggers = []

        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        mad.account_id,
                        mad.overdue_amt,
                        mad.dpd,
                        mad.bucket,
                        mad.owner_agent_id,
                        ag.team_id,
                        t.acm_agent_id,
                        c.name as customer_name,
                        COALESCE(last_pay.days_since_payment, 999) as days_since_payment
                    FROM mart_account_daily mad
                    LEFT JOIN dim_customer c ON mad.customer_id = c.customer_id
                    LEFT JOIN dim_agent ag ON mad.owner_agent_id = ag.agent_id
                    LEFT JOIN dim_team t ON ag.team_id = t.team_id
                    LEFT JOIN LATERAL (
                        SELECT DATE_PART('day', %s - MAX(DATE(pay_date))) as days_since_payment
                        FROM fct_payments
                        WHERE account_id = mad.account_id
                    ) last_pay ON TRUE
                    WHERE mad.date = %s
                      AND mad.overdue_amt >= %s
                      AND mad.dpd >= %s
                      AND COALESCE(last_pay.days_since_payment, 999) >= %s
                    ORDER BY mad.overdue_amt DESC
                """, (target_date, target_date, min_overdue, min_dpd, no_payment_days))

                accounts = cur.fetchall()

        for acc in accounts:
            triggers.append(InterventionTrigger(
                account_id=acc['account_id'],
                intervention_type=InterventionType.ACM_ESCALATION,
                priority=InterventionPriority.CRITICAL,
                reason=f"High-value stuck: ₹{acc['overdue_amt']:,.0f} overdue, {acc['dpd']} DPD, no payment {acc['days_since_payment']} days",
                assigned_to=acc['acm_agent_id'],
                triggered_at=datetime.now(),
                due_by=target_date + timedelta(days=1),
                context={
                    'customer_name': acc['customer_name'],
                    'overdue_amt': float(acc['overdue_amt']),
                    'dpd': acc['dpd'],
                    'bucket': acc['bucket'],
                    'days_since_payment': acc['days_since_payment'],
                    'owner_agent_id': acc['owner_agent_id'],
                }
            ))

        return triggers

    def detect_dispute_escalation(
        self,
        target_date: date,
        min_disputes: int = 2,
    ) -> List[InterventionTrigger]:
        """
        Detect accounts with repeated dispute dispositions

        Rule: 2+ dispute dispositions in 30 days → Hardship Review
        """
        triggers = []

        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        disp.account_id,
                        COUNT(*) as dispute_count,
                        STRING_AGG(disp.notes, ' | ' ORDER BY disp.created_at DESC) as dispute_notes,
                        mad.owner_agent_id,
                        ag.team_id,
                        mad.overdue_amt,
                        mad.dpd
                    FROM dispositions disp
                    JOIN mart_account_daily mad ON
                        disp.account_id = mad.account_id AND
                        mad.date = %s
                    LEFT JOIN dim_agent ag ON mad.owner_agent_id = ag.agent_id
                    WHERE disp.disposition_code IN ('DISPUTE_AMOUNT', 'DISPUTE_PAID', 'DISPUTE_NEVER_PURCHASED')
                      AND DATE(disp.created_at) >= %s - INTERVAL '30 days'
                    GROUP BY disp.account_id, mad.owner_agent_id, ag.team_id,
                             mad.overdue_amt, mad.dpd
                    HAVING COUNT(*) >= %s
                    ORDER BY COUNT(*) DESC
                """, (target_date, target_date, min_disputes))

                accounts = cur.fetchall()

        for acc in accounts:
            triggers.append(InterventionTrigger(
                account_id=acc['account_id'],
                intervention_type=InterventionType.HARDSHIP_REVIEW,
                priority=InterventionPriority.HIGH,
                reason=f"Dispute escalation: {acc['dispute_count']} dispute claims in 30 days",
                assigned_to=None,  # Assigned to hardship committee
                triggered_at=datetime.now(),
                due_by=target_date + timedelta(days=7),
                context={
                    'dispute_count': acc['dispute_count'],
                    'dispute_notes': acc['dispute_notes'],
                    'owner_agent_id': acc['owner_agent_id'],
                    'overdue_amt': float(acc['overdue_amt']),
                    'dpd': acc['dpd'],
                }
            ))

        return triggers

    def detect_selfcure_risk(
        self,
        target_date: date,
        max_selfcure_p: float = 0.15,
        min_bounce_p: float = 0.40,
    ) -> List[InterventionTrigger]:
        """
        Detect accounts at risk of NOT self-curing (need urgent field visit)

        Rule: Low selfcure_p, high bounce_p, B3 bucket → Field Urgent
        """
        triggers = []

        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        mad.account_id,
                        mad.selfcure_p,
                        mad.bounce_p,
                        mad.bucket,
                        mad.dpd,
                        mad.overdue_amt,
                        mad.owner_agent_id,
                        ag.name as agent_name
                    FROM mart_account_daily mad
                    LEFT JOIN dim_agent ag ON mad.owner_agent_id = ag.agent_id
                    WHERE mad.date = %s
                      AND mad.bucket = 'B3'
                      AND mad.selfcure_p <= %s
                      AND mad.bounce_p >= %s
                      AND mad.owner_agent_id IS NOT NULL
                    ORDER BY mad.selfcure_p ASC, mad.overdue_amt DESC
                    LIMIT 50  -- Top 50 most at risk
                """, (target_date, max_selfcure_p, min_bounce_p))

                accounts = cur.fetchall()

        for acc in accounts:
            triggers.append(InterventionTrigger(
                account_id=acc['account_id'],
                intervention_type=InterventionType.FIELD_URGENT,
                priority=InterventionPriority.CRITICAL,
                reason=f"Self-cure risk: {acc['selfcure_p']:.0%} cure probability, {acc['bounce_p']:.0%} bounce risk",
                assigned_to=acc['owner_agent_id'],
                triggered_at=datetime.now(),
                due_by=target_date + timedelta(days=2),
                context={
                    'selfcure_p': acc['selfcure_p'],
                    'bounce_p': acc['bounce_p'],
                    'bucket': acc['bucket'],
                    'dpd': acc['dpd'],
                    'overdue_amt': float(acc['overdue_amt']),
                    'agent_name': acc['agent_name'],
                }
            ))

        return triggers

    def detect_legal_trigger(
        self,
        target_date: date,
        min_dpd: int = 90,
        min_overdue: float = 100000,
        no_contact_days: int = 30,
    ) -> List[InterventionTrigger]:
        """
        Detect accounts that may need legal action

        Rule: 90+ DPD, ₹100K+, no contact in 30 days → Legal Notice
        """
        triggers = []

        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        mad.account_id,
                        mad.dpd,
                        mad.overdue_amt,
                        mad.bucket,
                        c.name as customer_name,
                        c.geo_state,
                        COALESCE(last_contact.days_since_contact, 999) as days_since_contact
                    FROM mart_account_daily mad
                    LEFT JOIN dim_customer c ON mad.customer_id = c.customer_id
                    LEFT JOIN LATERAL (
                        SELECT MIN(days) as days_since_contact
                        FROM (
                            SELECT DATE_PART('day', %s - MAX(DATE(call_date))) as days
                            FROM fct_calls WHERE account_id = mad.account_id
                            UNION ALL
                            SELECT DATE_PART('day', %s - MAX(DATE(visit_date))) as days
                            FROM fct_visits WHERE account_id = mad.account_id
                        ) contacts
                    ) last_contact ON TRUE
                    WHERE mad.date = %s
                      AND mad.dpd >= %s
                      AND mad.overdue_amt >= %s
                      AND COALESCE(last_contact.days_since_contact, 999) >= %s
                    ORDER BY mad.overdue_amt DESC
                """, (target_date, target_date, target_date, min_dpd, min_overdue, no_contact_days))

                accounts = cur.fetchall()

        for acc in accounts:
            triggers.append(InterventionTrigger(
                account_id=acc['account_id'],
                intervention_type=InterventionType.LEGAL_NOTICE,
                priority=InterventionPriority.MEDIUM,
                reason=f"Legal threshold: {acc['dpd']} DPD, ₹{acc['overdue_amt']:,.0f} overdue, {acc['days_since_contact']} days no contact",
                assigned_to=None,  # Assigned to legal team
                triggered_at=datetime.now(),
                due_by=target_date + timedelta(days=14),
                context={
                    'customer_name': acc['customer_name'],
                    'dpd': acc['dpd'],
                    'overdue_amt': float(acc['overdue_amt']),
                    'bucket': acc['bucket'],
                    'geo_state': acc['geo_state'],
                    'days_since_contact': acc['days_since_contact'],
                }
            ))

        return triggers

    def detect_settlement_opportunity(
        self,
        target_date: date,
        min_dpd: int = 60,
        min_partial_payments: int = 3,
    ) -> List[InterventionTrigger]:
        """
        Detect accounts showing partial payment behavior (settlement candidates)

        Rule: 60+ DPD, 3+ partial payments, consistent payment pattern → Settlement Offer
        """
        triggers = []

        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    WITH payment_patterns AS (
                        SELECT
                            p.account_id,
                            COUNT(*) as payment_count,
                            AVG(p.amount) as avg_payment,
                            STDDEV(p.amount) as stddev_payment,
                            MAX(DATE(p.pay_date)) as last_payment_date
                        FROM fct_payments p
                        WHERE DATE(p.pay_date) >= %s - INTERVAL '90 days'
                        GROUP BY p.account_id
                        HAVING COUNT(*) >= %s
                    )
                    SELECT
                        mad.account_id,
                        mad.dpd,
                        mad.overdue_amt,
                        mad.bucket,
                        pp.payment_count,
                        pp.avg_payment,
                        pp.last_payment_date,
                        mad.owner_agent_id,
                        ag.team_id,
                        t.acm_agent_id
                    FROM mart_account_daily mad
                    JOIN payment_patterns pp ON mad.account_id = pp.account_id
                    LEFT JOIN dim_agent ag ON mad.owner_agent_id = ag.agent_id
                    LEFT JOIN dim_team t ON ag.team_id = t.team_id
                    WHERE mad.date = %s
                      AND mad.dpd >= %s
                      AND pp.avg_payment < mad.overdue_amt / 3  -- Partial payments
                    ORDER BY pp.payment_count DESC, mad.overdue_amt DESC
                    LIMIT 20  -- Top 20 candidates
                """, (target_date, min_partial_payments, target_date, min_dpd))

                accounts = cur.fetchall()

        for acc in accounts:
            triggers.append(InterventionTrigger(
                account_id=acc['account_id'],
                intervention_type=InterventionType.SETTLEMENT_OFFER,
                priority=InterventionPriority.MEDIUM,
                reason=f"Settlement opportunity: {acc['payment_count']} partial payments, avg ₹{acc['avg_payment']:,.0f}",
                assigned_to=acc['acm_agent_id'],
                triggered_at=datetime.now(),
                due_by=target_date + timedelta(days=7),
                context={
                    'dpd': acc['dpd'],
                    'overdue_amt': float(acc['overdue_amt']),
                    'payment_count': acc['payment_count'],
                    'avg_payment': float(acc['avg_payment']),
                    'last_payment_date': acc['last_payment_date'].isoformat(),
                    'owner_agent_id': acc['owner_agent_id'],
                }
            ))

        return triggers

    def run_all_sensors(self, target_date: date) -> List[InterventionTrigger]:
        """Run all intervention sensors and return triggers"""
        all_triggers = []

        print(f"Running intervention sensors for {target_date}...\n")

        # Sensor 1: Broken PTP Streak
        print("Sensor 1: Detecting broken PTP streaks...")
        triggers = self.detect_broken_ptp_streak(target_date)
        all_triggers.extend(triggers)
        print(f"  Found {len(triggers)} triggers\n")

        # Sensor 2: High Value Stuck
        print("Sensor 2: Detecting high-value stuck accounts...")
        triggers = self.detect_high_value_stuck(target_date)
        all_triggers.extend(triggers)
        print(f"  Found {len(triggers)} triggers\n")

        # Sensor 3: Dispute Escalation
        print("Sensor 3: Detecting dispute escalations...")
        triggers = self.detect_dispute_escalation(target_date)
        all_triggers.extend(triggers)
        print(f"  Found {len(triggers)} triggers\n")

        # Sensor 4: Self-Cure Risk
        print("Sensor 4: Detecting self-cure risk accounts...")
        triggers = self.detect_selfcure_risk(target_date)
        all_triggers.extend(triggers)
        print(f"  Found {len(triggers)} triggers\n")

        # Sensor 5: Legal Trigger
        print("Sensor 5: Detecting legal trigger accounts...")
        triggers = self.detect_legal_trigger(target_date)
        all_triggers.extend(triggers)
        print(f"  Found {len(triggers)} triggers\n")

        # Sensor 6: Settlement Opportunity
        print("Sensor 6: Detecting settlement opportunities...")
        triggers = self.detect_settlement_opportunity(target_date)
        all_triggers.extend(triggers)
        print(f"  Found {len(triggers)} triggers\n")

        return all_triggers

    def save_interventions(self, triggers: List[InterventionTrigger]):
        """Save intervention triggers to database"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                for trigger in triggers:
                    cur.execute("""
                        INSERT INTO interventions (
                            account_id, intervention_type, priority, reason,
                            assigned_to, triggered_at, due_by, context, status
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, 'pending'
                        )
                        ON CONFLICT (account_id, intervention_type, triggered_at)
                        DO NOTHING
                    """, (
                        trigger.account_id,
                        trigger.intervention_type.value,
                        trigger.priority.value,
                        trigger.reason,
                        trigger.assigned_to,
                        trigger.triggered_at,
                        trigger.due_by,
                        json.dumps(trigger.context),
                    ))

                conn.commit()

    def print_intervention_report(self, triggers: List[InterventionTrigger]):
        """Print formatted intervention report"""
        print("\n" + "="*100)
        print("INTERVENTION TRIGGERS - DAILY REPORT")
        print("="*100)

        # Group by intervention type
        by_type = {}
        for trigger in triggers:
            int_type = trigger.intervention_type.value
            if int_type not in by_type:
                by_type[int_type] = []
            by_type[int_type].append(trigger)

        for int_type, type_triggers in by_type.items():
            print(f"\n{int_type.upper().replace('_', ' ')} ({len(type_triggers)} accounts)")
            print("-" * 100)

            for trigger in sorted(type_triggers, key=lambda x: x.priority.value):
                print(f"  [{trigger.priority.value.upper()}] {trigger.account_id}")
                print(f"    Reason: {trigger.reason}")
                print(f"    Assigned: {trigger.assigned_to or 'Unassigned'}")
                print(f"    Due By: {trigger.due_by}")
                print()


def run_daily_interventions(target_date: Optional[date] = None):
    """Main entry point for daily intervention detection"""
    target_date = target_date or date.today()

    print(f"Running intervention sensors for {target_date}")

    engine = InterventionEngine()
    triggers = engine.run_all_sensors(target_date)

    print(f"\nTotal triggers: {len(triggers)}")

    engine.print_intervention_report(triggers)
    engine.save_interventions(triggers)

    print(f"\nInterventions saved to database")

    return triggers


if __name__ == '__main__':
    import sys

    target_date = date.today()
    if len(sys.argv) > 1:
        target_date = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()

    run_daily_interventions(target_date)
