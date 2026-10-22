import pytest

from insightcopilot.guard import GuardError, validate

A = {"fct_transactions", "dim_users"}


def ok(sql, **kw):
    return validate(sql, A, "postgres", 1000, "public", **kw)


def test_adds_limit_and_strips_semicolon():
    assert ok("SELECT 1 FROM fct_transactions;").endswith("LIMIT 1000")


def test_caps_large_limit():
    assert "LIMIT 1000" in ok("SELECT * FROM fct_transactions LIMIT 99999")


def test_cte_allowed():
    ok("WITH x AS (SELECT * FROM fct_transactions) SELECT * FROM x")


def test_column_named_updated_at_is_fine():
    ok("SELECT updated_at FROM fct_transactions")


@pytest.mark.parametrize("sql", [
    "DELETE FROM fct_transactions",
    "SELECT 1; DROP TABLE fct_transactions",
    "SELECT * FROM secrets",
    "SELECT pg_sleep(10)",
    "SELECT * INTO x FROM fct_transactions",
    "SELECT * FROM other.fct_transactions",
    "",
    "not sql at all ((",
])
def test_rejects(sql):
    with pytest.raises(GuardError):
        ok(sql)
