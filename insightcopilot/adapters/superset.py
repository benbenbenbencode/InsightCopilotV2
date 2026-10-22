from __future__ import annotations

import hashlib
import json
import os

import requests

from .base import Adapter, AdapterError, ChartSpec


def build_dataset_payload(spec: ChartSpec, database_id: int, schema: str) -> dict:
    name = "ic_" + hashlib.sha1(spec.sql.encode()).hexdigest()[:10]
    return {"database": database_id, "schema": schema, "table_name": name, "sql": spec.sql}


def build_chart_payload(spec: ChartSpec, dataset_id: int) -> dict:
    if spec.chart_type in ("bar", "line") and spec.x and spec.y:
        viz = "echarts_timeseries_bar" if spec.chart_type == "bar" else "echarts_timeseries_line"
        params = {
            "viz_type": viz,
            "x_axis": spec.x,
            "metrics": [{"expressionType": "SQL", "sqlExpression": f'SUM("{spec.y}")', "label": spec.y}],
            "groupby": [],
            "row_limit": 1000,
        }
    else:
        viz = "table"
        params = {"viz_type": "table", "query_mode": "raw",
                  "all_columns": spec.columns or [], "row_limit": 1000}
    params["datasource"] = f"{dataset_id}__table"
    return {
        "slice_name": spec.title,
        "viz_type": viz,
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "params": json.dumps(params),
    }


class SupersetAdapter(Adapter):
    name = "superset"

    def __init__(self):
        self.base = os.environ.get("SUPERSET_URL", "").rstrip("/")
        self.user = os.environ.get("SUPERSET_USER")
        self.password = os.environ.get("SUPERSET_PASSWORD")
        db = os.environ.get("SUPERSET_DATABASE_ID")
        self.schema = os.environ.get("SUPERSET_SCHEMA", "public")
        if not (self.base and self.user and self.password and db):
            raise AdapterError("Set SUPERSET_URL, SUPERSET_USER, SUPERSET_PASSWORD, SUPERSET_DATABASE_ID.")
        self.database_id = int(db)

    def _session(self) -> requests.Session:
        s = requests.Session()
        r = s.post(f"{self.base}/api/v1/security/login", timeout=30,
                   json={"username": self.user, "password": self.password,
                         "provider": "db", "refresh": True})
        if not r.ok:
            raise AdapterError(f"Superset login failed: {r.status_code}")
        s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        c = s.get(f"{self.base}/api/v1/security/csrf_token/", timeout=30)
        if c.ok:
            s.headers["X-CSRFToken"] = c.json()["result"]
        s.headers["Referer"] = self.base
        return s

    def publish(self, spec: ChartSpec) -> str:
        s = self._session()
        ds = s.post(f"{self.base}/api/v1/dataset/", timeout=60,
                    json=build_dataset_payload(spec, self.database_id, self.schema))
        if ds.status_code == 422 and "already exists" in ds.text.lower():
            name = build_dataset_payload(spec, self.database_id, self.schema)["table_name"]
            q = json.dumps({"filters": [{"col": "table_name", "opr": "eq", "value": name}]})
            found = s.get(f"{self.base}/api/v1/dataset/", params={"q": q}, timeout=30)
            if not found.ok or not found.json().get("result"):
                raise AdapterError(f"Superset dataset error: {ds.text[:300]}")
            dataset_id = found.json()["result"][0]["id"]
        elif ds.ok:
            dataset_id = ds.json()["id"]
        else:
            raise AdapterError(f"Superset dataset error {ds.status_code}: {ds.text[:300]}")
        ch = s.post(f"{self.base}/api/v1/chart/", json=build_chart_payload(spec, dataset_id), timeout=60)
        if not ch.ok:
            raise AdapterError(f"Superset chart error {ch.status_code}: {ch.text[:300]}")
        return f"{self.base}/explore/?slice_id={ch.json()['id']}"
