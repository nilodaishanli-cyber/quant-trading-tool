from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import logging
from pathlib import Path
import time
from typing import Literal

import pandas as pd


logger = logging.getLogger(__name__)
ProviderName = Literal["akshare"]
CACHE_DIR = Path(__file__).resolve().parents[1] / "history_cache"


@dataclass
class StockFetchResult:
    code: str
    data: pd.DataFrame
    error: str | None = None
    source: str | None = None


REQUIRED_COLUMNS = {
    "date": "date",
    "open": "open",
    "close": "close",
    "high": "high",
    "low": "low",
    "volume": "volume",
    "amount": "amount",
    "pct_change": "pct_change",
}

CORE_PRICE_COLUMNS = ["date", "open", "close", "high", "low"]

COMMON_STOCK_NAMES = {
    "000001": "平安银行",
    "002384": "东山精密",
    "002463": "沪电股份",
    "300750": "宁德时代",
    "600519": "贵州茅台",
}


def fetch_stock_history(code: str, days: int = 30, provider: ProviderName = "akshare") -> StockFetchResult:
    if provider != "akshare":
        return StockFetchResult(code=code, data=pd.DataFrame(), error=f"暂不支持的数据源: {provider}")

    errors: list[str] = []
    try:
        raw = _fetch_with_retry(lambda: _fetch_akshare_history_tx(code, days=days), retries=2)
        _log_raw_history("Tencent", code, raw)
        data = normalize_history_frame(raw)
        if data.empty:
            raise ValueError("腾讯接口未返回行情数据")
        data = data.tail(days).reset_index(drop=True)
        _save_history_cache(code, data)
        return StockFetchResult(code=code, data=data, source="akshare/tencent")
    except Exception as exc:  # noqa: BLE001 - surface provider errors to the UI.
        logger.exception("腾讯接口失败: %s", code)
        errors.append(f"腾讯接口失败: {_short_error(exc)}")

    try:
        raw = _fetch_with_retry(lambda: _fetch_akshare_history_em(code, days=days), retries=2)
        _log_raw_history("Eastmoney", code, raw)
        data = normalize_history_frame(raw)
        if data.empty:
            raise ValueError("东方财富接口未返回行情数据")
        data = data.tail(days).reset_index(drop=True)
        _save_history_cache(code, data)
        return StockFetchResult(code=code, data=data, source="akshare/eastmoney")
    except Exception as exc:  # noqa: BLE001 - surface provider errors to the UI.
        logger.exception("东方财富备用接口失败: %s", code)
        errors.append(f"东方财富备用接口失败: {_short_error(exc)}")

    cached = _load_history_cache(code, days)
    if not cached.empty:
        return StockFetchResult(code=code, data=cached, source="本地最近成功缓存")
    return StockFetchResult(code=code, data=pd.DataFrame(), error="；".join(errors))


def _fetch_akshare_history_em(code: str, days: int) -> pd.DataFrame:
    import akshare as ak

    end_date = date.today()
    start_date = end_date - timedelta(days=max(days * 3, 120))
    return ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        adjust="qfq",
    )


def _fetch_akshare_history_tx(code: str, days: int) -> pd.DataFrame:
    import akshare as ak

    end_date = date.today()
    start_date = end_date - timedelta(days=max(days * 3, 120))
    return ak.stock_zh_a_hist_tx(
        symbol=to_prefixed_market_symbol(code),
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        adjust="qfq",
        timeout=15,
    )


def _fetch_with_retry(fetcher, retries: int) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return fetcher()
        except Exception as exc:  # noqa: BLE001 - retry provider/network errors.
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.8 * (attempt + 1))
    if last_error:
        raise last_error
    return pd.DataFrame()


def to_prefixed_market_symbol(code: str) -> str:
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    return f"sz{code}"


def fetch_stock_names(codes: list[str]) -> dict[str, str]:
    return {code: COMMON_STOCK_NAMES.get(code, "名称待获取") for code in codes}


def _log_raw_history(source: str, stock_code: str, df: pd.DataFrame) -> None:
    if df.empty:
        logger.info("%s raw columns for %s: []", source, stock_code)
        logger.info("%s last rows for %s: []", source, stock_code)
        return
    logger.info(
        "%s raw columns for %s: %s",
        source,
        stock_code,
        list(df.columns),
    )
    logger.info(
        "%s last rows for %s: %s",
        source,
        stock_code,
        df.tail(2).to_dict("records"),
    )


def normalize_history_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=list(REQUIRED_COLUMNS))

    df = raw.copy()
    rename_map = {
        "日期": "date",
        "交易日期": "date",
        "开盘": "open",
        "开盘价": "open",
        "收盘": "close",
        "收盘价": "close",
        "最新价": "close",
        "最高": "high",
        "最高价": "high",
        "最低": "low",
        "最低价": "low",
        "成交量": "volume",
        "成交量(手)": "volume",
        "成交额": "amount",
        "成交额(元)": "amount",
        "涨跌幅": "pct_change",
        "涨跌幅(%)": "pct_change",
    }
    df = df.rename(columns=rename_map)
    missing = [column for column in CORE_PRICE_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"行情字段缺失: {', '.join(missing)}")

    df["date"] = pd.to_datetime(df["date"])
    for column in ["open", "close", "high", "low"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    else:
        df["volume"] = pd.NA

    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    else:
        df["amount"] = pd.NA

    computed_pct_change = df["close"].pct_change() * 100
    if "pct_change" in df.columns:
        df["pct_change"] = pd.to_numeric(df["pct_change"], errors="coerce").combine_first(computed_pct_change)
    else:
        df["pct_change"] = computed_pct_change

    df = df[list(REQUIRED_COLUMNS)]
    return df.dropna(subset=["date", "open", "close", "high", "low"]).sort_values("date")


def _history_cache_path(code: str) -> Path:
    return CACHE_DIR / f"{code}.csv"


def _save_history_cache(code: str, data: pd.DataFrame) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data.to_csv(_history_cache_path(code), index=False, encoding="utf-8-sig")
    except Exception:  # noqa: BLE001 - cache failure must not affect analysis.
        logger.exception("保存历史行情缓存失败: %s", code)


def _load_history_cache(code: str, days: int) -> pd.DataFrame:
    try:
        path = _history_cache_path(code)
        if not path.exists():
            return pd.DataFrame(columns=list(REQUIRED_COLUMNS))
        data = pd.read_csv(path)
        return normalize_history_frame(data).tail(days).reset_index(drop=True)
    except Exception:  # noqa: BLE001 - cache failure must not affect analysis.
        logger.exception("读取历史行情缓存失败: %s", code)
        return pd.DataFrame(columns=list(REQUIRED_COLUMNS))


def _short_error(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    if not message:
        message = exc.__class__.__name__
    return message[:180]
