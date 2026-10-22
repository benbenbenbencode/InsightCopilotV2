-- Run ONCE as the owner/admin (Supabase: SQL Editor). Replace the password.
-- The agent connects as ic_readonly and can only SELECT from the dbt marts in `public`.
-- It has no access to the `raw` schema.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ic_readonly') THEN
    CREATE ROLE ic_readonly LOGIN PASSWORD 'CHANGE_ME';
  END IF;
END $$;

GRANT CONNECT ON DATABASE postgres TO ic_readonly;   -- Supabase/Neon default db is "postgres"; change if yours differs
GRANT USAGE ON SCHEMA public TO ic_readonly;
ALTER ROLE ic_readonly SET statement_timeout = '15s';

-- Future tables created by the role that runs dbt are readable automatically.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ic_readonly;
-- Tables that already exist (after the first dbt run):
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ic_readonly;
