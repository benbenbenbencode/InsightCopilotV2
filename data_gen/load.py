"""Load the generated CSVs into Postgres schema `raw` using COPY (fast, and
light on a free tier). Use your OWNER/admin connection string, not the
read-only one.

    python data_gen/load.py --data data

Env: ADMIN_DATABASE_URL  e.g. postgresql://user:pass@host:5432/postgres
(Supabase: use the *Session pooler* string, port 5432.)
"""
from __future__ import annotations

import argparse
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DDL = {
    "raw_products": """product_id int primary key, product_name text, product_type text,
        min_amount bigint, max_amount bigint, tenor_options text""",
    "raw_customers": """customer_id int primary key, signup_date date, birth_year int, gender text,
        city text, province text, employment_type text, monthly_income bigint,
        acquisition_channel text, device_os text, kyc_verified boolean""",
    "raw_applications": """application_id int primary key, customer_id int, application_date date,
        product_id int, requested_amount bigint, approved_amount bigint, decision text,
        reject_reason text, credit_score int, risk_grade text, accepted_by_customer boolean""",
    "raw_loans": """loan_id int primary key, application_id int, customer_id int, product_id int,
        disbursement_date date, principal bigint, tenor_months int, monthly_interest_rate numeric(6,4),
        admin_fee bigint, risk_grade text, acquisition_channel text""",
    "raw_installments": """loan_id int, installment_no int, due_date date, principal_due bigint,
        interest_due bigint, total_due bigint, primary key (loan_id, installment_no)""",
    "raw_payments": """payment_id bigint primary key, loan_id int, installment_no int,
        paid_at timestamp, amount_paid bigint, late_fee bigint, payment_channel text""",
}
ORDER = list(DDL)


def connect():
    url = os.environ.get("ADMIN_DATABASE_URL")
    if not url:
        raise SystemExit("Set ADMIN_DATABASE_URL in .env (owner connection, not the read-only role).")
    return psycopg2.connect(url.replace("+psycopg2", ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    a = ap.parse_args()
    con = connect()
    cur = con.cursor()
    cur.execute("create schema if not exists raw")
    for t in reversed(ORDER):
        cur.execute(f"drop table if exists raw.{t}")
    for t in ORDER:
        cur.execute(f"create table raw.{t} ({DDL[t]})")
    con.commit()

    for t in ORDER:
        with open(os.path.join(a.data, f"{t}.csv"), "r", encoding="utf-8") as f:
            cur.copy_expert(f"copy raw.{t} from stdin with (format csv, header true)", f)
        con.commit()
        cur.execute(f"select count(*) from raw.{t}")
        print(f"raw.{t:18s} {cur.fetchone()[0]:>10,} rows")

    cur.execute("analyze")
    con.commit()
    cur.execute("select pg_size_pretty(pg_database_size(current_database()))")
    print("database size now:", cur.fetchone()[0], "(free tier limit is usually 500 MB)")
    con.close()


if __name__ == "__main__":
    main()
