-- One row per calendar day 2023-2027.
select
    d::date                                   as date_day,
    extract(year from d)::int                 as year,
    extract(quarter from d)::int              as quarter,
    extract(month from d)::int                as month,
    to_char(d, 'YYYY-MM')                     as year_month,
    to_char(d, 'Mon')                         as month_name,
    date_trunc('month', d)::date              as month_start,
    date_trunc('week', d)::date               as week_start,
    extract(isodow from d)::int               as day_of_week,   -- 1 = Monday
    extract(isodow from d) in (6, 7)          as is_weekend
from generate_series('2023-01-01'::date, '2027-12-31'::date, interval '1 day') as d
