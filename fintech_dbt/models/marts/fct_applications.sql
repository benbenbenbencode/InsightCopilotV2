{{ config(indexes=[{'columns': ['customer_id']}, {'columns': ['application_date']}]) }}
-- Grain: one row per loan application (approved AND rejected). Use for funnel / approval analysis.

select
    a.application_id,
    a.customer_id,
    a.application_date,
    date_trunc('month', a.application_date)::date            as application_month,
    a.product_id,
    a.requested_amount,
    a.approved_amount,
    a.decision,                                              -- approved | rejected
    a.reject_reason,                                         -- null when approved
    a.credit_score,
    a.risk_grade,                                            -- A (best) .. E (worst)
    a.accepted_by_customer,
    l.loan_id,                                               -- null if not disbursed
    (l.loan_id is not null)                                  as is_disbursed,
    (l.disbursement_date - a.application_date)               as days_to_disburse
from {{ source('raw', 'raw_applications') }} a
left join {{ source('raw', 'raw_loans') }} l using (application_id)
