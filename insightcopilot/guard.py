"""SQL guard. Parses the query (no string matching) and enforces:
single statement, read-only query, table whitelist, no dangerous functions,
row cap. Returns the normalized SQL that is safe to execute."""
from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError


class GuardError(ValueError):
    pass


_FORBIDDEN_NAMES = [
    "Insert", "Update", "Delete", "Drop", "Create", "Alter", "AlterTable",
    "Command", "Merge", "TruncateTable", "Into", "Set", "Use", "Copy",
    "Grant", "Revoke", "Transaction", "Commit", "Rollback", "LockingProperty",
]
FORBIDDEN_NODES = tuple(getattr(exp, n) for n in _FORBIDDEN_NAMES if hasattr(exp, n))

_BLOCKED_FUNC_PREFIXES = ("pg_", "lo_", "dblink")
_BLOCKED_FUNCS = {"set_config", "current_setting", "query_to_xml", "xpath", "load_extension", "readfile"}


def _func_name(f: exp.Func) -> str:
    name = f.name if isinstance(f, exp.Anonymous) else f.sql_name()
    return (name or "").lower()


def validate(sql: str, allowed_tables: set[str], dialect: str, max_rows: int = 1000,
             schema: str | None = None) -> str:
    if not sql or not sql.strip():
        raise GuardError("empty SQL")

    try:
        statements = sqlglot.parse(sql, read=dialect)
    except SqlglotError as e:
        raise GuardError(f"cannot parse SQL: {e}") from e

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise GuardError("exactly one statement is allowed")
    tree = statements[0]

    if not isinstance(tree, exp.Query):
        raise GuardError("only SELECT / WITH queries are allowed")

    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise GuardError(f"forbidden construct: {type(node).__name__}")

    for f in tree.find_all(exp.Func):
        name = _func_name(f)
        if name.startswith(_BLOCKED_FUNC_PREFIXES) or name in _BLOCKED_FUNCS:
            raise GuardError(f"function not allowed: {name}")

    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    allowed = {t.lower() for t in allowed_tables}
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if name in cte_names and not t.db:
            continue
        if t.db and schema and t.db.lower() != schema.lower():
            raise GuardError(f"schema not allowed: {t.db}")
        if name not in allowed:
            raise GuardError(f"table not allowed: {t.name}. Allowed: {sorted(allowed)}")

    limit = tree.args.get("limit")
    n = None
    if limit is not None:
        try:
            n = int(limit.expression.name)
        except (ValueError, AttributeError, TypeError):
            n = None
    if limit is None or n is None or n > max_rows:
        tree = tree.limit(max_rows)

    return tree.sql(dialect=dialect)
