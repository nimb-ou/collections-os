-- Migration 009: Views and Helper Functions
-- Analytical views and utility functions
-- Created: 2026-07-19

-- View: Current agent roster (active agents with latest SCD record)
CREATE OR REPLACE VIEW v_agent_roster AS
SELECT
    a.agent_id,
    a.name,
    a.role,
    a.team_id,
    t.team_name,
    t.zone,
    a.supervisor_id,
    a.base_pincode,
    g.city as base_city,
    g.state as base_state,
    a.langs,
    a.capacity_override,
    a.active,
    a.valid_from
FROM dim_agent a
LEFT JOIN dim_team t ON a.team_id = t.team_id
LEFT JOIN dim_geo g ON a.base_geo_id = g.geo_id
WHERE a.valid_to = '9999-12-31'::timestamp
  AND a.active = true;

-- View: Account summary with customer info
CREATE OR REPLACE VIEW v_account_summary AS
SELECT
    a.account_id,
    a.customer_id,
    c.name as customer_name,
    c.lang_pref,
    a.product_type,
    a.disbursal_date,
    a.disbursal_amt,
    a.tenure_m,
    a.emi_amt,
    a.cycle_day,
    a.status,
    g.city,
    g.state,
    g.zone,
    -- Latest DPD
    (SELECT dpd FROM mart_account_daily m WHERE m.account_id = a.account_id ORDER BY date DESC LIMIT 1) as current_dpd,
    (SELECT bucket FROM mart_account_daily m WHERE m.account_id = a.account_id ORDER BY date DESC LIMIT 1) as current_bucket,
    -- Primary contact
    (SELECT phone FROM dim_customer_contacts cc WHERE cc.customer_id = a.customer_id AND cc.is_primary = true LIMIT 1) as primary_phone
FROM dim_account a
JOIN dim_customer c ON a.customer_id = c.customer_id
LEFT JOIN dim_geo g ON a.geo_id = g.geo_id
WHERE a.status = 'ACTIVE';

-- View: PTP Book (open and upcoming PTPs)
CREATE OR REPLACE VIEW v_ptp_book AS
SELECT
    p.ptp_id,
    p.account_id,
    vs.customer_name,
    vs.product_type,
    vs.current_bucket,
    p.promise_date,
    p.promise_amount,
    p.payment_mode,
    p.status,
    p.made_by,
    a.name as maker_name,
    p.channel,
    p.created_at as ptp_created_at,
    CASE
        WHEN p.promise_date = CURRENT_DATE THEN 'DUE_TODAY'
        WHEN p.promise_date < CURRENT_DATE THEN 'OVERDUE'
        WHEN p.promise_date = CURRENT_DATE + 1 THEN 'DUE_TOMORROW'
        ELSE 'FUTURE'
    END as urgency
FROM fct_ptp p
JOIN v_account_summary vs ON p.account_id = vs.account_id
LEFT JOIN v_agent_roster a ON p.made_by = a.agent_id
WHERE p.status = 'OPEN'
ORDER BY p.promise_date;

-- View: Daily campaign performance
CREATE OR REPLACE VIEW v_campaign_performance AS
SELECT
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,
    c.channel,
    DATE(ca.added_at) as campaign_date,
    COUNT(DISTINCT ca.account_id) as targeted_accounts,
    COUNT(DISTINCT CASE WHEN ca.is_control_group THEN ca.account_id END) as control_accounts,
    COUNT(DISTINCT CASE WHEN NOT ca.is_control_group THEN ca.account_id END) as treatment_accounts,
    -- Calls made
    COUNT(DISTINCT fc.call_id) as calls_made,
    COUNT(DISTINCT CASE WHEN fc.outcome = 'CONNECTED' THEN fc.call_id END) as calls_connected,
    -- PTPs
    COUNT(DISTINCT p.ptp_id) as ptps_made,
    SUM(CASE WHEN p.status = 'KEPT' THEN p.kept_amount ELSE 0 END) as ptp_amount_kept
