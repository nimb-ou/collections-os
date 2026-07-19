-- ============================================================================
-- Portfolio Command Dashboard
-- Demand, bounce%, resolution% by bucket/product/zone, flows, roll matrix
-- ============================================================================

-- Query 1: Portfolio Summary (Latest)
-- Shows current portfolio status by bucket
SELECT
    bucket,
    COUNT(DISTINCT account_id) as account_count,
    SUM(overdue_amt) as total_overdue,
    SUM(pos) as total_pos,
    AVG(dpd) as avg_dpd,
    AVG(bounce_p) as avg_bounce_risk
FROM mart_account_daily
WHERE date = (SELECT MAX(date) FROM mart_account_daily)
GROUP BY bucket
ORDER BY
    CASE bucket
        WHEN 'PRE_DUE' THEN 1
        WHEN 'X' THEN 2
        WHEN 'B1' THEN 3
        WHEN 'B2' THEN 4
        WHEN 'B3' THEN 5
        WHEN 'NPA_90' THEN 6
        WHEN 'NPA_120' THEN 7
        WHEN 'NPA_150' THEN 8
        WHEN 'NPA_180+' THEN 9
    END;

-- Query 2: Bounce Rate Trend (Last 30 days)
-- Daily bounce rate tracking
SELECT
    p.present_date::date as date,
    COUNT(*) as presentations,
    SUM(CASE WHEN p.status = 'B' THEN 1 ELSE 0 END) as bounces,
    ROUND(100.0 * SUM(CASE WHEN p.status = 'B' THEN 1 ELSE 0 END) / COUNT(*), 2) as bounce_rate_pct
FROM fct_presentations p
WHERE p.present_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY p.present_date::date
ORDER BY date DESC;

-- Query 3: Resolution Rate by Bucket (Month-to-Date)
-- What % of accounts in each bucket have cleared dues
SELECT
    bucket,
    COUNT(DISTINCT account_id) as accounts,
    SUM(CASE WHEN overdue_amt = 0 THEN 1 ELSE 0 END) as resolved,
    ROUND(100.0 * SUM(CASE WHEN overdue_amt = 0 THEN 1 ELSE 0 END) / COUNT(DISTINCT account_id), 2) as resolution_pct
FROM mart_account_daily
WHERE date = (SELECT MAX(date) FROM mart_account_daily)
  AND bucket IN ('X', 'B1', 'B2', 'B3')
GROUP BY bucket
ORDER BY bucket;

-- Query 4: Collection Efficiency (Month-to-Date)
-- Amount collected vs amount due
SELECT
    DATE_TRUNC('month', pay_date) as month,
    SUM(amount) as collected,
    (SELECT SUM(emi_amt * COUNT(DISTINCT account_id))
     FROM mart_account_daily
     WHERE DATE_TRUNC('month', date) = DATE_TRUNC('month', p.pay_date)
       AND date = DATE_TRUNC('month', date)
    ) as demanded,
    ROUND(100.0 * SUM(amount) / NULLIF((SELECT SUM(emi_amt)
                                         FROM mart_account_daily
                                         WHERE DATE_TRUNC('month', date) = DATE_TRUNC('month', p.pay_date)
                                         LIMIT 1), 0), 2) as efficiency_pct
FROM fct_payments p
WHERE pay_date >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY DATE_TRUNC('month', pay_date)
ORDER BY month DESC;

-- Query 5: Portfolio by Product Type
-- Product mix and performance
SELECT
    a.product_type,
    COUNT(DISTINCT m.account_id) as accounts,
    SUM(m.overdue_amt) as total_overdue,
    SUM(m.pos) as total_pos,
    ROUND(AVG(m.dpd), 1) as avg_dpd,
    ROUND(100.0 * SUM(CASE WHEN m.overdue_amt > 0 THEN 1 ELSE 0 END) / COUNT(DISTINCT m.account_id), 2) as delinquency_pct
FROM mart_account_daily m
JOIN dim_account a ON m.account_id = a.account_id
WHERE m.date = (SELECT MAX(date) FROM mart_account_daily)
GROUP BY a.product_type
ORDER BY accounts DESC;

-- Query 6: Portfolio by Zone
-- Geographic distribution and performance
SELECT
    g.zone,
    COUNT(DISTINCT m.account_id) as accounts,
    SUM(m.overdue_amt) as total_overdue,
    ROUND(AVG(m.dpd), 1) as avg_dpd,
    ROUND(100.0 * SUM(CASE WHEN m.bucket IN ('B1', 'B2', 'B3') THEN 1 ELSE 0 END) / COUNT(DISTINCT m.account_id), 2) as early_bucket_pct
FROM mart_account_daily m
JOIN dim_account a ON m.account_id = a.account_id
JOIN dim_geo g ON a.geo_id = g.geo_id
WHERE m.date = (SELECT MAX(date) FROM mart_account_daily)
GROUP BY g.zone
ORDER BY accounts DESC;

-- Query 7: Roll Matrix (Last Month)
-- Bucket transitions (flow X→1, stabilization, roll-forward, roll-back)
WITH month_start AS (
    SELECT
        account_id,
        bucket as start_bucket
    FROM mart_account_daily
    WHERE date = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
),
month_end AS (
    SELECT
        account_id,
        bucket as end_bucket
    FROM mart_account_daily
    WHERE date = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') + INTERVAL '1 month' - INTERVAL '1 day'
)
SELECT
    ms.start_bucket,
    me.end_bucket,
    COUNT(*) as account_count,
    CASE
        WHEN ms.start_bucket = me.end_bucket THEN 'Stabilized'
        WHEN ms.start_bucket = 'X' AND me.end_bucket = 'B1' THEN 'Flow X→1'
        WHEN ms.start_bucket < me.end_bucket THEN 'Roll Forward'
        WHEN ms.start_bucket > me.end_bucket THEN 'Roll Back'
    END as flow_type
FROM month_start ms
JOIN month_end me ON ms.account_id = me.account_id
GROUP BY ms.start_bucket, me.end_bucket
ORDER BY ms.start_bucket, me.end_bucket;

-- Query 8: NPA Movement Trend
-- 90+ DPD accounts over time
SELECT
    date,
    COUNT(DISTINCT account_id) as npa_accounts,
    SUM(overdue_amt) as npa_amount
FROM mart_account_daily
WHERE bucket IN ('NPA_90', 'NPA_120', 'NPA_150', 'NPA_180+')
  AND date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY date
ORDER BY date;
