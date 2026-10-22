"""Golden-question regression harness.

    python -m insightcopilot.evals evals/golden.yml

Each case has a question and a reference SQL written by a human. The agent's
result must match the reference result (order-insensitive, numbers rounded).
Run it after every prompt, model or schema change: agent SQL is only
trustworthy if you measure it."""
from __future__ import annotations

import sys

import pandas as pd
import yaml

from .db import run_select
from .service import Service


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    for c in out.select_dtypes(include="number").columns:
        out[c] = out[c].astype(float).round(2)
    out = out[sorted(out.columns)]
    return out.sort_values(list(out.columns)).reset_index(drop=True)


def same_result(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    if a.shape != b.shape:
        return False
    # compare values only: the agent may alias columns differently
    va = pd.DataFrame(_norm(a).values)
    vb = pd.DataFrame(_norm(b).values)
    try:
        return bool((va.astype(str) == vb.astype(str)).all().all())
    except Exception:
        return False


def run(path: str) -> int:
    cases = yaml.safe_load(open(path, encoding="utf-8"))["cases"]
    svc = Service.build()
    passed = 0
    for case in cases:
        res = svc.ask(case["question"])
        ok = False
        if res.ok and res.rows:
            expected = run_select(svc.engine, case["reference_sql"], svc.settings)
            ok = same_result(pd.DataFrame(res.rows), expected)
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {case['question']}  (steps={len(res.trace)})")
        if not ok:
            print(f"        agent sql: {res.sql}")
    print(f"\n{passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else "evals/golden.yml"))
