from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.data_providers import normalize_history_frame


INDEXES = {
    "上证指数": "sh000001",
    "深证成指": "sz399001",
    "创业板指数": "sz399006",
    "科创50指数": "sh000688",
}


def fetch_market_environment(days: int = 80) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    errors: list[str] = []
    for name, symbol in INDEXES.items():
        try:
            history = _fetch_index_history(symbol, days)
            rows.append(_analyze_index(name, history))
        except Exception as exc:  # noqa: BLE001 - keep the dashboard usable.
            errors.append(f"{name}: {str(exc)[:120]}")

    if not rows:
        return {
            "score": 50,
            "status": "震荡市场",
            "indexes": pd.DataFrame(),
            "errors": errors,
        }

    table = pd.DataFrame(rows)
    score = round(float(table["指数评分"].mean()), 1)
    return {
        "score": score,
        "status": _market_status(score),
        "indexes": table,
        "errors": errors,
    }


def _fetch_index_history(symbol: str, days: int) -> pd.DataFrame:
    import akshare as ak

    end_date = date.today()
    start_date = end_date - timedelta(days=max(days * 3, 180))
    try:
        raw = ak.stock_zh_index_daily_em(
            symbol=symbol,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
    except Exception:  # noqa: BLE001 - Tencent is the fallback index source.
        raw = ak.stock_zh_index_daily_tx(
            symbol=symbol,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
    return normalize_history_frame(raw).tail(days).reset_index(drop=True)


def _analyze_index(name: str, history: pd.DataFrame) -> dict[str, object]:
    latest = history.iloc[-1]
    close = history["close"]
    volume = history["volume"]
    pct_today = _pct(close.iloc[-1], close.iloc[-2]) if len(close) >= 2 else 0
    trend_5 = _pct(close.iloc[-1], close.iloc[max(0, len(close) - 6)])
    trend_20 = _pct(close.iloc[-1], close.iloc[max(0, len(close) - 21)])
    volume_change = _pct(volume.iloc[-1], volume.tail(20).mean()) if len(volume) else 0
    score = 50 + trend_5 * 4 + trend_20 * 2 + pct_today * 5 + min(max(volume_change, -30), 30) * 0.25
    score = round(float(np.clip(score, 0, 100)), 1)
    return {
        "指数名称": name,
        "当前点位": round(float(latest["close"]), 2),
        "今日涨跌": f"{pct_today:.2f}%",
        "5日趋势": f"{trend_5:.2f}%",
        "20日趋势": f"{trend_20:.2f}%",
        "成交量变化": f"{volume_change:.2f}%",
        "指数评分": score,
    }


def _pct(current: float, base: float) -> float:
    return float((current / base - 1) * 100) if base else 0.0


def _market_status(score: float) -> str:
    if score >= 65:
        return "强势市场"
    if score <= 40:
        return "弱势市场"
    return "震荡市场"
