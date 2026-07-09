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
