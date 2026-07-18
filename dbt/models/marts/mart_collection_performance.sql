{{
    config(
        materialized='table'
    )
}}

-- Collection performance metrics by month
-- Aggregates call activity, contact rates, field activity

WITH monthly_calls AS (
    SELECT
        DATE_TRUNC('month', call_date) as month,
        COUNT(*) as total_calls,
        SUM(is_bot_call) as bot_calls,
        SUM(is_human_call) as human_calls,
        SUM(is_connected) as connected_calls,
        SUM(is_ptp_call) as ptp_calls,
        AVG(duration_sec) as avg_call_duration_sec
    FROM {{ ref('stg_calls') }}
    GROUP BY 1
),

monthly_visits AS (
    SELECT
        DATE_TRUNC('month', visit_date) as month,
        COUNT(*) as total_visits,
        SUM(is_customer_met) as customers_met,
        SUM(has_payment) as visits_with_payment,
        SUM(amount_collected) as total_field_collection_amount
    FROM {{ ref('stg_visits') }}
    GROUP BY 1
),

monthly_payments AS (
    SELECT
        DATE_TRUNC('month', pay_date) as month,
        COUNT(*) as total_payments,
        SUM(amount) as total_payment_amount,
        SUM(is_field_collection) as field_collection_payments
    FROM {{ ref('stg_payments') }}
    GROUP BY 1
)

SELECT
    COALESCE(c.month, v.month, p.month) as month,

    -- Call metrics
    COALESCE(c.total_calls, 0) as total_calls,
    COALESCE(c.bot_calls, 0) as bot_calls,
    COALESCE(c.human_calls, 0) as human_calls,
    COALESCE(c.connected_calls, 0) as connected_calls,
    COALESCE(c.ptp_calls, 0) as ptp_calls,
    COALESCE(c.avg_call_duration_sec, 0) as avg_call_duration_sec,

    -- Visit metrics
    COALESCE(v.total_visits, 0) as total_visits,
    COALESCE(v.customers_met, 0) as customers_met,
    COALESCE(v.visits_with_payment, 0) as visits_with_payment,
    COALESCE(v.total_field_collection_amount, 0) as total_field_collection_amount,

    -- Payment metrics
    COALESCE(p.total_payments, 0) as total_payments,
    COALESCE(p.total_payment_amount, 0) as total_payment_amount,
    COALESCE(p.field_collection_payments, 0) as field_collection_payments,

    -- Derived rates
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
    END as field_collection_rate_pct

FROM monthly_calls c
FULL OUTER JOIN monthly_visits v ON c.month = v.month
FULL OUTER JOIN monthly_payments p ON COALESCE(c.month, v.month) = p.month
ORDER BY month DESC
