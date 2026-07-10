from __future__ import annotations

import pandas as pd

from models.opening_pattern import classify_gap


def analyze_auction(df: pd.DataFrame, window: int = 60) -> dict[str, object]:
    data = df.sort_values("date").reset_index(drop=True)
    if len(data) < 2:
        return _empty()

    latest = data.iloc[-1]
    previous = data.iloc[-2]
    previous_close = float(previous["close"])
    auction_price = float(latest["open"])
    gap_pct = (auction_price / previous_close - 1) * 100 if previous_close else 0
    gap_type = classify_gap(gap_pct)
    volume_avg = data["volume"].tail(20).mean()
    auction_volume = float(latest["volume"]) * 0.08
    auction_amount = auction_volume * auction_price * 100
    auction_ratio = auction_volume / (volume_avg * 0.08) if volume_avg else 1.0

    similar = _similar_gap_stats(data.tail(window + 1), gap_type)
    period_stats = _gap_period_stats(data)
    return {
        "昨日收盘价": round(previous_close, 2),
        "今日竞价价格": round(auction_price, 2),
        "竞价涨跌幅": round(gap_pct, 2),
        "开盘类型": gap_type,
        "竞价成交量": round(auction_volume, 0),
        "竞价成交额": round(auction_amount, 0),
        "竞价量比": round(auction_ratio, 2),
        "今日可能走势": _expected_move(gap_type, similar),
        **similar,
        "历史分周期统计": period_stats,
        "数据说明": "未接入真实 Level-2 集合竞价，当前用今日开盘价与估算竞价量近似分析。",
    }


def _similar_gap_stats(data: pd.DataFrame, gap_type: str) -> dict[str, object]:
    counts = {
        "高开高走次数": 0,
        "高开低走次数": 0,
        "平开上涨次数": 0,
        "平开下跌次数": 0,
        "低开高走次数": 0,
        "低开低走次数": 0,
    }
    total = 0
    for index in range(1, len(data)):
        previous_close = float(data.iloc[index - 1]["close"])
        today_open = float(data.iloc[index]["open"])
        today_close = float(data.iloc[index]["close"])
        current_gap = classify_gap((today_open / previous_close - 1) * 100 if previous_close else 0)
        if current_gap != gap_type:
            continue
        total += 1
        is_up = today_close >= today_open
        if current_gap == "高开":
            counts["高开高走次数" if is_up else "高开低走次数"] += 1
        elif current_gap == "平开":
            counts["平开上涨次数" if is_up else "平开下跌次数"] += 1
        elif current_gap == "低开":
            counts["低开高走次数" if is_up else "低开低走次数"] += 1

    if gap_type == "高开":
        good = counts["高开高走次数"]
        bad = counts["高开低走次数"]
    elif gap_type == "平开":
        good = counts["平开上涨次数"]
        bad = counts["平开下跌次数"]
    elif gap_type == "低开":
        good = counts["低开高走次数"]
        bad = counts["低开低走次数"]
    else:
        good = 0
        bad = 0

    probability = round(good / total * 100, 1) if total else 0
    return {
        **counts,
        "历史相似次数": total,
        "顺势概率": probability,
        "反向次数": bad,
    }


def _gap_period_stats(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for period in [20, 60, 250]:
        sample = data.tail(period + 1)
        for current_gap in ["高开", "平开", "低开"]:
            stats = _similar_gap_stats(sample, current_gap)
            success = int(stats["历史相似次数"]) - int(stats["反向次数"])
            rows.append(
                {
                    "统计周期": f"近{period}个交易日",
                    "开盘类型": current_gap,
                    "样本数量": stats["历史相似次数"],
                    "成功次数": success,
                    "失败次数": stats["反向次数"],
                    "上涨概率": f"{float(stats['顺势概率']):.1f}%",
                    "高开高走次数": stats["高开高走次数"],
                    "高开低走次数": stats["高开低走次数"],
                    "平开上涨次数": stats["平开上涨次数"],
                    "平开下跌次数": stats["平开下跌次数"],
                    "低开高走次数": stats["低开高走次数"],
                    "低开低走次数": stats["低开低走次数"],
                }
            )
    return pd.DataFrame(rows)


def auction_type_probability_summary(period_stats: pd.DataFrame, period: str = "近60个交易日") -> pd.DataFrame:
    if period_stats.empty:
        return pd.DataFrame()
    sample = period_stats[period_stats["统计周期"] == period].copy()
    if sample.empty:
        sample = period_stats.copy()
    sample = sample[sample["开盘类型"].isin(["高开", "平开", "低开"])]
    return sample[["开盘类型", "样本数量", "成功次数", "失败次数", "上涨概率"]].reset_index(drop=True)


def has_all_opening_type_stats(period_stats: pd.DataFrame, period: str = "近60个交易日") -> bool:
    if period_stats.empty:
        return False
    sample = period_stats[period_stats["统计周期"] == period]
    return {"高开", "平开", "低开"}.issubset(set(sample["开盘类型"]))


def _expected_move(gap_type: str, stats: dict[str, object]) -> str:
    probability = float(stats["顺势概率"])
    if gap_type == "平开":
        return "平开震荡，重点观察成交量是否放大"
    if probability >= 65:
        return f"{gap_type}后延续概率较高"
    if probability <= 35:
        return f"{gap_type}后回落或反向概率较高"
    return f"{gap_type}后方向不明，适合等待确认"


def _empty() -> dict[str, object]:
    return {
        "昨日收盘价": 0,
        "今日竞价价格": 0,
        "竞价涨跌幅": 0,
        "开盘类型": "数据不足",
        "竞价成交量": 0,
        "竞价成交额": 0,
        "竞价量比": 0,
        "今日可能走势": "数据不足",
        "高开高走次数": 0,
        "高开低走次数": 0,
        "平开上涨次数": 0,
        "平开下跌次数": 0,
        "低开高走次数": 0,
        "低开低走次数": 0,
        "历史相似次数": 0,
        "顺势概率": 0,
        "反向次数": 0,
        "历史分周期统计": pd.DataFrame(),
        "数据说明": "数据不足",
    }
