from __future__ import annotations

import pandas as pd


STAT_PERIODS = [20, 60, 250]


def outcome_stats(returns: pd.Series) -> dict[str, object]:
    clean = returns.dropna()
    if clean.empty:
        return {
            "出现次数": 0,
            "成功次数": 0,
            "失败次数": 0,
            "胜率": "0.0%",
            "平均收益": "0.00%",
            "最大涨幅": "0.00%",
            "最大回撤": "0.00%",
        }

    success = int((clean > 0).sum())
    total = int(len(clean))
    failure = total - success
    return {
        "出现次数": total,
        "成功次数": success,
        "失败次数": failure,
        "胜率": f"{success / total * 100:.1f}%",
        "平均收益": f"{clean.mean():.2f}%",
        "最大涨幅": f"{clean.max():.2f}%",
        "最大回撤": f"{clean.min():.2f}%",
    }


def historical_probability_database(df: pd.DataFrame) -> pd.DataFrame:
    data = df.sort_values("date").copy()
    data["次日收益"] = data["close"].pct_change().shift(-1) * 100
    data["五日收益"] = (data["close"].shift(-5) / data["close"] - 1) * 100
    rows: list[dict[str, object]] = []

    for period in STAT_PERIODS:
        sample = data.tail(period)
        rows.append({"统计周期": f"近{period}个交易日", "场景": "次日上涨概率", **outcome_stats(sample["次日收益"])})
        rows.append({"统计周期": f"近{period}个交易日", "场景": "5日波段收益概率", **outcome_stats(sample["五日收益"])})

    return pd.DataFrame(rows)


def yellow_line_probability_database(df: pd.DataFrame) -> pd.DataFrame:
    data = df.sort_values("date").copy()
    if data.empty:
        return pd.DataFrame()
    avg_line = data.apply(_daily_vwap_proxy, axis=1)
    volume_ratio = data["volume"] / data["volume"].rolling(20).mean()
    breakout = (data["close"] > avg_line) & (data["open"] <= avg_line) & (volume_ratio >= 1)
    breakdown = (data["close"] < avg_line) & (data["open"] >= avg_line) & (volume_ratio >= 1)
    rows: list[dict[str, object]] = []
    for period in STAT_PERIODS:
        rows.append(
            {
                "统计周期": f"近{period}个交易日",
                "场景": "价格放量突破分时黄线",
                **_event_stats(data, breakout, period, forward_days=1, reverse=False),
            }
        )
        rows.append(
            {
                "统计周期": f"近{period}个交易日",
                "场景": "价格放量跌破分时黄线",
                **_event_stats(data, breakdown, period, forward_days=1, reverse=True),
            }
        )
    return pd.DataFrame(rows)


def forward_returns_after_condition(
    data: pd.DataFrame,
    condition: pd.Series,
    forward_days: int = 3,
    period: int = 250,
) -> pd.Series:
    sample = data.sort_values("date").tail(period).copy()
    aligned_condition = condition.reindex(sample.index).fillna(False)
    future_return = (sample["close"].shift(-forward_days) / sample["close"] - 1) * 100
    return future_return[aligned_condition]


def _event_stats(
    data: pd.DataFrame,
    condition: pd.Series,
    period: int,
    forward_days: int,
    reverse: bool,
) -> dict[str, object]:
    returns = forward_returns_after_condition(data, condition, forward_days=forward_days, period=period)
    if reverse:
        returns = -returns
    stats = outcome_stats(returns)
    return {
        "出现次数": stats["出现次数"],
        "上涨次数" if not reverse else "下跌次数": stats["成功次数"],
        "下跌次数" if not reverse else "反弹次数": stats["失败次数"],
        "上涨概率" if not reverse else "继续下跌概率": stats["胜率"],
        "平均涨幅" if not reverse else "平均跌幅": stats["平均收益"],
        "最大上涨" if not reverse else "最大下跌": stats["最大涨幅"],
        "最大回撤": stats["最大回撤"],
        "数据口径": "免费源无法稳定回放250日逐分钟黄线，当前用日内均价线代理事件做历史统计。",
    }


def _daily_vwap_proxy(row: pd.Series) -> float:
    amount = float(row.get("amount", 0) or 0)
    volume = float(row.get("volume", 0) or 0)
    if amount > 0 and volume > 0:
        return amount / volume / 100
    return float((row["high"] + row["low"] + row["close"]) / 3)
