"""Schema introspection + optional semantic layer (semantic.yml)."""
from __future__ import annotations

from dataclasses import dataclass, field

import yaml
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from .config import Settings


@dataclass
class SchemaInfo:
    tables: dict[str, list[tuple[str, str]]]
    descriptions: dict[str, str] = field(default_factory=dict)
    column_docs: dict[str, dict[str, str]] = field(default_factory=dict)
    joins: list[str] = field(default_factory=list)
    metrics: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def table_names(self) -> set[str]:
        return set(self.tables)

    def to_prompt(self) -> str:
        out = ["SCHEMA"]
        for t, cols in self.tables.items():
            desc = self.descriptions.get(t)
            out.append(f"- {t}" + (f": {desc}" if desc else ""))
            for c, typ in cols:
                doc = self.column_docs.get(t, {}).get(c)
                out.append(f"    {c} ({typ})" + (f" -- {doc}" if doc else ""))
        if self.joins:
            out.append("\nJOINS (known keys)")
            out += [f"- {j}" for j in self.joins]
        if self.metrics:
            out.append("\nBUSINESS METRICS (use these definitions)")
            out += [f"- {k} = {v}" for k, v in self.metrics.items()]
        if self.notes:
            out.append("\nNOTES")
            out += [f"- {n}" for n in self.notes]
        return "\n".join(out)


def load_semantic(path: str | None) -> dict:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_schema(engine: Engine, s: Settings) -> SchemaInfo:
    sem = load_semantic(s.semantic_file)
    schema = s.db_schema if engine.dialect.name == "postgresql" else None
    insp = inspect(engine)
    names = set(insp.get_table_names(schema=schema)) | set(insp.get_view_names(schema=schema))

    wanted = list((sem.get("tables") or {}).keys()) or s.allowed_tables
    if wanted:
        names = {n for n in names if n in set(wanted)}
    if not names:
        raise RuntimeError("No queryable tables found. Check DB_SCHEMA / ALLOWED_TABLES / semantic.yml.")

    tables, fk_joins = {}, []
    for n in sorted(names):
        tables[n] = [(c["name"], str(c["type"])) for c in insp.get_columns(n, schema=schema)]
        try:
            for fk in insp.get_foreign_keys(n, schema=schema):
                ref = fk["referred_table"]
                if ref in names:
                    for a, b in zip(fk["constrained_columns"], fk["referred_columns"]):
                        fk_joins.append(f"{n}.{a} = {ref}.{b}")
        except NotImplementedError:
            pass

    sem_tables = sem.get("tables") or {}
    return SchemaInfo(
        tables=tables,
        descriptions={t: (v or {}).get("description", "") for t, v in sem_tables.items()},
        column_docs={t: (v or {}).get("columns", {}) for t, v in sem_tables.items()},
        joins=list(sem.get("joins") or []) + fk_joins,
        metrics=sem.get("metrics") or {},
        notes=sem.get("notes") or [],
    )
