from __future__ import annotations

import re
from io import StringIO
from typing import Iterable

import pandas as pd


def parse_stock_codes(raw_text: str) -> list[str]:
    """Parse user pasted stock codes and keep stable order."""
    tokens = re.split(r"[\s,，;；、]+", raw_text.strip())
    seen: set[str] = set()
    codes: list[str] = []
    for token in tokens:
        code = normalize_stock_code(token)
        if code and code not in seen:
            codes.append(code)
            seen.add(code)
    return codes


def normalize_stock_code(raw_code: str) -> str | None:
    digits = re.sub(r"\D", "", raw_code)
    if len(digits) < 6:
        return None
    return digits[-6:]


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = StringIO()
    df.to_csv(buffer, index=False, encoding="utf-8-sig")
    return buffer.getvalue().encode("utf-8-sig")


def first_non_empty(values: Iterable[str | None], fallback: str = "") -> str:
    for value in values:
        if value:
            return value
    return fallback
