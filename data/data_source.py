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
