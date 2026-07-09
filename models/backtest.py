from __future__ import annotations

import pandas as pd


def simple_trend_backtest(df: pd.DataFrame) -> dict[str, object]:
    data = df.sort_values("date").copy()
    if len(data) < 30:
        return {"回测结论": "数据不足", "样本次数": 0, "胜率": "0.00%"}
    data["ma20"] = data["close"].rolling(20, min_periods=1).mean()
    signals = data[data["close"] > data["ma20"]].copy()
    wins = 0
    valid = 0
    for index in signals.index:
        loc = data.index.get_loc(index)
        if loc + 5 >= len(data):
            continue
        valid += 1
        wins += int(data.iloc[loc + 5]["close"] > data.iloc[loc]["close"])
    win_rate = wins / valid * 100 if valid else 0
    return {
        "回测结论": "站上20日均线后的5日表现统计",
        "样本次数": valid,
        "胜率": f"{win_rate:.2f}%",
    }
