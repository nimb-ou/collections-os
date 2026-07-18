{{
    config(
        materialized='table'
    )
}}

-- Monthly portfolio summary
-- Aggregates presentations, bounces, payments by month

WITH presentations AS (
    SELECT
        DATE_TRUNC('month', present_date) as month,
        COUNT(*) as total_presentations,
        SUM(CASE WHEN status = 'B' THEN 1 ELSE 0 END) as total_bounces,
        SUM(CASE WHEN status = 'S' THEN 1 ELSE 0 END) as total_successes,
        SUM(amount) as total_presented_amount
    FROM {{ ref('stg_presentations') }}
    GROUP BY 1
),

payments AS (
    SELECT
        DATE_TRUNC('month', pay_date) as month,
        COUNT(*) as total_payments,
        SUM(amount) as total_paid_amount,
        SUM(is_field_collection) as field_collections
    FROM {{ ref('stg_payments') }}
    GROUP BY 1
)

SELECT
    COALESCE(p.month, pay.month) as month,
    COALESCE(p.total_presentations, 0) as total_presentations,
    COALESCE(p.total_bounces, 0) as total_bounces,
    COALESCE(p.total_successes, 0) as total_successes,
    COALESCE(p.total_presented_amount, 0) as total_presented_amount,
    COALESCE(pay.total_payments, 0) as total_payments,
    COALESCE(pay.total_paid_amount, 0) as total_paid_amount,
    COALESCE(pay.field_collections, 0) as field_collections,

    -- Derived metrics
    CASE
        WHEN p.total_presentations > 0
        THEN ROUND(p.total_bounces::NUMERIC / p.total_presentations * 100, 2)
        ELSE 0
    END as bounce_rate_pct,

    CASE
        WHEN p.total_presentations > 0
        THEN ROUND(pay.total_payments::NUMERIC / p.total_presentations * 100, 2)
        ELSE 0
    END as payment_rate_pct

FROM presentations p
FULL OUTER JOIN payments pay ON p.month = pay.month
ORDER BY month DESC
