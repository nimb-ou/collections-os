"""
Feature engineering for ML models.
Builds feature matrices from mart_account_daily and fact tables.
"""

import pandas as pd
import psycopg2
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from .config import DB_CONFIG


class FeatureEngineer:
    """
    Builds feature matrices for ML models from PostgreSQL data.
    """

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()

    def build_bounce_features(
        self,
        as_of_date: str,
        lookback_months: int = 24
    ) -> pd.DataFrame:
        """
        Build features for bounce prediction model.

        Args:
            as_of_date: Date to build features as of (YYYY-MM-DD)
            lookback_months: Months of history to use

        Returns:
            DataFrame with features and target (bounce in next presentation)
        """
        query = f"""
        WITH account_history AS (
            SELECT
                mad.account_id,
                mad.date,
                mad.dpd,
                mad.bucket,
                mad.overdue_amt,
                mad.pos,
                mad.emi_amt,
                mad.cycle_day,
                a.product_type,
                a.disbursal_amt,
                a.roi,
                a.tenure_m,
                a.state,
                a.disbursal_date,
                -- Calculate vintage
                EXTRACT(YEAR FROM AGE(mad.date, a.disbursal_date)) * 12 +
                EXTRACT(MONTH FROM AGE(mad.date, a.disbursal_date)) as vintage_months
            FROM mart_account_daily mad
            JOIN dim_account a ON mad.account_id = a.account_id
            WHERE mad.date BETWEEN DATE '{as_of_date}' - INTERVAL '{lookback_months} months'
                  AND DATE '{as_of_date}'
        ),

        bounce_history AS (
            SELECT
                account_id,
                COUNT(*) FILTER (WHERE status = 'B' AND present_date >= DATE '{as_of_date}' - INTERVAL '3 months') as bounces_3m,
                COUNT(*) FILTER (WHERE status = 'B' AND present_date >= DATE '{as_of_date}' - INTERVAL '6 months') as bounces_6m,
                COUNT(*) FILTER (WHERE status = 'B' AND present_date >= DATE '{as_of_date}' - INTERVAL '12 months') as bounces_12m,
                COUNT(*) FILTER (WHERE present_date >= DATE '{as_of_date}' - INTERVAL '3 months') as presentations_3m,
                COUNT(*) FILTER (WHERE present_date >= DATE '{as_of_date}' - INTERVAL '6 months') as presentations_6m,
                COUNT(*) FILTER (WHERE present_date >= DATE '{as_of_date}' - INTERVAL '12 months') as presentations_12m
            FROM fct_presentations
            WHERE present_date <= DATE '{as_of_date}'
            GROUP BY account_id
        ),

        payment_stats AS (
            SELECT
                account_id,
                COUNT(*) as payment_count_6m,
                AVG(amount) as avg_payment_amt,
                STDDEV(amount) / NULLIF(AVG(amount), 0) as payment_cv
            FROM fct_payments
            WHERE pay_date >= DATE '{as_of_date}' - INTERVAL '6 months'
              AND pay_date <= DATE '{as_of_date}'
            GROUP BY account_id
        ),

        latest_state AS (
            SELECT DISTINCT ON (account_id)
                account_id,
                dpd as current_dpd,
                bucket as current_bucket,
                overdue_amt,
                pos,
                emi_amt,
                cycle_day,
                product_type,
                disbursal_amt,
                roi,
                tenure_m,
                state,
                vintage_months
            FROM account_history
            WHERE date = DATE '{as_of_date}'
            ORDER BY account_id, date DESC
        ),

        -- Target: Did account bounce in next presentation after as_of_date?
        next_presentation AS (
            SELECT
                account_id,
                CASE WHEN status = 'B' THEN 1 ELSE 0 END as target_bounce
            FROM (
                SELECT
                    account_id,
                    status,
                    ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY present_date ASC) as rn
                FROM fct_presentations
                WHERE present_date > DATE '{as_of_date}'
            ) sub
            WHERE rn = 1
        )

        SELECT
            ls.account_id,
            -- Current state features
            ls.current_dpd,
            ls.current_bucket::text as current_bucket,
            ls.overdue_amt,
            ls.pos,
            ls.emi_amt,
            ls.cycle_day,

            -- Account characteristics
            ls.product_type,
            ls.disbursal_amt,
            ls.roi,
            ls.tenure_m,
            ls.state,
            ls.vintage_months,

            -- Bounce history features
            COALESCE(bh.bounces_3m, 0) as bounces_3m,
            COALESCE(bh.bounces_6m, 0) as bounces_6m,
            COALESCE(bh.bounces_12m, 0) as bounces_12m,
            COALESCE(bh.presentations_3m, 0) as presentations_3m,
            COALESCE(bh.presentations_6m, 0) as presentations_6m,
            COALESCE(bh.presentations_12m, 0) as presentations_12m,

            -- Derived bounce rates
            CASE WHEN bh.presentations_3m > 0 THEN bh.bounces_3m::float / bh.presentations_3m ELSE 0 END as bounce_rate_3m,
            CASE WHEN bh.presentations_6m > 0 THEN bh.bounces_6m::float / bh.presentations_6m ELSE 0 END as bounce_rate_6m,
            CASE WHEN bh.presentations_12m > 0 THEN bh.bounces_12m::float / bh.presentations_12m ELSE 0 END as bounce_rate_12m,

            -- Payment features
            COALESCE(ps.payment_count_6m, 0) as payment_count_6m,
            COALESCE(ps.avg_payment_amt, 0) as avg_payment_amt,
            COALESCE(ps.payment_cv, 0) as payment_cv,

            -- Seasonality
            EXTRACT(MONTH FROM DATE '{as_of_date}') as seasonality_month,

            -- Target
            COALESCE(np.target_bounce, 0) as target

        FROM latest_state ls
        LEFT JOIN bounce_history bh ON ls.account_id = bh.account_id
        LEFT JOIN payment_stats ps ON ls.account_id = ps.account_id
        LEFT JOIN next_presentation np ON ls.account_id = np.account_id
        WHERE np.target_bounce IS NOT NULL  -- Only include accounts with a next presentation
        """

        df = pd.read_sql(query, self.conn)
        return df

    def build_selfcure_features(
        self,
        as_of_date: str,
        lookback_months: int = 12
    ) -> pd.DataFrame:
        """
        Build features for self-cure prediction (simplified version).
        Target: Did customer pay within 7 days after bounce without any contact?
        """
        query = f"""
        WITH recent_bounces AS (
            SELECT
                p.account_id,
                p.present_date as bounce_date,
                p.amount as bounce_amount,
                p.bounce_reason
            FROM fct_presentations p
            WHERE p.status = 'B'
              AND p.present_date BETWEEN DATE '{as_of_date}' - INTERVAL '1 month' AND DATE '{as_of_date}'
        ),

        cure_outcome AS (
            SELECT
                rb.account_id,
                rb.bounce_date,
                -- Check if payment within 7 days with no contact
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM fct_payments pay
                        WHERE pay.account_id = rb.account_id
                          AND pay.pay_date BETWEEN rb.bounce_date AND rb.bounce_date + INTERVAL '7 days'
                          AND pay.collected_by IS NULL  -- Self-cure (not field collection)
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM fct_calls c
                        WHERE c.account_id = rb.account_id
                          AND c.call_start_time BETWEEN rb.bounce_date AND rb.bounce_date + INTERVAL '7 days'
                    )
                    THEN 1
                    ELSE 0
                END as target_selfcure
            FROM recent_bounces rb
        ),

        account_features AS (
            SELECT DISTINCT ON (account_id)
                account_id,
                dpd as current_dpd,
                overdue_amt,
                pos,
                emi_amt
            FROM mart_account_daily
            WHERE date = DATE '{as_of_date}'
            ORDER BY account_id, date DESC
        )

        SELECT
            co.account_id,
            af.current_dpd,
            af.overdue_amt,
            af.pos,
            af.emi_amt,
            co.target_selfcure as target
        FROM cure_outcome co
        LEFT JOIN account_features af ON co.account_id = af.account_id
        WHERE af.account_id IS NOT NULL
        """

        df = pd.read_sql(query, self.conn)
        return df

    def close(self):
        """Close database connection."""
        self.conn.close()
