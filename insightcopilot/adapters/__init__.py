from __future__ import annotations

from ..agent import AskResult
from .base import Adapter, AdapterError, ChartSpec
from .csv_export import CsvAdapter
from .metabase import MetabaseAdapter
from .superset import SupersetAdapter

TARGETS = ("metabase", "superset", "csv")


def publish_result(result: AskResult, target: str) -> str:
    """Send an agent result to a BI tool. Returns a URL (or file path for csv)."""
    if not result.ok or not result.sql:
        raise AdapterError("Nothing to publish: the agent did not produce a query.")
    chart = result.chart or {}
    if target == "csv":
        return CsvAdapter().export_rows(chart.get("title", "result"), result.columns, result.rows)
    spec = ChartSpec(title=chart.get("title", "InsightCopilot result"), sql=result.sql,
                     chart_type=chart.get("type", "table"), x=chart.get("x"), y=chart.get("y"),
                     columns=result.columns)
    if target == "metabase":
        return MetabaseAdapter().publish(spec)
    if target == "superset":
        return SupersetAdapter().publish(spec)
    raise AdapterError(f"Unknown target {target!r}. Choose from {TARGETS}.")
