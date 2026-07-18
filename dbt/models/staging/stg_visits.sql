{{
    config(
        materialized='view'
    )
}}

-- Staging model for field visits
-- Source: fct_visits

SELECT
    visit_id,
    account_id,
    customer_id,
    agent_id,
    visit_date,
    visit_time,
    disposition,
    amount_collected,
    payment_mode,
    payment_ref,
    geo_lat,
    geo_lon,
    photo_path,
    notes,
    created_at,

    -- Derived fields
    CASE WHEN amount_collected > 0 THEN 1 ELSE 0 END as has_payment,
    CASE WHEN geo_lat IS NOT NULL AND geo_lon IS NOT NULL THEN 1 ELSE 0 END as has_geolocation,
    CASE WHEN photo_path IS NOT NULL THEN 1 ELSE 0 END as has_photo,
    CASE WHEN disposition = 'VISIT_MET' THEN 1 ELSE 0 END as is_customer_met,
    CASE WHEN disposition = 'VISIT_NOT_FOUND' THEN 1 ELSE 0 END as is_customer_not_home,
    EXTRACT(HOUR FROM visit_time) as visit_hour

FROM {{ source('raw', 'fct_visits') }}
