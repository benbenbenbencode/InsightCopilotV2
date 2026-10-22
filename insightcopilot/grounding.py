"""Cheap guardrail: flag numbers in a narrative that cannot be derived from the
query result (cell values, sums, means, min/max, counts, shares in %)."""
from __future__ import annotations

import re

import pandas as pd

_NUM = re.compile(r"(?<![\w.])(-?\d[\d,]*\.?\d*)\s*([kKmMbB])?(?![\w])")
_MULT = {"k": 1e3, "m": 1e6, "b": 1e9}


def numbers_in_text(text: str) -> list[float]:
    vals = []
    for raw, suffix in _NUM.findall(text or ""):
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        if suffix:
            v *= _MULT[suffix.lower()]
        vals.append(v)
    return vals


def derivable_numbers(df: pd.DataFrame, cap: int = 5000) -> list[float]:
    vals: list[float] = [float(len(df))]
    for col in df.select_dtypes(include="number").columns:
        s = df[col].dropna().astype(float)
        if s.empty:
            continue
        vals += [s.sum(), s.mean(), s.min(), s.max(), float(s.count())]
        vals += s.head(cap).tolist()
        total = s.sum()
        if total:
            vals += (s.head(cap) / total * 100).tolist()
    # also numbers appearing inside text cells (e.g. years, ids as labels)
    for col in df.select_dtypes(exclude="number").columns:
        for cell in df[col].dropna().astype(str).head(cap):
            vals += numbers_in_text(cell)
    return vals


def ungrounded(summary: str, df: pd.DataFrame) -> list[float]:
    real = derivable_numbers(df)
    bad = []
    for n in numbers_in_text(summary):
        if abs(n) <= 1:
            continue
        if not any(abs(n - r) <= max(1.0, 0.005 * abs(r)) for r in real):
            bad.append(n)
    return sorted(set(bad))
