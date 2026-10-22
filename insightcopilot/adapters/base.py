from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChartSpec:
    title: str
    sql: str
    chart_type: str  # bar | line | table | number
    x: str | None = None
    y: str | None = None
    columns: list[str] | None = None


class AdapterError(RuntimeError):
    pass


class Adapter:
    name = "base"

    def publish(self, spec: ChartSpec) -> str:
        """Create the chart/question in the target BI tool and return its URL."""
        raise NotImplementedError
