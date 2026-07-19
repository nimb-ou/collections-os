-- ============================================================================
-- Field Ops Dashboard
-- Visits, strike rate, collections by mode, beat adherence, geo heatmap
-- ============================================================================

-- Query 1: Field Visit Summary (Today)
-- Visit outcomes and effectiveness
SELECT
    outcome,
    COUNT(*) as visits,
    SUM(collected_amt) as total_collected,
    ROUND(AVG(collected_amt), 2) as avg_collected,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct_of_visits
FROM fct_visits
WHERE visit_date = CURRENT_DATE
GROUP BY outcome
ORDER BY visits DESC;

-- Query 2: Strike Rate Trend (Last 30 Days)
-- What % of visits result in collection or PTP?
SELECT
    visit_date,
    COUNT(*) as total_visits,
    SUM(CASE WHEN outcome IN ('MET', 'COLLECTED') THEN 1 ELSE 0 END) as productive_visits,
    SUM(CASE WHEN collected_amt > 0 THEN 1 ELSE 0 END) as visits_with_collection,
    SUM(collected_amt) as total_collected,
    ROUND(100.0 * SUM(CASE WHEN outcome IN ('MET', 'COLLECTED') THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as strike_rate_pct
FROM fct_visits
WHERE visit_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY visit_date
ORDER BY visit_date DESC;

-- Query 3: Collections by Payment Mode
-- How are customers paying?
SELECT
    pay_mode,
    COUNT(*) as payments,
    SUM(amount) as total_amount,
    ROUND(AVG(amount), 2) as avg_amount,
    ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 2) as pct_of_total_amount
FROM fct_payments
WHERE pay_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY pay_mode
ORDER BY total_amount DESC;

-- Query 4: Field Agent Productivity (Today)
-- Visits per agent, collection effectiveness
SELECT
    v.agent_id,
    a.name as agent_name,
    COUNT(*) as visits_completed,
    SUM(CASE WHEN v.outcome = 'MET' THEN 1 ELSE 0 END) as customer_met,
    SUM(CASE WHEN v.outcome = 'NOT_FOUND' THEN 1 ELSE 0 END) as not_found,
    SUM(v.collected_amt) as total_collected,
    ROUND(AVG(v.collected_amt), 2) as avg_per_visit,
    ROUND(100.0 * SUM(CASE WHEN v.outcome = 'MET' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as meet_rate_pct
FROM fct_visits v
JOIN dim_agent a ON v.agent_id = a.agent_id
WHERE v.visit_date = CURRENT_DATE
GROUP BY v.agent_id, a.name
HAVING COUNT(*) > 0
ORDER BY visits_completed DESC
LIMIT 20;

-- Query 5: Beat Plan Adherence
-- Are agents following their assigned beat plans?
SELECT
    DATE(bp.beat_date) as date,
    COUNT(DISTINCT bp.agent_id) as agents_with_beats,
    COUNT(*) as planned_stops,
    SUM(CASE WHEN bp.completed THEN 1 ELSE 0 END) as completed_stops,
    ROUND(100.0 * SUM(CASE WHEN bp.completed THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as completion_pct
FROM beat_plan bp
WHERE bp.beat_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(bp.beat_date)
ORDER BY date DESC;

-- Query 6: Geographic Heatmap (Collections by Zone)
-- Which zones are performing well?
SELECT
    g.zone,
    g.state,
    COUNT(DISTINCT v.visit_id) as visits,
    SUM(v.collected_amt) as total_collected,
    COUNT(DISTINCT v.account_id) as unique_accounts_visited,
    ROUND(AVG(v.collected_amt), 2) as avg_per_visit,
    ROUND(100.0 * SUM(CASE WHEN v.outcome = 'MET' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as meet_rate_pct
FROM fct_visits v
JOIN dim_account a ON v.account_id = a.account_id
JOIN dim_geo g ON a.geo_id = g.geo_id
WHERE v.visit_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY g.zone, g.state
ORDER BY total_collected DESC;

-- Query 7: Visit Disposition Breakdown
-- Detailed visit outcomes
SELECT
    disposition,
    COUNT(*) as count,
    SUM(collected_amt) as total_collected,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct
FROM fct_visits
WHERE visit_date >= CURRENT_DATE - INTERVAL '7 days'
  AND disposition IS NOT NULL
GROUP BY disposition
ORDER BY count DESC;

-- Query 8: Field Collections vs Expectations
-- Comparing actual collections against beat plan expectations
SELECT
    DATE(v.visit_date) as date,
    COUNT(DISTINCT v.visit_id) as actual_visits,
    SUM(v.collected_amt) as actual_collected,
    (SELECT SUM(bp.expected_collection)
     FROM beat_plan bp
     WHERE DATE(bp.beat_date) = DATE(v.visit_date)
       AND bp.completed = true
    ) as expected_collected,
    ROUND(100.0 * SUM(v.collected_amt) / NULLIF((SELECT SUM(bp.expected_collection)
                                                   FROM beat_plan bp
                                                   WHERE DATE(bp.beat_date) = DATE(v.visit_date)
                                                     AND bp.completed = true), 0), 2) as achievement_pct
FROM fct_visits v
WHERE v.visit_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(v.visit_date)
ORDER BY date DESC;

-- Query 9: Top Performing Field Agents (Last 30 Days)
-- Leaderboard by collections
SELECT
    v.agent_id,
    a.name as agent_name,
    a.team_id,
    COUNT(*) as visits,
    SUM(v.collected_amt) as total_collected,
    ROUND(AVG(v.collected_amt), 2) as avg_per_visit,
    ROUND(100.0 * SUM(CASE WHEN v.outcome = 'MET' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as meet_rate_pct,
    RANK() OVER (ORDER BY SUM(v.collected_amt) DESC) as rank
FROM fct_visits v
JOIN dim_agent a ON v.agent_id = a.agent_id
WHERE v.visit_date >= CURRENT_DATE - INTERVAL '30 days'
  AND a.role = 'FOS'
GROUP BY v.agent_id, a.name, a.team_id
HAVING COUNT(*) >= 10
ORDER BY total_collected DESC
LIMIT 20;
