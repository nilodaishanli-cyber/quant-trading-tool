from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators import add_indicators


def calculate_risk_and_buy_zone(df: pd.DataFrame) -> dict[str, float | str]:
    data = add_indicators(df)
    latest = data.iloc[-1]
    current = float(latest["close"])
    ma20 = float(latest["ma20"])
    ma30 = float(latest["ma30"])
    low_20 = float(latest["low_20"])
    high_20 = float(latest["high_20"])
    atr = float(latest["atr"])
    volume_avg_20 = float(latest["volume_avg_20"] or 0)
    latest_volume = float(latest["volume"] or 0)

    valuation_deviation = max(0.0, (current / ma20 - 1) * 100) if ma20 else 0.0
    recent_gain = _recent_gain_pct(data, window=10)
    volatility_pct = (atr / current * 100) if current else 0.0
    support_distance_pct = ((current - low_20) / current * 100) if current else 0.0
    volume_ratio = (latest_volume / volume_avg_20) if volume_avg_20 else 1.0

    score = (
        min(valuation_deviation, 20) * 1.4
        + min(max(recent_gain, 0), 30) * 1.1
        + min(volatility_pct, 12) * 2.2
        + min(support_distance_pct, 25) * 0.8
        + min(max(volume_ratio - 1, 0) * 20, 20)
    )
    risk_score = round(float(np.clip(score, 0, 100)), 2)

    conservative = min(ma30, ma20 - 0.6 * atr)
    balanced = min(ma20, current - 0.35 * atr)
    aggressive = min(current, ma20 + 0.25 * atr)
    chase_line = max(high_20, ma20 + 1.5 * atr)

    return {
        "risk_score": risk_score,
        "risk_level": _risk_level(risk_score),
        "conservative_buy_price": round(max(conservative, 0), 2),
        "balanced_buy_price": round(max(balanced, 0), 2),
        "aggressive_buy_price": round(max(aggressive, 0), 2),
        "avoid_chasing_above": round(max(chase_line, 0), 2),
        "valuation_deviation_pct": round(valuation_deviation, 2),
        "recent_gain_pct": round(recent_gain, 2),
        "volatility_pct": round(volatility_pct, 2),
        "support_distance_pct": round(support_distance_pct, 2),
        "volume_ratio": round(volume_ratio, 2),
    }


def _recent_gain_pct(data: pd.DataFrame, window: int) -> float:
    if len(data) <= 1:
        return 0.0
    start = data["close"].iloc[max(0, len(data) - window - 1)]
    end = data["close"].iloc[-1]
    return float((end / start - 1) * 100) if start else 0.0


def _risk_level(score: float) -> str:
    if score < 25:
        return "低"
    if score < 50:
        return "中"
    if score < 75:
        return "高"
    return "极高"
