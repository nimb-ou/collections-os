{{
    config(
        materialized='view'
    )
}}

-- Staging model for payments
-- Source: fct_payments

SELECT
    payment_id,
    account_id,
    pay_date,
    amount,
    mode,
    alloc_to_inst,
    collected_by,
    created_at,

    -- Derived fields
    CASE WHEN collected_by IS NOT NULL THEN 1 ELSE 0 END as is_field_collection

FROM {{ source('raw', 'fct_payments') }}
