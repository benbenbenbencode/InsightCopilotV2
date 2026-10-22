from __future__ import annotations

import os

import requests

from .base import Adapter, AdapterError, ChartSpec

_DISPLAY = {"bar": "bar", "line": "line", "table": "table", "number": "scalar"}


def build_card_payload(spec: ChartSpec, database_id: int, collection_id: int | None) -> dict:
    settings: dict = {}
    if spec.chart_type in ("bar", "line") and spec.x and spec.y:
        settings = {"graph.dimensions": [spec.x], "graph.metrics": [spec.y]}
    payload = {
        "name": spec.title,
        "display": _DISPLAY.get(spec.chart_type, "table"),
        "visualization_settings": settings,
        "dataset_query": {
            "type": "native",
            "database": database_id,
            "native": {"query": spec.sql},
        },
    }
    if collection_id:
        payload["collection_id"] = collection_id
    return payload


class MetabaseAdapter(Adapter):
    name = "metabase"

    def __init__(self):
        self.base = os.environ.get("METABASE_URL", "").rstrip("/")
        self.api_key = os.environ.get("METABASE_API_KEY")
        self.user = os.environ.get("METABASE_USER")
        self.password = os.environ.get("METABASE_PASSWORD")
        db = os.environ.get("METABASE_DATABASE_ID")
        col = os.environ.get("METABASE_COLLECTION_ID")
        if not self.base or not db:
            raise AdapterError("Set METABASE_URL and METABASE_DATABASE_ID.")
        self.database_id = int(db)
        self.collection_id = int(col) if col else None

    def _headers(self) -> dict:
        if self.api_key:
            return {"x-api-key": self.api_key}
        if self.user and self.password:
            r = requests.post(f"{self.base}/api/session",
                              json={"username": self.user, "password": self.password}, timeout=30)
            if not r.ok:
                raise AdapterError(f"Metabase login failed: {r.status_code}")
            return {"X-Metabase-Session": r.json()["id"]}
        raise AdapterError("Set METABASE_API_KEY (or METABASE_USER + METABASE_PASSWORD).")

    def publish(self, spec: ChartSpec) -> str:
        payload = build_card_payload(spec, self.database_id, self.collection_id)
        r = requests.post(f"{self.base}/api/card", json=payload, headers=self._headers(), timeout=60)
        if not r.ok:
            raise AdapterError(f"Metabase error {r.status_code}: {r.text[:300]}")
        return f"{self.base}/question/{r.json()['id']}"
