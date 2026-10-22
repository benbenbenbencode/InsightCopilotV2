{% set as_of = "'" ~ var('as_of_date') ~ "'::date" %}

select
    customer_id,
    signup_date,
    ({{ as_of }} - signup_date)                              as tenure_days,
    birth_year,
    extract(year from {{ as_of }})::int - birth_year         as age,
    case
        when extract(year from {{ as_of }})::int - birth_year < 25 then '<25'
        when extract(year from {{ as_of }})::int - birth_year < 35 then '25-34'
        when extract(year from {{ as_of }})::int - birth_year < 45 then '35-44'
        else '45+'
    end                                                      as age_band,
    gender,
    city,
    province,
    employment_type,
    monthly_income,
    case
        when monthly_income <  5000000 then '<5M'
        when monthly_income < 10000000 then '5-10M'
        when monthly_income < 20000000 then '10-20M'
        else '20M+'
    end                                                      as income_band,
    acquisition_channel,
    device_os,
    kyc_verified
from {{ source('raw', 'raw_customers') }}
