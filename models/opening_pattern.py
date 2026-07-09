from __future__ import annotations

import pandas as pd


PATTERN_COLUMNS = [
    "gap_type",
    "high_open_rise_count",
    "high_open_fall_count",
    "low_open_rise_count",
    "low_open_fall_count",
    "flat_open_rise_count",
    "flat_open_fall_count",
]


def analyze_opening_patterns(df: pd.DataFrame, window: int = 20, flat_threshold_pct: float = 0.15) -> dict[str, int | str]:
    data = df.copy().sort_values("date").tail(window + 1)
    if len(data) < 2:
        return {
            "gap_type": "数据不足",
            "high_open_rise_count": 0,
            "high_open_fall_count": 0,
            "low_open_rise_count": 0,
            "low_open_fall_count": 0,
            "flat_open_rise_count": 0,
            "flat_open_fall_count": 0,
        }

    counts = {column: 0 for column in PATTERN_COLUMNS if column != "gap_type"}
    records = data.reset_index(drop=True)
    latest_gap = "数据不足"

    for index in range(1, len(records)):
        previous_close = float(records.loc[index - 1, "close"])
        today_open = float(records.loc[index, "open"])
        today_close = float(records.loc[index, "close"])
        gap_pct = (today_open / previous_close - 1) * 100 if previous_close else 0
        gap_type = classify_gap(gap_pct, flat_threshold_pct)
        direction_up = today_close >= today_open

        if gap_type == "高开":
            counts["high_open_rise_count" if direction_up else "high_open_fall_count"] += 1
        elif gap_type == "低开":
            counts["low_open_rise_count" if direction_up else "low_open_fall_count"] += 1
        else:
            counts["flat_open_rise_count" if direction_up else "flat_open_fall_count"] += 1
        latest_gap = gap_type

    return {"gap_type": latest_gap, **counts}


def classify_gap(gap_pct: float, flat_threshold_pct: float = 0.15) -> str:
    if gap_pct > flat_threshold_pct:
        return "高开"
    if gap_pct < -flat_threshold_pct:
        return "低开"
    return "平开"
