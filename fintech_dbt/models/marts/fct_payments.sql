{{ config(indexes=[{'columns': ['loan_id']}, {'columns': ['paid_at']}]) }}
-- Grain: one row per payment received (cash-in events).

select
    p.payment_id,
    p.loan_id,
    l.customer_id,
    l.product_id,
    p.installment_no,
    p.paid_at,
    p.paid_at::date                                           as paid_date,
    date_trunc('month', p.paid_at)::date                      as paid_month,
    i.due_date,
    greatest(p.paid_at::date - i.due_date, 0)                 as days_late,
    (p.paid_at::date > i.due_date)                            as is_late,
    p.amount_paid,
    p.late_fee,
    p.payment_channel
from {{ source('raw', 'raw_payments') }} p
join {{ source('raw', 'raw_loans') }} l using (loan_id)
join {{ source('raw', 'raw_installments') }} i using (loan_id, installment_no)
