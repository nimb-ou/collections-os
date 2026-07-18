{{
    config(
        materialized='view'
    )
}}

-- Staging model for EMI presentations
-- Source: fct_presentations

SELECT
    presentation_id,
    account_id,
    present_date,
    amount,
    status,
    bounce_reason,
    inst_no,
    created_at,

    -- Derived fields
    CASE WHEN status = 'B' THEN 1 ELSE 0 END as is_bounce,
    CASE WHEN status = 'S' THEN 1 ELSE 0 END as is_success

FROM {{ source('raw', 'fct_presentations') }}
