from __future__ import annotations

import pandas as pd


PERIODS = [20, 60, 250]


def historical_statistics(df: pd.DataFrame) -> pd.DataFrame:
    data = df.sort_values("date").copy()
    data["daily_pct"] = data["close"].pct_change() * 100
    rows: list[dict[str, object]] = []
    for period in PERIODS:
        sample = data.tail(period).dropna(subset=["daily_pct"])
        up = sample[sample["daily_pct"] > 0]["daily_pct"]
        down = sample[sample["daily_pct"] < 0]["daily_pct"]
        rows.append(
            {
                "统计周期": f"近{period}个交易日",
                "上涨次数": int((sample["daily_pct"] > 0).sum()),
                "下跌次数": int((sample["daily_pct"] < 0).sum()),
                "平均涨幅": _fmt(up.mean()),
                "平均跌幅": _fmt(down.mean()),
                "最大涨幅": _fmt(sample["daily_pct"].max()),
                "最大跌幅": _fmt(sample["daily_pct"].min()),
            }
        )
    return pd.DataFrame(rows)


def find_similar_trends(df: pd.DataFrame, lookback: int = 250) -> dict[str, object]:
    data = df.sort_values("date").copy().tail(lookback)
    if len(data) < 15:
        return {"历史相似走势": "数据不足", "相似次数": 0, "次日上涨概率": 0}

    data["pct_5"] = data["close"].pct_change(5) * 100
    data["volume_ratio"] = data["volume"] / data["volume"].rolling(20, min_periods=1).mean()
    latest = data.iloc[-1]
    similar = data[
        (data["pct_5"].sub(latest["pct_5"]).abs() <= 2.0)
        & (data["volume_ratio"].sub(latest["volume_ratio"]).abs() <= 0.5)
    ].copy()
    similar = similar.iloc[:-1]
    next_up = 0
    valid = 0
    for index in similar.index:
        loc = data.index.get_loc(index)
        if loc + 1 >= len(data):
            continue
        valid += 1
        next_up += int(data.iloc[loc + 1]["close"] > data.iloc[loc]["close"])
    probability = round(next_up / valid * 100, 1) if valid else 0
    return {
        "历史相似走势": f"近5日涨跌幅与成交量结构相近的走势出现 {valid} 次",
        "相似次数": valid,
        "次日上涨概率": probability,
    }


def _fmt(value: float) -> str:
    if pd.isna(value):
        return "0.00%"
    return f"{value:.2f}%"
