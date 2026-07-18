{{
    config(
        materialized='view'
    )
}}

-- Staging model for account dimension
-- Source: dim_account

SELECT
    account_id,
    customer_id,
    product_type,
    asset_desc,
    disbursal_date,
    disbursal_amt,
    tenure_m,
    roi,
    emi_amt,
    cycle_day,
    branch,
    state,
    city,
    pincode,
    geo_id,
    status,
    created_at,
    updated_at,
    valid_from,
    valid_to,

    -- Derived fields
    CASE
        WHEN disbursal_amt < 500000 THEN 'small'
        WHEN disbursal_amt < 2000000 THEN 'medium'
        ELSE 'large'
    END as ticket_size_category,

    CASE
        WHEN tenure_m <= 24 THEN 'short'
        WHEN tenure_m <= 48 THEN 'medium'
        ELSE 'long'
    END as tenure_category,

    -- Account vintage in months from disbursal to current date
    EXTRACT(YEAR FROM AGE(CURRENT_DATE, disbursal_date)) * 12 +
    EXTRACT(MONTH FROM AGE(CURRENT_DATE, disbursal_date)) as vintage_months,

    -- LTV (total interest + principal)
    disbursal_amt * (1 + (roi / 100.0) * (tenure_m / 12.0)) as total_ltv,

    -- Product category grouping
    CASE
        WHEN product_type IN ('LCV', 'HCV', 'TIPPER') THEN 'commercial_vehicle'
        WHEN product_type = 'TRACTOR' THEN 'farm_equipment'
        WHEN product_type IN ('CE', 'EXCAVATOR', 'LOADER') THEN 'construction_equipment'
        ELSE 'other'
    END as product_category

FROM {{ source('raw', 'dim_account') }}
WHERE status = 'ACTIVE'
