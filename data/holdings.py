from __future__ import annotations

from pathlib import Path

import pandas as pd


HOLDINGS_FILE = Path(__file__).resolve().parent / "personal_holdings.csv"
HOLDING_COLUMNS = ["股票代码", "股票名称", "成本价格", "持仓数量"]


def load_holdings() -> pd.DataFrame:
    if not HOLDINGS_FILE.exists():
        return empty_holdings()
    try:
        data = pd.read_csv(HOLDINGS_FILE, dtype={"股票代码": str})
        return normalize_holdings(data)
    except Exception:
        return empty_holdings()


def save_holdings(data: pd.DataFrame) -> pd.DataFrame:
    clean = normalize_holdings(data)
    clean.to_csv(HOLDINGS_FILE, index=False, encoding="utf-8-sig")
    return clean


def empty_holdings() -> pd.DataFrame:
    return pd.DataFrame(columns=HOLDING_COLUMNS)


def normalize_holdings(data: pd.DataFrame) -> pd.DataFrame:
    if data is None or data.empty:
        return empty_holdings()
    clean = data.copy()
    for column in HOLDING_COLUMNS:
        if column not in clean.columns:
            clean[column] = "" if column in {"股票代码", "股票名称"} else 0
    clean = clean[HOLDING_COLUMNS]
    clean["股票代码"] = clean["股票代码"].astype(str).str.extract(r"(\d{6})", expand=False).fillna("")
    clean["股票名称"] = clean["股票名称"].fillna("").astype(str)
    clean["成本价格"] = pd.to_numeric(clean["成本价格"], errors="coerce").fillna(0.0)
    clean["持仓数量"] = pd.to_numeric(clean["持仓数量"], errors="coerce").fillna(0).astype(int)
    clean = clean[(clean["股票代码"] != "") & (clean["成本价格"] > 0) & (clean["持仓数量"] > 0)]
    clean = clean.drop_duplicates(subset=["股票代码"], keep="last").reset_index(drop=True)
    return clean
