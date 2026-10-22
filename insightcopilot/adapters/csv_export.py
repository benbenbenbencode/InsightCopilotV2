from __future__ import annotations

import csv
import os
import re
import time

from .base import Adapter, ChartSpec


class CsvAdapter(Adapter):
    """Fallback 'BI': writes the result to exports/*.csv. Needs rows, so it
    is called through export_rows() rather than publish()."""
    name = "csv"

    def __init__(self, out_dir: str = "exports"):
        self.out_dir = out_dir

    def export_rows(self, title: str, columns: list[str], rows: list[dict]) -> str:
        os.makedirs(self.out_dir, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "result"
        path = os.path.join(self.out_dir, f"{slug}-{int(time.time())}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=columns)
            w.writeheader()
            w.writerows(rows)
        return path

    def publish(self, spec: ChartSpec) -> str:  # pragma: no cover
        raise NotImplementedError("Use export_rows() for CSV.")
