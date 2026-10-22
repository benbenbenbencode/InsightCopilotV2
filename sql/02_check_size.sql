-- Free tier check (limit is typically 500 MB)
select pg_size_pretty(pg_database_size(current_database())) as db_size;

select schemaname, relname as table_name,
       pg_size_pretty(pg_total_relation_size(relid)) as total_size,
       n_live_tup as approx_rows
from pg_stat_user_tables
where schemaname in ('raw', 'public')
order by pg_total_relation_size(relid) desc;
