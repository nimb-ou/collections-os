{{
    config(
        materialized='view'
    )
}}

-- Staging model for collection calls
-- Source: fct_calls

SELECT
    call_id,
    account_id,
    customer_id,
    phone,
    channel,
    agent_id,
    campaign_id,
    call_start_time,
    call_end_time,
    duration_sec,
    outcome,
    disposition,
    notes,
    transcript_path,
    created_at,

    -- Derived fields
    CASE WHEN channel = 'BOT' THEN 1 ELSE 0 END as is_bot_call,
    CASE WHEN channel = 'TELECALLER' THEN 1 ELSE 0 END as is_human_call,
    CASE WHEN outcome = 'CONNECTED' THEN 1 ELSE 0 END as is_connected,
    CASE WHEN outcome IN ('NO_ANSWER', 'BUSY', 'FAILED') THEN 1 ELSE 0 END as is_not_connected,
    CASE WHEN disposition IN ('PTP', 'PAID_CLAIM') THEN 1 ELSE 0 END as is_ptp_call,
    CASE WHEN transcript_path IS NOT NULL THEN 1 ELSE 0 END as has_transcript,
    DATE(call_start_time) as call_date,
    EXTRACT(HOUR FROM call_start_time) as call_hour

FROM {{ source('raw', 'fct_calls') }}
