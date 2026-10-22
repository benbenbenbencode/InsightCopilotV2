from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .config import Settings


class DBError(RuntimeError):
    pass


def make_engine(s: Settings) -> Engine:
    return create_engine(s.database_url, pool_pre_ping=True)


def dialect_for(engine: Engine) -> str:
    """sqlglot dialect name matching the engine."""
    return {"postgresql": "postgres"}.get(engine.dialect.name, engine.dialect.name)


def run_select(engine: Engine, sql: str, s: Settings) -> pd.DataFrame:
    """Run an already-validated SELECT. Defense in depth on Postgres: the
    transaction is read-only and has a statement timeout, on top of the
    read-only role you should connect with."""
    try:
        with engine.connect() as conn:
            with conn.begin():
                if engine.dialect.name == "postgresql":
                    conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                    conn.exec_driver_sql(f"SET LOCAL statement_timeout = {int(s.statement_timeout_ms)}")
                res = conn.exec_driver_sql(sql)
                rows = [tuple(r) for r in res.fetchmany(s.max_rows)]
                return pd.DataFrame(rows, columns=list(res.keys()))
    except SQLAlchemyError as e:
        raise DBError(str(getattr(e, "orig", e)).strip()) from e