FROM campaigns c
JOIN campaign_targets ca ON c.campaign_id = ca.campaign_id
LEFT JOIN fct_calls fc ON ca.account_id = fc.account_id AND DATE(fc.call_start_time) = DATE(ca.added_at)
LEFT JOIN fct_ptp p ON fc.call_id = p.call_id
GROUP BY c.campaign_id, c.campaign_name, c.campaign_type, c.channel, DATE(ca.added_at);

-- Function: Calculate working days between two dates (excluding weekends and Indian holidays)
CREATE OR REPLACE FUNCTION working_days_between(start_date DATE, end_date DATE)
RETURNS INTEGER AS $$
DECLARE
    days INTEGER := 0;
    current_date DATE := start_date;
BEGIN
    WHILE current_date <= end_date LOOP
        -- Count only weekdays (Mon-Sat, excluding Sunday)
        IF EXTRACT(DOW FROM current_date) <> 0 THEN
            days := days + 1;
        END IF;
        current_date := current_date + 1;
    END LOOP;
    RETURN days;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function: Get customer insight card (for collector UIs)
CREATE OR REPLACE FUNCTION get_customer_insight_card(p_account_id VARCHAR)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'account_id', m.account_id,
        'customer_name', c.name,
        'product_type', a.product_type,
        'dpd', m.dpd,
        'bucket', m.bucket,
        'overdue_amt', m.overdue_amt,
        'emi_amt', m.emi_amt,
        'bounce_prob', m.bounce_p,
        'selfcure_prob', m.selfcure_p,
        'has_open_ptp', m.has_open_ptp,
        'last_contact_date', m.last_contact_date,
        'last_payment_date', m.last_payment_date,
        'primary_phone', (SELECT phone FROM dim_customer_contacts WHERE customer_id = a.customer_id AND is_primary = true LIMIT 1),
        'lang_pref', c.lang_pref,
        'treatment', m.treatment_code,
        'next_action', m.next_action,
        'owner', m.owner_agent_id
    )
    INTO result
    FROM mart_account_daily m
    JOIN dim_account a ON m.account_id = a.account_id
    JOIN dim_customer c ON a.customer_id = c.customer_id
    WHERE m.account_id = p_account_id
      AND m.date = CURRENT_DATE;

    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Function: Calculate portfolio resolution rate (for a bucket and date range)
CREATE OR REPLACE FUNCTION calculate_resolution_rate(
    p_bucket bucket_type,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS DECIMAL AS $$
DECLARE
    demand_count INTEGER;
    resolved_count INTEGER;
BEGIN
    -- Accounts in bucket at start
    SELECT COUNT(DISTINCT account_id)
    INTO demand_count
    FROM mart_account_daily
    WHERE date = p_start_date
      AND bucket = p_bucket;

    IF demand_count = 0 THEN
        RETURN 0;
    END IF;

    -- Accounts that moved to current or closed
    SELECT COUNT(DISTINCT m1.account_id)
    INTO resolved_count
    FROM mart_account_daily m1
    WHERE m1.date = p_start_date
      AND m1.bucket = p_bucket
      AND EXISTS (
          SELECT 1
          FROM mart_account_daily m2
          WHERE m2.account_id = m1.account_id
            AND m2.date = p_end_date
            AND m2.dpd = 0
      );

    RETURN ROUND((resolved_count::DECIMAL / demand_count) * 100, 2);
END;
$$ LANGUAGE plpgsql;

-- Function: Validate contact hours (for queue builder)
CREATE OR REPLACE FUNCTION is_valid_contact_time(check_time TIMESTAMP)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXTRACT(HOUR FROM check_time) >= 8
       AND EXTRACT(HOUR FROM check_time) < 19;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON VIEW v_agent_roster IS 'Current active agent roster with team and geography';
COMMENT ON VIEW v_account_summary IS 'Account summary with customer details and current DPD/bucket';
COMMENT ON VIEW v_ptp_book IS 'Open PTPs with urgency classification';
COMMENT ON FUNCTION get_customer_insight_card IS 'Get complete customer context for collector screens';
