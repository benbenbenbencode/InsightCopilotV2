"""Autonomous SQL agent. The model explores the schema, writes SQL, reads
errors/results and fixes itself, then answers. Every query goes through the
guard; the model never touches the database directly.

Protocol: one JSON object per turn (works with any chat model):
  {"action":"sample_rows","table":"..."}
  {"action":"run_sql","sql":"..."}
  {"action":"answer","summary":"...","chart":{...}}
  {"action":"answer","cannot_answer":true,"summary":"why"}
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from string import Template

import pandas as pd
from sqlalchemy.engine import Engine

from . import guard
from .audit import log_event
from .config import Settings
from .db import DBError, dialect_for, run_select
from .grounding import ungrounded
from .llm import LLMClient
from .schema import SchemaInfo

SYSTEM = Template("""You are an autonomous data analyst agent. Answer the user's question by exploring the database and writing SQL yourself.
Dialect: $dialect. Access is read-only. Results are capped at $max_rows rows.

$schema

Reply with EXACTLY ONE JSON object per turn and nothing else. Actions:
{"action":"sample_rows","table":"<table>"}                 -> 5 example rows, use to learn real values
{"action":"run_sql","sql":"<one SELECT or WITH query>"}    -> runs it, you get columns + preview or an error
{"action":"answer","summary":"<2-5 sentences>","chart":{"type":"bar|line|table|number","x":"<col>","y":"<col>","title":"<title>"}}
{"action":"answer","cannot_answer":true,"summary":"<why the data can't answer this>"}

Rules:
- Use only the tables and columns listed. If a query errors, read the error and fix it.
- Aggregate BEFORE joining across one-to-many relationships (use CTEs), otherwise sums get multiplied.
- Return only the columns needed, with readable aliases, sensible ORDER BY. Prefer few columns so it can be charted.
- Follow the business metric definitions and notes above.
- The summary may only use numbers that appear in your LAST successful query result. Never invent or estimate figures.
- Stop exploring once a result answers the question. You have at most $max_steps steps.
""")


@dataclass
class AskResult:
    question: str
    ok: bool
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    summary: str = ""
    chart: dict | None = None
    warnings: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    error: str | None = None
    chart_url: str | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def parse_action(text: str) -> dict | None:
    start = text.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) and "action" in obj else None


def _observation(df: pd.DataFrame, preview_rows: int = 15, limit_chars: int = 3000) -> str:
    text = f"OK rows={len(df)} columns={list(df.columns)}\n" + df.head(preview_rows).to_csv(index=False)
    return text[:limit_chars]


def _clean_chart(chart: dict | None, df: pd.DataFrame) -> dict:
    chart = chart or {}
    ctype = chart.get("type", "table")
    cols = set(df.columns)
    x, y = chart.get("x"), chart.get("y")
    if ctype in ("bar", "line") and (x not in cols or y not in cols):
        ctype, x, y = "table", None, None
    if ctype == "number" and (y not in cols and df.shape[1] != 1):
        ctype = "table"
    if ctype not in ("bar", "line", "number", "table"):
        ctype = "table"
    return {"type": ctype, "x": x, "y": y, "title": chart.get("title") or "InsightCopilot result"}


def ask(question: str, s: Settings, engine: Engine, schema: SchemaInfo, llm: LLMClient) -> AskResult:
    t0 = time.time()
    dialect = dialect_for(engine)
    pg_schema = s.db_schema if engine.dialect.name == "postgresql" else None
    system = SYSTEM.substitute(dialect=dialect, max_rows=s.max_rows, max_steps=s.max_steps,
                               schema=schema.to_prompt())
    messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]

    result = AskResult(question=question, ok=False)
    last_sql, last_df = None, None
    revised = False

    def run(sql: str) -> tuple[str, pd.DataFrame]:
        safe = guard.validate(sql, schema.table_names, dialect, s.max_rows, pg_schema)
        return safe, run_select(engine, safe, s)

    for step in range(1, s.max_steps + 1):
        raw = llm.chat(messages)
        messages.append({"role": "assistant", "content": raw})
        action = parse_action(raw)

        if action is None:
            obs = "Invalid reply. Respond with a single JSON object using one of the listed actions."
            result.trace.append({"step": step, "action": "invalid", "observation": obs})
            messages.append({"role": "user", "content": obs})
            continue

        kind = action.get("action")
        entry = {"step": step, "action": kind}

        if kind == "sample_rows":
            table = str(action.get("table", ""))
            if table not in schema.table_names:
                obs = f"ERROR: unknown table {table!r}. Tables: {sorted(schema.table_names)}"
            else:
                try:
                    _, df = run(f'SELECT * FROM "{table}" LIMIT 5')
                    obs = _observation(df)
                except (guard.GuardError, DBError) as e:
                    obs = f"ERROR: {e}"
            entry.update(table=table, observation=obs)

        elif kind == "run_sql":
            sql = str(action.get("sql", ""))
            entry["sql"] = sql
            try:
                safe, df = run(sql)
                last_sql, last_df = safe, df
                obs = _observation(df)
                entry["rows"] = len(df)
            except (guard.GuardError, DBError) as e:
                obs = f"ERROR: {e}"
            entry["observation"] = obs

        elif kind == "answer":
            summary = str(action.get("summary", "")).strip()
            if action.get("cannot_answer"):
                result.ok, result.summary = True, summary
                result.trace.append(entry)
                break
            if last_df is None:
                obs = "ERROR: run a successful query before answering."
                entry["observation"] = obs
            else:
                bad = ungrounded(summary, last_df)
                if bad and not revised:
                    revised = True
                    obs = (f"Your summary mentions numbers not found in the last result: {bad}. "
                           "Rewrite the answer using only numbers from the result.")
                    entry["observation"] = obs
                else:
                    if bad:
                        result.warnings.append(
                            f"Figures {bad} in the summary could not be verified against the data.")
                    result.ok = True
                    result.sql = last_sql
                    result.columns = list(last_df.columns)
                    result.rows = json.loads(last_df.to_json(orient="records", date_format="iso"))
                    result.summary = summary
                    result.chart = _clean_chart(action.get("chart"), last_df)
                    result.trace.append(entry)
                    break
        else:
            obs = f"Unknown action {kind!r}."
            entry["observation"] = obs

        result.trace.append(entry)
        messages.append({"role": "user", "content": entry["observation"]})
    else:
        result.error = f"No final answer after {s.max_steps} steps."
        if last_df is not None:  # return the best partial result instead of nothing
            result.sql = last_sql
            result.columns = list(last_df.columns)
            result.rows = json.loads(last_df.to_json(orient="records", date_format="iso"))
            result.chart = _clean_chart(None, last_df)
            result.warnings.append("Agent ran out of steps; showing the last successful query.")

    log_event(s.audit_log, question=question, ok=result.ok, sql=result.sql, rows=len(result.rows),
              steps=len(result.trace), seconds=round(time.time() - t0, 2), error=result.error,
              warnings=result.warnings)
    return result
