{{ config(indexes=[{'columns': ['customer_id']}, {'columns': ['disbursement_date']}]) }}
-- Grain: one row per disbursed loan, with repayment performance as of `as_of_date`.

with inst as (
    select
        loan_id,
        count(*)                                                                as installments_total,
        count(*) filter (where status in ('paid_on_time', 'paid_late'))         as installments_paid,
        count(*) filter (where status = 'overdue')                              as installments_overdue,
        sum(total_due)                                                          as total_due_amount,
        sum(paid_amount)                                                        as total_paid_amount,
        sum(principal_due) filter (where status in ('paid_on_time', 'paid_late')) as principal_repaid,
        sum(interest_due)  filter (where status in ('paid_on_time', 'paid_late')) as interest_collected,
        sum(late_fee_paid)                                                      as late_fees_collected,
        sum(principal_due) filter (where status = 'overdue')                    as overdue_principal,
        max(dpd)                                                                as max_dpd_ever,
        max(dpd) filter (where status = 'overdue')                              as current_dpd,
        max(dpd) filter (where installment_no = 1)                              as first_installment_dpd
    from {{ ref('fct_installments') }}
    group by 1
)

select
    l.loan_id,
    l.application_id,
    l.customer_id,
    l.product_id,
    l.disbursement_date,
    date_trunc('month', l.disbursement_date)::date            as disbursement_month,
    l.principal,
    l.tenor_months,
    l.monthly_interest_rate,
    l.admin_fee,
    l.risk_grade,
    l.acquisition_channel,
    i.installments_total,
    i.installments_paid,
    i.installments_overdue,
    i.total_due_amount,
    i.total_paid_amount,
    coalesce(i.principal_repaid, 0)                           as principal_repaid,
    l.principal - coalesce(i.principal_repaid, 0)             as outstanding_principal,
    coalesce(i.overdue_principal, 0)                          as overdue_principal,
    coalesce(i.interest_collected, 0)                         as interest_collected,
    coalesce(i.late_fees_collected, 0)                        as late_fees_collected,
    l.admin_fee + coalesce(i.interest_collected, 0)
                + coalesce(i.late_fees_collected, 0)          as revenue_collected,
    i.max_dpd_ever,
    coalesce(i.current_dpd, 0)                                as current_dpd,
    case
        when i.installments_paid = i.installments_total then 'closed'
        when coalesce(i.current_dpd, 0) > 90                  then 'npl_90plus'
        when coalesce(i.current_dpd, 0) > 0                   then 'delinquent'
        else 'current'
    end                                                       as loan_status,
    coalesce(i.current_dpd, 0) > 90                           as is_npl90,
    coalesce(i.max_dpd_ever, 0) >= 30                         as ever_dpd30,
    coalesce(i.first_installment_dpd, 0) >= 30                as is_fpd30   -- first-payment default
from {{ source('raw', 'raw_loans') }} l
join inst i using (loan_id)
