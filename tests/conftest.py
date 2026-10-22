import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from insightcopilot.config import Settings  # noqa: E402
from insightcopilot.db import make_engine  # noqa: E402
from insightcopilot.schema import load_schema  # noqa: E402


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "retail.db"
    con = sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE dim_users (user_id INTEGER PRIMARY KEY, city TEXT);
    CREATE TABLE dim_products (product_id INTEGER PRIMARY KEY, product_name TEXT);
    CREATE TABLE fct_transactions (order_id INTEGER, user_id INTEGER, product_id INTEGER, revenue REAL);
    INSERT INTO dim_users VALUES (1,'Jakarta'),(2,'Batam');
    INSERT INTO dim_products VALUES (1,'Tea'),(2,'Coffee');
    INSERT INTO fct_transactions VALUES (1,1,1,100),(2,1,2,300),(3,2,1,50);
    """)
    con.commit(); con.close()
    s = Settings(database_url=f"sqlite:///{db}", audit_log=str(tmp_path / "audit.jsonl"), max_steps=6)
    engine = make_engine(s)
    return s, engine, load_schema(engine, s)


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return self.replies.pop(0)
