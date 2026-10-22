import json

from insightcopilot.adapters.base import ChartSpec
from insightcopilot.adapters.metabase import build_card_payload
from insightcopilot.adapters.superset import build_chart_payload, build_dataset_payload

SPEC = ChartSpec(title="Rev", sql="SELECT 1 AS a, 2 AS b LIMIT 1000", chart_type="bar", x="a", y="b",
                 columns=["a", "b"])


def test_metabase_payload():
    p = build_card_payload(SPEC, 3, 7)
    assert p["dataset_query"]["native"]["query"] == SPEC.sql
    assert p["display"] == "bar" and p["visualization_settings"]["graph.dimensions"] == ["a"]
    assert p["collection_id"] == 7


def test_superset_payloads():
    d = build_dataset_payload(SPEC, 1, "public")
    assert d["table_name"].startswith("ic_") and d["sql"] == SPEC.sql
    c = build_chart_payload(SPEC, 42)
    params = json.loads(c["params"])
    assert c["datasource_id"] == 42 and params["x_axis"] == "a"
    table = build_chart_payload(ChartSpec("t", "SELECT 1", "table", columns=["a"]), 42)
    assert json.loads(table["params"])["viz_type"] == "table"
