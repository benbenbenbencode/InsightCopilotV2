from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


@dataclass
class Settings:
    database_url: str
    db_schema: str = "public"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5-coder:7b"
    max_steps: int = 8
    max_rows: int = 1000
    statement_timeout_ms: int = 15000
    semantic_file: str | None = None
    allowed_tables: list[str] | None = None
    audit_log: str = "logs/queries.jsonl"
    api_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env.")
        allowed = os.environ.get("ALLOWED_TABLES")
        return cls(
            database_url=url,
            db_schema=os.environ.get("DB_SCHEMA", "public"),
            llm_base_url=os.environ.get("LLM_BASE_URL", cls.llm_base_url).rstrip("/"),
            llm_api_key=os.environ.get("LLM_API_KEY", cls.llm_api_key),
            llm_model=os.environ.get("LLM_MODEL", cls.llm_model),
            max_steps=_int("MAX_STEPS", cls.max_steps),
            max_rows=_int("MAX_ROWS", cls.max_rows),
            statement_timeout_ms=_int("STATEMENT_TIMEOUT_MS", cls.statement_timeout_ms),
            semantic_file=os.environ.get("SEMANTIC_FILE") or None,
            allowed_tables=[t.strip() for t in allowed.split(",")] if allowed else None,
            audit_log=os.environ.get("AUDIT_LOG", cls.audit_log),
            api_key=os.environ.get("API_KEY") or None,
        )
