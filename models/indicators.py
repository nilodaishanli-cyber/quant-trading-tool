from __future__ import annotations

import numpy as np
import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    for window in [5, 10, 20, 30]:
        data[f"ma{window}"] = data["close"].rolling(window=window, min_periods=1).mean()

    previous_close = data["close"].shift(1)
    true_range = pd.concat(
        [
            data["high"] - data["low"],
            (data["high"] - previous_close).abs(),
            (data["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["atr"] = true_range.rolling(window=14, min_periods=1).mean()
    data["ma20_deviation_pct"] = _safe_pct(data["close"], data["ma20"])
    data["ma30_deviation_pct"] = _safe_pct(data["close"], data["ma30"])
    data["avg_price_20"] = data["close"].rolling(window=20, min_periods=1).mean()
    data["avg_price_30"] = data["close"].rolling(window=30, min_periods=1).mean()
    data["high_20"] = data["high"].rolling(window=20, min_periods=1).max()
    data["low_20"] = data["low"].rolling(window=20, min_periods=1).min()
    data["volume_avg_20"] = data["volume"].rolling(window=20, min_periods=1).mean()
    return data


def _safe_pct(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return np.where(denominator == 0, np.nan, (numerator / denominator - 1) * 100)


def latest_metrics(df: pd.DataFrame) -> dict[str, float]:
    latest = add_indicators(df).iloc[-1]
    return {
        "current_price": float(latest["close"]),
        "ma5": float(latest["ma5"]),
        "ma10": float(latest["ma10"]),
        "ma20": float(latest["ma20"]),
        "ma30": float(latest["ma30"]),
        "ma20_deviation_pct": float(latest["ma20_deviation_pct"]),
        "ma30_deviation_pct": float(latest["ma30_deviation_pct"]),
        "avg_price_20": float(latest["avg_price_20"]),
        "avg_price_30": float(latest["avg_price_30"]),
        "high_20": float(latest["high_20"]),
        "low_20": float(latest["low_20"]),
        "atr": float(latest["atr"]),
        "volume_avg_20": float(latest["volume_avg_20"]),
    }
