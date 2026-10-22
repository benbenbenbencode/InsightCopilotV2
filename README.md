# InsightCopilot v2

Ask a question in plain language. An **autonomous agent** explores your schema, writes its own SQL, reads errors and fixes itself, then answers with a verified summary and a chart you can send to **Metabase, Superset, or CSV**.

```
question -> agent loop (LLM) -> guard (sqlglot) -> read-only DB
                 ^                                      |
                 +---- errors / previews fed back ------+
                 |
                 v
   answer + chart spec -> grounding check -> adapter (Metabase | Superset | CSV)
```

## What changed from v1

| v1 | v2 |
|---|---|
| LLM only picked table names; query rebuilt from keywords | LLM writes the SQL; agent iterates until the result answers the question |
| String-matching validator (`;`, `UPDATE` in column names broke it) | `sqlglot` AST guard: single SELECT/WITH, table whitelist, blocked functions, row cap |
| Superuser DB creds, no timeout | Read-only role + read-only transaction + statement timeout |
| Fan-out double counting through promo join | Prompt rules + `semantic.yml` notes/metrics; agent aggregates before joining |
| Anomaly/root-cause/recommender bolted on | Removed (not part of the core job) |
| Ollama via subprocess, hardcoded URLs | Any OpenAI-compatible endpoint (Ollama, Groq, OpenAI) via env |
| No pipeline tests | 24 tests incl. agent self-correction + golden-question eval harness |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env     # DATABASE_URL (read-only role), LLM_*, SEMANTIC_FILE=semantic.yml
```

Run:

```bash
streamlit run insightcopilot/ui.py                 # UI
uvicorn insightcopilot.api:app                     # API: POST /ask {"question": "...", "publish_to": "metabase"}
pytest                                             # unit tests
python -m insightcopilot.evals evals/golden.yml    # accuracy regression against the demo data
```

## Demo data: synthetic fintech lending (free-tier friendly)

A consumer-lending dataset (applications, loans, installments, payments) with built-in stories to discover
(worse default rate for loans disbursed from 2025-07, paid-social vs referral, risk grade E, first-payment defaults).

| size | customers | rows (raw) | DB size raw + marts |
|---|---|---|---|
| small | 10k | ~115k | ~35 MB |
| medium (default) | 40k | ~460k | ~125 MB |
| large | 100k | ~1.16M | ~310 MB |

```bash
pip install -r requirements-data.txt
python data_gen/generate.py --size medium --out data          # CSVs, deterministic (--seed)
# run sql/01_readonly_role.sql once as admin (creates ic_readonly)
python data_gen/load.py --data data                           # needs ADMIN_DATABASE_URL in .env
cd fintech_dbt && cp profiles.yml.example ~/.dbt/profiles.yml  # set DBT_* env vars (owner connection)
dbt run && dbt test                                           # builds 3 dims + 4 facts in schema public
```

Marts (`fintech_dbt/models/marts`): `dim_customers`, `dim_products`, `dim_date`, `fct_applications` (one row per application),
`fct_loans` (one row per loan + performance), `fct_installments` (one row per scheduled installment, with DPD), `fct_payments` (one row per payment).
`semantic.yml` documents them for the agent. Check size anytime with `sql/02_check_size.sql`.
To free ~45% space after dbt, `DROP SCHEMA raw CASCADE;` (keep the CSVs to reload).

## Safety model

1. Guard parses every query (never string-matches) and only lets one read-only SELECT/WITH over whitelisted tables through.
2. Postgres side: read-only transaction, statement timeout, read-only role.
3. Every query is appended to `logs/queries.jsonl` (question, SQL, rows, steps, errors).
4. Summary numbers are checked against the result; unverifiable figures trigger one rewrite, then a visible warning.
5. Set `API_KEY` to require `X-API-Key` on the API.

## Output adapters

- **Metabase**: native-SQL question via `/api/card`. Needs `METABASE_URL`, `METABASE_DATABASE_ID`, and `METABASE_API_KEY`.
- **Superset**: virtual dataset + chart via REST API. Needs `SUPERSET_*`.
- **CSV**: `exports/*.csv`.

> The Metabase and Superset adapters are unit-tested for payload shape only, not against a live instance. Superset's chart `params` differ between versions; if a chart looks wrong, adjust `build_chart_payload` in `adapters/superset.py`. Add a new BI tool by implementing `Adapter.publish(spec) -> url`.

## Accuracy

SQL agents are only as good as their schema docs and your measurement. Fill `semantic.yml` (metric definitions, join keys, gotchas) and grow `evals/golden.yml` with real questions; rerun it after any model, prompt, or schema change. Models without strong SQL ability (small local models) will need more steps and fail more often. A 7B+ coder model or a hosted 70B is a sensible floor.
