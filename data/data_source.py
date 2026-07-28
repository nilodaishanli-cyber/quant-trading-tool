from __future__ import annotations

from typing import Protocol

import pandas as pd

from data.providers.akshare_provider import StockFetchResult, fetch_stock_history
from data.realtime_market import RealtimeFetchResult
from data.realtime_market import fetch_intraday_minutes
from data.realtime_market import fetch_realtime_indexes
from data.realtime_market import fetch_realtime_quotes


class MarketDataSource(Protocol):
    name: str

    def history(self, code: str, days: int) -> StockFetchResult:
        ...

    def realtime_quotes(self, codes: list[str]) -> RealtimeFetchResult:
        ...

    def intraday_minutes(self, code: str) -> pd.DataFrame:
        ...

    def realtime_indexes(self) -> RealtimeFetchResult:
        ...


class AkShareDataSource:
    name = "AkShare免费行情"

    def history(self, code: str, days: int) -> StockFetchResult:
        return fetch_stock_history(code, days=days)

    def realtime_quotes(self, codes: list[str]) -> RealtimeFetchResult:
        return fetch_realtime_quotes(codes)

    def intraday_minutes(self, code: str) -> pd.DataFrame:
        return fetch_intraday_minutes(code)

    def realtime_indexes(self) -> RealtimeFetchResult:
        return fetch_realtime_indexes()


def get_data_source(name: str = "akshare") -> MarketDataSource:
    if name != "akshare":
        raise ValueError(f"暂不支持的数据源: {name}")
    return AkShareDataSource()


def fetch_quote_with_fallback(code: str) -> dict[str, object]:
    stock_code = str(code).strip().zfill(6)
    source = get_data_source()
    quote_result = source.realtime_quotes([stock_code])
    if not quote_result.data.empty:
        row = quote_result.data.iloc[0]
        price = _safe_float(row.get("当前价格"))
        pct_change = _safe_float(row.get("实时涨跌"))
        return {
            "code": stock_code,
            "price": price,
            "pct_change": pct_change,
            "source": quote_result.source,
            "error": quote_result.error,
        }

    history_result = source.history(stock_code, days=260)
    if history_result.error or history_result.data.empty:
        return {
            "code": stock_code,
            "price": None,
            "pct_change": None,
            "source": history_result.source,
            "error": history_result.error or quote_result.error,
        }

    latest = history_result.data.iloc[-1]
    return {
        "code": stock_code,
        "price": _safe_float(latest.get("close")),
        "pct_change": _safe_float(latest.get("pct_change")),
        "source": history_result.source,
        "error": quote_result.error,
    }


def _safe_float(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
