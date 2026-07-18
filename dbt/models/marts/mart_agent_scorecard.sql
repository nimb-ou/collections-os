{{
    config(
        materialized='table'
    )
}}

-- Agent performance scorecard by month
-- Individual agent metrics for call activity, contact rates, field collections

WITH agent_calls AS (
    SELECT
        agent_id,
        DATE_TRUNC('month', call_date) as month,
        COUNT(*) as total_calls,
        SUM(is_connected) as connected_calls,
        SUM(is_ptp_call) as ptp_calls,
        AVG(duration_sec) as avg_call_duration_sec
    FROM {{ ref('stg_calls') }}
    WHERE agent_id IS NOT NULL
    GROUP BY 1, 2
),

agent_visits AS (
    SELECT
        agent_id,
        DATE_TRUNC('month', visit_date) as month,
        COUNT(*) as total_visits,
        SUM(is_customer_met) as customers_met,
        SUM(has_payment) as visits_with_payment,
        SUM(amount_collected) as total_collected_amount
    FROM {{ ref('stg_visits') }}
    GROUP BY 1, 2
),

agent_field_payments AS (
    SELECT
        collected_by as agent_id,
        DATE_TRUNC('month', pay_date) as month,
        COUNT(*) as field_payment_count,
        SUM(amount) as field_payment_amount
    FROM {{ ref('stg_payments') }}
    WHERE collected_by IS NOT NULL
    GROUP BY 1, 2
)

SELECT
    COALESCE(c.agent_id, v.agent_id, p.agent_id) as agent_id,
    COALESCE(c.month, v.month, p.month) as month,

    -- Call metrics
    COALESCE(c.total_calls, 0) as total_calls,
    COALESCE(c.connected_calls, 0) as connected_calls,
    COALESCE(c.ptp_calls, 0) as ptp_calls,
    COALESCE(c.avg_call_duration_sec, 0) as avg_call_duration_sec,

    -- Visit metrics
    COALESCE(v.total_visits, 0) as total_visits,
    COALESCE(v.customers_met, 0) as customers_met,
    COALESCE(v.visits_with_payment, 0) as visits_with_payment,
    COALESCE(v.total_collected_amount, 0) as visit_collected_amount,

    -- Field payment metrics
    COALESCE(p.field_payment_count, 0) as field_payment_count,
    COALESCE(p.field_payment_amount, 0) as field_payment_amount,

    -- Performance rates
    CASE
        WHEN c.total_calls > 0
        THEN ROUND(c.connected_calls::NUMERIC / c.total_calls * 100, 2)
        ELSE 0
    END as contact_rate_pct,

    CASE
        WHEN c.connected_calls > 0
        THEN ROUND(c.ptp_calls::NUMERIC / c.connected_calls * 100, 2)
        ELSE 0
    END as ptp_conversion_rate_pct,

    CASE
        WHEN v.total_visits > 0
        THEN ROUND(v.customers_met::NUMERIC / v.total_visits * 100, 2)
        ELSE 0
    END as customer_met_rate_pct,

    CASE
        WHEN v.total_visits > 0
        THEN ROUND(v.visits_with_payment::NUMERIC / v.total_visits * 100, 2)
        ELSE 0
    END as collection_success_rate_pct,

    -- Total productivity score (simple weighted average for now)
    -- This will be enhanced with difficulty index in later sessions
    ROUND(
        (COALESCE(c.total_calls, 0) * 1.0 +
         COALESCE(v.total_visits, 0) * 3.0 +
         COALESCE(v.visits_with_payment, 0) * 10.0) /
        NULLIF((COALESCE(c.total_calls, 0) + COALESCE(v.total_visits, 0) + COALESCE(v.visits_with_payment, 0)), 0),
        2
    ) as productivity_score

FROM agent_calls c
FULL OUTER JOIN agent_visits v
    ON c.agent_id = v.agent_id AND c.month = v.month
FULL OUTER JOIN agent_field_payments p
    ON COALESCE(c.agent_id, v.agent_id) = p.agent_id
    AND COALESCE(c.month, v.month) = p.month
WHERE COALESCE(c.agent_id, v.agent_id, p.agent_id) IS NOT NULL
ORDER BY month DESC, agent_id
