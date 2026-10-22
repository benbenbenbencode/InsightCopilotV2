import json

from insightcopilot.agent import ask, parse_action

from conftest import FakeLLM


def j(**kw):
    return json.dumps(kw)


def test_parse_action_tolerates_chatter():
    assert parse_action('Sure!\n```json\n{"action":"run_sql","sql":"SELECT 1"}\n```')["action"] == "run_sql"
    assert parse_action("no json here") is None


def test_agent_self_corrects_then_answers(env):
    s, engine, schema = env
    llm = FakeLLM([
        j(action="run_sql", sql="SELECT city, SUM(rev) FROM fct_transactions"),  # bad column
        j(action="run_sql", sql=("SELECT u.city, SUM(t.revenue) AS total_revenue FROM fct_transactions t "
                                 "JOIN dim_users u ON t.user_id = u.user_id GROUP BY u.city ORDER BY 2 DESC")),
        j(action="answer", summary="Jakarta leads with 400 revenue.",
          chart={"type": "bar", "x": "city", "y": "total_revenue", "title": "Revenue by city"}),
    ])
    r = ask("revenue by city", s, engine, schema, llm)
    assert r.ok and r.rows[0] == {"city": "Jakarta", "total_revenue": 400.0}
    assert r.chart["type"] == "bar"
    assert "ERROR" in r.trace[0]["observation"]
    assert not r.warnings


def test_agent_blocked_sql_is_fed_back(env):
    s, engine, schema = env
    llm = FakeLLM([
        j(action="run_sql", sql="DROP TABLE dim_users"),
        j(action="run_sql", sql="SELECT COUNT(*) AS n FROM dim_users"),
        j(action="answer", summary="There are 2 users.", chart={"type": "number", "y": "n"}),
    ])
    r = ask("how many users", s, engine, schema, llm)
    assert r.ok and r.rows == [{"n": 2}]
    assert "only SELECT" in r.trace[0]["observation"]


def test_hallucinated_number_triggers_one_revision(env):
    s, engine, schema = env
    llm = FakeLLM([
        j(action="run_sql", sql="SELECT COUNT(*) AS n FROM dim_users"),
        j(action="answer", summary="There are 777 users.", chart={"type": "number", "y": "n"}),
        j(action="answer", summary="There are 2 users.", chart={"type": "number", "y": "n"}),
    ])
    r = ask("how many users", s, engine, schema, llm)
    assert r.ok and r.summary == "There are 2 users." and not r.warnings


def test_answer_without_query_is_rejected_and_steps_are_capped(env):
    s, engine, schema = env
    llm = FakeLLM([j(action="answer", summary="42")] * 6)
    r = ask("anything", s, engine, schema, llm)
    assert not r.ok and "steps" in r.error


def test_invalid_chart_falls_back_to_table(env):
    s, engine, schema = env
    llm = FakeLLM([
        j(action="run_sql", sql="SELECT city FROM dim_users"),
        j(action="answer", summary="Two cities.", chart={"type": "bar", "x": "nope", "y": "nada"}),
    ])
    r = ask("cities", s, engine, schema, llm)
    assert r.chart["type"] == "table"
