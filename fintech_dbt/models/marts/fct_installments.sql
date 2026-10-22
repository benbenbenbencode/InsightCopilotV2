{{ config(indexes=[{'columns': ['loan_id']}, {'columns': ['due_date']}, {'columns': ['customer_id']}]) }}
{% set as_of = "'" ~ var('as_of_date') ~ "'::date" %}
-- Grain: one row per scheduled installment, evaluated as of `as_of_date`.
-- dpd = days past due: for paid installments the days it was paid late, for unpaid overdue
-- installments the days overdue as of the snapshot date.

with pay as (
    select
        loan_id,
        installment_no,
        min(paid_at)::date    as paid_date,
        sum(amount_paid)      as paid_amount,
        sum(late_fee)         as late_fee_paid
    from {{ source('raw', 'raw_payments') }}
    group by 1, 2
),

base as (
    select
        i.loan_id,
        i.installment_no,
        i.due_date,
        i.principal_due,
        i.interest_due,
        i.total_due,
        p.paid_date,
        coalesce(p.paid_amount, 0)    as paid_amount,
        coalesce(p.late_fee_paid, 0)  as late_fee_paid,
        case
            when p.paid_date is not null then greatest(p.paid_date - i.due_date, 0)
            when i.due_date < {{ as_of }} then {{ as_of }} - i.due_date
            else 0
        end as dpd,
        case
            when p.paid_date is not null and p.paid_date <= i.due_date then 'paid_on_time'
            when p.paid_date is not null                               then 'paid_late'
            when i.due_date < {{ as_of }}                              then 'overdue'
            else 'not_yet_due'
        end as status
    from {{ source('raw', 'raw_installments') }} i
    left join pay p using (loan_id, installment_no)
)

select
    (b.loan_id::bigint * 100 + b.installment_no)  as installment_id,
    b.loan_id,
    l.customer_id,
    l.product_id,
    l.risk_grade,
    l.acquisition_channel,
    date_trunc('month', l.disbursement_date)::date as disbursement_month,
    b.installment_no,
    b.due_date,
    b.principal_due,
    b.interest_due,
    b.total_due,
    b.paid_date,
    b.paid_amount,
    b.late_fee_paid,
    b.dpd,
    case
        when b.dpd = 0   then '0'
        when b.dpd <= 7  then '1-7'
        when b.dpd <= 30 then '8-30'
        when b.dpd <= 60 then '31-60'
        when b.dpd <= 90 then '61-90'
        else '90+'
    end as dpd_bucket,
    b.status                                       -- paid_on_time | paid_late | overdue | not_yet_due
from base b
join {{ source('raw', 'raw_loans') }} l using (loan_id)
