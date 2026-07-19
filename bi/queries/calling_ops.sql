-- ============================================================================
-- Calling Ops Dashboard
-- Attempts/connects/RPC/PTP by channel, slot heatmaps, bot containment, queue SLAs
-- ============================================================================

-- Query 1: Call Metrics by Channel (Today)
-- Bot vs Telecaller performance
SELECT
    channel,
    COUNT(*) as total_calls,
    SUM(CASE WHEN outcome = 'CONNECTED' THEN 1 ELSE 0 END) as connected,
    SUM(CASE WHEN disposition IN ('CONNECT_RPC') THEN 1 ELSE 0 END) as rpc,
    SUM(CASE WHEN disposition = 'PTP' THEN 1 ELSE 0 END) as ptps,
    ROUND(100.0 * SUM(CASE WHEN outcome = 'CONNECTED' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as connect_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN disposition = 'CONNECT_RPC' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN outcome = 'CONNECTED' THEN 1 ELSE 0 END), 0), 2) as rpc_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN disposition = 'PTP' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN disposition = 'CONNECT_RPC' THEN 1 ELSE 0 END), 0), 2) as ptp_conversion_pct
FROM fct_calls
WHERE call_date = CURRENT_DATE
GROUP BY channel
ORDER BY total_calls DESC;

-- Query 2: Call Volume Trend (Last 30 Days)
-- Daily call attempts and outcomes
SELECT
    call_date,
    COUNT(*) as total_calls,
    SUM(CASE WHEN outcome = 'CONNECTED' THEN 1 ELSE 0 END) as connected,
    SUM(CASE WHEN outcome = 'NO_ANSWER' THEN 1 ELSE 0 END) as no_answer,
    SUM(CASE WHEN outcome = 'SWITCHED_OFF' THEN 1 ELSE 0 END) as switched_off,
    SUM(CASE WHEN disposition = 'PTP' THEN 1 ELSE 0 END) as ptps_made
FROM fct_calls
WHERE call_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY call_date
ORDER BY call_date DESC;

-- Query 3: Slot Heatmap (Hour of Day Performance)
-- When are calls most effective?
SELECT
    EXTRACT(HOUR FROM call_time) as hour,
    COUNT(*) as attempts,
    ROUND(100.0 * SUM(CASE WHEN outcome = 'CONNECTED' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as connect_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN disposition = 'PTP' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN outcome = 'CONNECTED' THEN 1 ELSE 0 END), 0), 2) as ptp_rate_pct
FROM fct_calls
WHERE call_date >= CURRENT_DATE - INTERVAL '7 days'
  AND EXTRACT(HOUR FROM call_time) BETWEEN 8 AND 19
GROUP BY EXTRACT(HOUR FROM call_time)
ORDER BY hour;

-- Query 4: Bot Containment Rate
-- What % of bot calls require human escalation?
SELECT
    call_date,
    COUNT(*) as bot_calls,
    SUM(CASE WHEN disposition IN ('CONNECT_RPC', 'PTP', 'PAID_CLAIM') THEN 1 ELSE 0 END) as resolved_by_bot,
    SUM(CASE WHEN disposition = 'CALLBACK' THEN 1 ELSE 0 END) as escalated_to_human,
    ROUND(100.0 * SUM(CASE WHEN disposition IN ('CONNECT_RPC', 'PTP', 'PAID_CLAIM') THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as containment_pct
FROM fct_calls
WHERE channel = 'BOT'
  AND call_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY call_date
ORDER BY call_date DESC;

-- Query 5: Agent Productivity (Today)
-- Calls per agent, connect rates
SELECT
    c.agent_id,
    a.name as agent_name,
    a.role,
    COUNT(*) as calls_made,
    SUM(CASE WHEN c.outcome = 'CONNECTED' THEN 1 ELSE 0 END) as connects,
    SUM(CASE WHEN c.disposition = 'CONNECT_RPC' THEN 1 ELSE 0 END) as rpcs,
    SUM(CASE WHEN c.disposition = 'PTP' THEN 1 ELSE 0 END) as ptps,
    ROUND(100.0 * SUM(CASE WHEN c.outcome = 'CONNECTED' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as connect_rate_pct
FROM fct_calls c
JOIN dim_agent a ON c.agent_id = a.agent_id
WHERE c.call_date = CURRENT_DATE
  AND c.channel = 'TELECALLER'
GROUP BY c.agent_id, a.name, a.role
HAVING COUNT(*) > 10
ORDER BY calls_made DESC
LIMIT 20;

-- Query 6: PTP Performance
-- PTPs made vs kept
SELECT
    DATE(ptp_date) as date,
    COUNT(*) as ptps_made,
    SUM(CASE WHEN status = 'KEPT' THEN 1 ELSE 0 END) as ptps_kept,
    SUM(CASE WHEN status = 'BROKEN' THEN 1 ELSE 0 END) as ptps_broken,
    SUM(CASE WHEN status = 'PARTIAL' THEN 1 ELSE 0 END) as ptps_partial,
    ROUND(100.0 * SUM(CASE WHEN status = 'KEPT' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as kept_rate_pct
FROM fct_ptp
WHERE ptp_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(ptp_date)
ORDER BY date DESC;

-- Query 7: Disposition Distribution (Last 7 Days)
-- What are the common call outcomes?
SELECT
    disposition,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct
FROM fct_calls
WHERE call_date >= CURRENT_DATE - INTERVAL '7 days'
  AND disposition IS NOT NULL
GROUP BY disposition
ORDER BY count DESC;

-- Query 8: Queue SLA (Today)
-- Are we calling accounts within SLA windows?
WITH queue_stats AS (
    SELECT
        q.account_id,
        q.scheduled_time,
        MIN(c.call_time) as first_attempt_time,
        EXTRACT(EPOCH FROM (MIN(c.call_time) - q.scheduled_time)) / 3600 as hours_to_first_attempt
    FROM call_queue q
    LEFT JOIN fct_calls c ON q.account_id = c.account_id
        AND DATE(c.call_date) = DATE(q.scheduled_time)
    WHERE DATE(q.scheduled_time) = CURRENT_DATE
    GROUP BY q.account_id, q.scheduled_time
)
SELECT
    COUNT(*) as queued_accounts,
    SUM(CASE WHEN first_attempt_time IS NOT NULL THEN 1 ELSE 0 END) as attempted,
    SUM(CASE WHEN hours_to_first_attempt <= 2 THEN 1 ELSE 0 END) as within_2h_sla,
    ROUND(100.0 * SUM(CASE WHEN first_attempt_time IS NOT NULL THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as attempt_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN hours_to_first_attempt <= 2 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as sla_compliance_pct
FROM queue_stats;
