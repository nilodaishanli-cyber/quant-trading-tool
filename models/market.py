from __future__ import annotations

import numpy as np
import pandas as pd

from data.realtime_market import fetch_realtime_indexes


def analyze_realtime_market() -> dict[str, object]:
    result = fetch_realtime_indexes()
    if result.error or result.data.empty:
        return {
            "score": 50.0,
            "status": "震荡市场",
            "indexes": pd.DataFrame(),
            "errors": [result.error] if result.error else [],
            "source": result.source,
            "limitations": result.limitations,
        }

    table = result.data.copy()
    table["趋势状态"] = table["实时涨跌"].apply(_trend_status)
    table["指数评分"] = table["实时涨跌"].apply(_score_from_pct)
    score = round(float(table["指数评分"].mean()), 1)
    return {
        "score": score,
        "status": _market_status(score),
        "indexes": table[["指数名称", "当前点位", "实时涨跌", "成交量", "成交额", "趋势状态", "指数评分", "更新时间"]],
        "errors": [],
        "source": result.source,
        "limitations": result.limitations,
    }


def _score_from_pct(pct: float) -> float:
    if pd.isna(pct):
        return 50.0
    return round(float(np.clip(50 + float(pct) * 12, 0, 100)), 1)


def _trend_status(pct: float) -> str:
    if pd.isna(pct):
        return "数据不足"
    if pct >= 1:
        return "强势上行"
    if pct >= 0.2:
        return "偏强震荡"
    if pct <= -1:
        return "弱势下行"
    if pct <= -0.2:
        return "偏弱震荡"
    return "窄幅震荡"


def _market_status(score: float) -> str:
    if score >= 65:
        return "强势市场"
    if score <= 40:
        return "弱势市场"
    return "震荡市场"
