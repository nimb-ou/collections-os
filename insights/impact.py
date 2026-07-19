"""
Impact Measurement - Uplift analysis and causal inference

Measures incremental impact of interventions (bot, field, SMS) vs control groups.
Uses propensity score matching and difference-in-differences for causal estimation.
"""

import psycopg2
import psycopg2.extras
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta
from dataclasses import dataclass
import os


@dataclass
class UpliftResult:
    """Results from uplift analysis"""
    intervention: str
    treatment_group_size: int
    control_group_size: int
    treatment_outcome: float
    control_outcome: float
    absolute_uplift: float
    relative_uplift: float
    p_value: float
    confidence_interval: Tuple[float, float]
    cost_per_treatment: float
    roi: float


class ImpactAnalyzer:
    """
    Measure incremental impact of interventions using causal inference

    Methods:
    1. Propensity Score Matching: Match treated/control by account characteristics
    2. Difference-in-Differences: Compare before/after changes
    3. A/B Test Analysis: Random assignment evaluation

    Key Metrics:
    - Resolution uplift (% accounts resolved)
    - Collection uplift (₹ collected)
    - PTP uplift (% promises made/kept)
    - Cost efficiency (uplift per ₹ spent)
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

    def calculate_bot_uplift(
        self,
        start_date: date,
        end_date: date,
        outcome_metric: str = 'resolution',
    ) -> UpliftResult:
        """
        Calculate uplift from bot calls vs no-contact control

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            outcome_metric: 'resolution', 'collection', or 'ptp'

        Returns:
            UpliftResult with treatment effect estimates
        """
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get treatment group (received bot call)
                cur.execute("""
                    WITH treatment_group AS (
                        SELECT DISTINCT
                            c.account_id,
                            mad.bucket,
                            mad.dpd,
                            mad.overdue_amt,
                            mad.bounce_p,
                            mad.selfcure_p,
                            -- Outcome: resolution within 7 days of call
                            CASE WHEN EXISTS (
                                SELECT 1 FROM fct_payments p
                                WHERE p.account_id = c.account_id
                                AND DATE(p.pay_date) BETWEEN DATE(c.call_date)
                                    AND DATE(c.call_date) + INTERVAL '7 days'
                            ) THEN 1 ELSE 0 END as resolved,
                            -- Outcome: collection amount
                            COALESCE((
                                SELECT SUM(p.amount) FROM fct_payments p
                                WHERE p.account_id = c.account_id
                                AND DATE(p.pay_date) BETWEEN DATE(c.call_date)
                                    AND DATE(c.call_date) + INTERVAL '7 days'
                            ), 0) as collected,
                            -- Outcome: PTP made
                            CASE WHEN EXISTS (
                                SELECT 1 FROM fct_ptp ptp
                                WHERE ptp.account_id = c.account_id
                                AND DATE(ptp.made_at) = DATE(c.call_date)
                                AND ptp.channel = 'BOT'
                            ) THEN 1 ELSE 0 END as ptp_made
                        FROM fct_calls c
                        JOIN mart_account_daily mad ON
                            c.account_id = mad.account_id AND
                            DATE(c.call_date) = mad.date
                        WHERE DATE(c.call_date) BETWEEN %s AND %s
                          AND c.channel = 'BOT'
                          AND c.call_outcome = 'CONNECT_RPC'
                    ),
                    control_group AS (
                        -- Matched control: similar accounts, no bot contact in period
                        SELECT
                            mad.account_id,
                            mad.bucket,
                            mad.dpd,
                            mad.overdue_amt,
                            mad.bounce_p,
                            mad.selfcure_p,
                            -- Same outcome windows
                            CASE WHEN EXISTS (
                                SELECT 1 FROM fct_payments p
                                WHERE p.account_id = mad.account_id
                                AND DATE(p.pay_date) BETWEEN mad.date
                                    AND mad.date + INTERVAL '7 days'
                            ) THEN 1 ELSE 0 END as resolved,
                            COALESCE((
                                SELECT SUM(p.amount) FROM fct_payments p
                                WHERE p.account_id = mad.account_id
                                AND DATE(p.pay_date) BETWEEN mad.date
                                    AND mad.date + INTERVAL '7 days'
                            ), 0) as collected,
                            0 as ptp_made  -- No bot call = no bot PTP
                        FROM mart_account_daily mad
                        WHERE mad.date BETWEEN %s AND %s
                          AND NOT EXISTS (
                              SELECT 1 FROM fct_calls c
                              WHERE c.account_id = mad.account_id
                                AND DATE(c.call_date) BETWEEN %s AND %s
                                AND c.channel = 'BOT'
                          )
                          -- Match on bucket only (simple matching)
                          AND mad.bucket IN (SELECT DISTINCT bucket FROM treatment_group)
                        ORDER BY RANDOM()
                        LIMIT (SELECT COUNT(*) FROM treatment_group)
                    )
                    SELECT
                        'treatment' as group_type,
                        COUNT(*) as size,
                        AVG(resolved) as resolution_rate,
                        AVG(collected) as avg_collection,
                        AVG(ptp_made) as ptp_rate
                    FROM treatment_group
                    UNION ALL
                    SELECT
                        'control' as group_type,
                        COUNT(*) as size,
                        AVG(resolved) as resolution_rate,
                        AVG(collected) as avg_collection,
                        AVG(ptp_made) as ptp_rate
                    FROM control_group
                """, (start_date, end_date, start_date, end_date, start_date, end_date))

                results = cur.fetchall()

        # Parse results
        treatment = next(r for r in results if r['group_type'] == 'treatment')
        control = next(r for r in results if r['group_type'] == 'control')

        # Select outcome metric
        if outcome_metric == 'resolution':
            treatment_outcome = treatment['resolution_rate']
            control_outcome = control['resolution_rate']
        elif outcome_metric == 'collection':
            treatment_outcome = treatment['avg_collection']
            control_outcome = control['avg_collection']
        else:  # ptp
            treatment_outcome = treatment['ptp_rate']
            control_outcome = control['ptp_rate']

        # Calculate uplift
        absolute_uplift = treatment_outcome - control_outcome
        relative_uplift = (absolute_uplift / control_outcome * 100) if control_outcome > 0 else 0

        # Simple t-test for statistical significance (approximation)
        # In production, use scipy.stats.ttest_ind
        n_t = treatment['size']
        n_c = control['size']
        pooled_std = np.sqrt((treatment_outcome * (1 - treatment_outcome) / n_t) +
                             (control_outcome * (1 - control_outcome) / n_c))
        z_score = absolute_uplift / pooled_std if pooled_std > 0 else 0
        p_value = 2 * (1 - self._norm_cdf(abs(z_score)))  # Two-tailed

        # Confidence interval (95%)
        margin = 1.96 * pooled_std
        ci = (absolute_uplift - margin, absolute_uplift + margin)

        # Cost and ROI (assuming ₹5 per bot call)
        cost_per_treatment = 5.0
        total_cost = n_t * cost_per_treatment
        incremental_value = absolute_uplift * n_t * (
            treatment['avg_collection'] if outcome_metric == 'collection' else 1000
        )
        roi = (incremental_value - total_cost) / total_cost if total_cost > 0 else 0

        return UpliftResult(
            intervention='bot_call',
            treatment_group_size=n_t,
            control_group_size=n_c,
            treatment_outcome=treatment_outcome,
            control_outcome=control_outcome,
            absolute_uplift=absolute_uplift,
            relative_uplift=relative_uplift,
            p_value=p_value,
            confidence_interval=ci,
            cost_per_treatment=cost_per_treatment,
            roi=roi,
        )

    def calculate_field_uplift(
        self,
        start_date: date,
        end_date: date,
    ) -> UpliftResult:
        """
        Calculate uplift from field visits vs telecaller contact

        Compares field visits to telecaller calls (both are interventions,
        but field is more expensive - want to measure incremental value)
        """
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    WITH field_treatment AS (
                        SELECT DISTINCT
                            v.account_id,
                            CASE WHEN EXISTS (
                                SELECT 1 FROM fct_payments p
                                WHERE p.account_id = v.account_id
                                AND DATE(p.pay_date) BETWEEN DATE(v.visit_date)
                                    AND DATE(v.visit_date) + INTERVAL '7 days'
                            ) THEN 1 ELSE 0 END as resolved,
                            COALESCE((
                                SELECT SUM(p.amount) FROM fct_payments p
                                WHERE p.account_id = v.account_id
                                AND DATE(p.pay_date) BETWEEN DATE(v.visit_date)
                                    AND DATE(v.visit_date) + INTERVAL '7 days'
                            ), 0) as collected
                        FROM fct_visits v
                        WHERE DATE(v.visit_date) BETWEEN %s AND %s
                          AND v.disposition IN ('CUSTOMER_MET', 'PAYMENT_COLLECTED')
                    ),
                    telecaller_control AS (
                        SELECT DISTINCT
                            c.account_id,
                            CASE WHEN EXISTS (
                                SELECT 1 FROM fct_payments p
                                WHERE p.account_id = c.account_id
                                AND DATE(p.pay_date) BETWEEN DATE(c.call_date)
                                    AND DATE(c.call_date) + INTERVAL '7 days'
                            ) THEN 1 ELSE 0 END as resolved,
                            COALESCE((
                                SELECT SUM(p.amount) FROM fct_payments p
                                WHERE p.account_id = c.account_id
                                AND DATE(p.pay_date) BETWEEN DATE(c.call_date)
                                    AND DATE(c.call_date) + INTERVAL '7 days'
                            ), 0) as collected
                        FROM fct_calls c
                        WHERE DATE(c.call_date) BETWEEN %s AND %s
                          AND c.channel = 'TELECALLER'
                          AND c.call_outcome = 'CONNECT_RPC'
                          -- Exclude accounts that also got field visit
                          AND NOT EXISTS (
                              SELECT 1 FROM fct_visits v
                              WHERE v.account_id = c.account_id
                                AND DATE(v.visit_date) BETWEEN %s AND %s
                          )
                        ORDER BY RANDOM()
                        LIMIT (SELECT COUNT(*) FROM field_treatment)
                    )
                    SELECT
                        'treatment' as group_type,
                        COUNT(*) as size,
                        AVG(resolved) as resolution_rate,
                        AVG(collected) as avg_collection
                    FROM field_treatment
                    UNION ALL
                    SELECT
                        'control' as group_type,
                        COUNT(*) as size,
                        AVG(resolved) as resolution_rate,
                        AVG(collected) as avg_collection
                    FROM telecaller_control
                """, (start_date, end_date, start_date, end_date, start_date, end_date))

                results = cur.fetchall()

        treatment = next(r for r in results if r['group_type'] == 'treatment')
        control = next(r for r in results if r['group_type'] == 'control')

        # Use collection as primary outcome for field
        treatment_outcome = treatment['avg_collection']
        control_outcome = control['avg_collection']

        absolute_uplift = treatment_outcome - control_outcome
        relative_uplift = (absolute_uplift / control_outcome * 100) if control_outcome > 0 else 0

        # Stats
        n_t = treatment['size']
        n_c = control['size']
        pooled_std = np.sqrt(
            (treatment_outcome * 0.5) ** 2 / n_t +
            (control_outcome * 0.5) ** 2 / n_c
        )
        z_score = absolute_uplift / pooled_std if pooled_std > 0 else 0
        p_value = 2 * (1 - self._norm_cdf(abs(z_score)))

        margin = 1.96 * pooled_std
        ci = (absolute_uplift - margin, absolute_uplift + margin)

        # Field visit cost: ₹200 (fuel, time)
        cost_per_treatment = 200.0
        total_cost = n_t * cost_per_treatment
        incremental_value = absolute_uplift * n_t
        roi = (incremental_value - total_cost) / total_cost if total_cost > 0 else 0

        return UpliftResult(
            intervention='field_visit',
            treatment_group_size=n_t,
            control_group_size=n_c,
            treatment_outcome=treatment_outcome,
            control_outcome=control_outcome,
            absolute_uplift=absolute_uplift,
            relative_uplift=relative_uplift,
            p_value=p_value,
            confidence_interval=ci,
            cost_per_treatment=cost_per_treatment,
            roi=roi,
        )

    def calculate_sms_campaign_uplift(
        self,
        campaign_id: str,
        outcome_window_days: int = 3,
    ) -> UpliftResult:
        """
        Calculate uplift from SMS campaign vs no-message control

        Requires campaign to have control group (A/B test design)
        """
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    WITH campaign_treatment AS (
                        SELECT
                            s.account_id,
                            CASE WHEN EXISTS (
                                SELECT 1 FROM fct_payments p
                                WHERE p.account_id = s.account_id
                                AND DATE(p.pay_date) BETWEEN DATE(s.sent_at)
                                    AND DATE(s.sent_at) + %s * INTERVAL '1 day'
                            ) THEN 1 ELSE 0 END as resolved,
                            COALESCE((
                                SELECT SUM(p.amount) FROM fct_payments p
                                WHERE p.account_id = s.account_id
                                AND DATE(p.pay_date) BETWEEN DATE(s.sent_at)
                                    AND DATE(s.sent_at) + %s * INTERVAL '1 day'
                            ), 0) as collected
                        FROM fct_sms s
                        WHERE s.campaign_id = %s
                          AND s.ab_group = 'treatment'
                    ),
                    campaign_control AS (
                        SELECT
                            s.account_id,
                            CASE WHEN EXISTS (
                                SELECT 1 FROM fct_payments p
                                WHERE p.account_id = s.account_id
                                AND DATE(p.pay_date) BETWEEN DATE(s.sent_at)
                                    AND DATE(s.sent_at) + %s * INTERVAL '1 day'
                            ) THEN 1 ELSE 0 END as resolved,
                            COALESCE((
                                SELECT SUM(p.amount) FROM fct_payments p
                                WHERE p.account_id = s.account_id
                                AND DATE(p.pay_date) BETWEEN DATE(s.sent_at)
                                    AND DATE(s.sent_at) + %s * INTERVAL '1 day'
                            ), 0) as collected
                        FROM fct_sms s
                        WHERE s.campaign_id = %s
                          AND s.ab_group = 'control'
                    )
                    SELECT
                        'treatment' as group_type,
                        COUNT(*) as size,
                        AVG(resolved) as resolution_rate,
                        AVG(collected) as avg_collection
                    FROM campaign_treatment
                    UNION ALL
                    SELECT
                        'control' as group_type,
                        COUNT(*) as size,
                        AVG(resolved) as resolution_rate,
                        AVG(collected) as avg_collection
                    FROM campaign_control
                """, (
                    outcome_window_days, outcome_window_days, campaign_id,
                    outcome_window_days, outcome_window_days, campaign_id
                ))

                results = cur.fetchall()

        if len(results) < 2:
            # Campaign has no control group
            return None

        treatment = next(r for r in results if r['group_type'] == 'treatment')
        control = next(r for r in results if r['group_type'] == 'control')

        treatment_outcome = treatment['resolution_rate']
        control_outcome = control['resolution_rate']

        absolute_uplift = treatment_outcome - control_outcome
        relative_uplift = (absolute_uplift / control_outcome * 100) if control_outcome > 0 else 0

        n_t = treatment['size']
        n_c = control['size']
        pooled_std = np.sqrt((treatment_outcome * (1 - treatment_outcome) / n_t) +
                             (control_outcome * (1 - control_outcome) / n_c))
        z_score = absolute_uplift / pooled_std if pooled_std > 0 else 0
        p_value = 2 * (1 - self._norm_cdf(abs(z_score)))

        margin = 1.96 * pooled_std
        ci = (absolute_uplift - margin, absolute_uplift + margin)

        # SMS cost: ₹0.20 per message
        cost_per_treatment = 0.20
        total_cost = n_t * cost_per_treatment
        incremental_value = absolute_uplift * n_t * treatment['avg_collection']
        roi = (incremental_value - total_cost) / total_cost if total_cost > 0 else 0

        return UpliftResult(
            intervention=f'sms_{campaign_id}',
            treatment_group_size=n_t,
            control_group_size=n_c,
            treatment_outcome=treatment_outcome,
            control_outcome=control_outcome,
            absolute_uplift=absolute_uplift,
            relative_uplift=relative_uplift,
            p_value=p_value,
            confidence_interval=ci,
            cost_per_treatment=cost_per_treatment,
            roi=roi,
        )

    def run_all_uplift_analyses(
        self,
        start_date: date,
        end_date: date,
    ) -> List[UpliftResult]:
        """Run all uplift analyses and return results"""
        results = []

        # Bot uplift
        print("Calculating bot call uplift...")
        bot_result = self.calculate_bot_uplift(start_date, end_date, outcome_metric='resolution')
        results.append(bot_result)

        # Field uplift
        print("Calculating field visit uplift...")
        field_result = self.calculate_field_uplift(start_date, end_date)
        results.append(field_result)

        # SMS campaigns (if any)
        # TODO: Query for active campaigns and analyze each

        return results

    @staticmethod
    def _norm_cdf(x):
        """Approximate normal CDF (for p-value calculation)"""
        # Using error function approximation
        return 0.5 * (1 + np.tanh(0.7978845608 * (x + 0.044715 * x**3)))

    def print_uplift_report(self, results: List[UpliftResult]):
        """Print formatted uplift report"""
        print("\n" + "="*80)
        print("IMPACT MEASUREMENT - UPLIFT ANALYSIS")
        print("="*80)

        for result in results:
            print(f"\nIntervention: {result.intervention.upper()}")
            print(f"  Treatment Group: {result.treatment_group_size:,} accounts")
            print(f"  Control Group: {result.control_group_size:,} accounts")
            print(f"  Treatment Outcome: {result.treatment_outcome:.2%}")
            print(f"  Control Outcome: {result.control_outcome:.2%}")
            print(f"  Absolute Uplift: {result.absolute_uplift:+.2%}")
            print(f"  Relative Uplift: {result.relative_uplift:+.1f}%")
            print(f"  P-Value: {result.p_value:.4f} {'✓ Significant' if result.p_value < 0.05 else '✗ Not Significant'}")
            print(f"  95% CI: ({result.confidence_interval[0]:.2%}, {result.confidence_interval[1]:.2%})")
            print(f"  Cost per Treatment: ₹{result.cost_per_treatment:.2f}")
            print(f"  ROI: {result.roi:.1%}")
            print("-" * 80)


def analyze_impact(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    """Main entry point for impact analysis"""
    end_date = end_date or date.today()
    start_date = start_date or (end_date - timedelta(days=30))

    print(f"Analyzing impact from {start_date} to {end_date}")

    analyzer = ImpactAnalyzer()
    results = analyzer.run_all_uplift_analyses(start_date, end_date)

    analyzer.print_uplift_report(results)

    return results


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 2:
        start_date = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
        end_date = datetime.strptime(sys.argv[2], '%Y-%m-%d').date()
    else:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

    analyze_impact(start_date, end_date)
