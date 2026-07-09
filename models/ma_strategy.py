from __future__ import annotations

import numpy as np
import pandas as pd

from models.indicators import add_indicators
from models.probability import forward_returns_after_condition, outcome_stats


MA_CONFIG = {
    5: ("5日均线短线买入评估", "适合短线交易"),
    10: ("10日均线趋势买入评估", "趋势确认"),
    20: ("20日均线波段买入评估", "最佳波段参考"),
    30: ("30日均线中期买入评估", "安全边际较高"),
}


def analyze_ma_buying(df: pd.DataFrame) -> dict[str, object]:
    data = add_indicators(df).sort_values("date").copy()
    rows = [_analyze_one_ma(data, window) for window in MA_CONFIG]
    table = pd.DataFrame(rows)
    ranking = table.sort_values("买入评分", ascending=False).reset_index(drop=True)
    return {
        "评估表": table,
        "四周期买入排名": ranking[["均线周期", "交易定位", "买入评分", "风险等级", "历史上涨概率", "结论"]],
    }


def _analyze_one_ma(data: pd.DataFrame, window: int) -> dict[str, object]:
    ma_col = f"ma{window}"
    latest = data.iloc[-1]
    current = float(latest["close"])
    ma_value = float(latest[ma_col])
    distance = (current / ma_value - 1) * 100 if ma_value else 0
    direction = _ma_direction(data[ma_col])
    support_strength, touch_count = _support_strength(data, ma_col)
    returns = _pullback_returns(data, ma_col)
    stats = outcome_stats(returns)
    win_rate = _parse_pct(str(stats["胜率"]))
    score = _buy_score(distance, direction, support_strength, win_rate)
    risk = _risk_level(score, distance)
    title, position = MA_CONFIG[window]
    return {
        "模块名称": title,
        "均线周期": f"{window}日均线",
        "交易定位": position,
        "当前价格": round(current, 2),
        f"MA{window}": round(ma_value, 2),
        "距离均线": f"{distance:.2f}%",
        "均线方向": direction,
        "均线支撑强度": support_strength,
        "历史回踩次数": touch_count,
        "历史上涨概率": stats["胜率"],
        "历史平均收益": stats["平均收益"],
        "历史最大回撤": stats["最大回撤"],
        "买入评分": score,
        "星级": _stars(score),
        "风险等级": risk,
        "结论": _conclusion(window, score, distance, direction),
    }


def _ma_direction(ma: pd.Series) -> str:
    if len(ma.dropna()) < 4:
        return "数据不足"
    delta = float(ma.iloc[-1] - ma.iloc[-4])
    if delta > 0:
        return "向上"
    if delta < 0:
        return "向下"
    return "走平"


def _support_strength(data: pd.DataFrame, ma_col: str) -> tuple[str, int]:
    sample = data.tail(120).copy()
    touch = (sample["low"] <= sample[ma_col] * 1.01) & (sample["close"] >= sample[ma_col] * 0.995)
    count = int(touch.sum())
    if count >= 18:
        return "强", count
    if count >= 8:
        return "中", count
    return "弱", count


def _pullback_returns(data: pd.DataFrame, ma_col: str) -> pd.Series:
    touch = (data["low"] <= data[ma_col] * 1.012) & (data["close"] >= data[ma_col] * 0.99)
    return forward_returns_after_condition(data, touch, forward_days=3, period=250)


def _buy_score(distance: float, direction: str, support_strength: str, win_rate: float) -> float:
    distance_score = max(0, 30 - abs(distance) * 3)
    direction_score = {"向上": 25, "走平": 15, "向下": 5}.get(direction, 10)
    support_score = {"强": 25, "中": 16, "弱": 8}.get(support_strength, 8)
    probability_score = win_rate * 0.2
    return round(float(np.clip(distance_score + direction_score + support_score + probability_score, 0, 100)), 1)


def _risk_level(score: float, distance: float) -> str:
    if distance > 8:
        return "追高风险"
    if score >= 75:
        return "低风险"
    if score >= 60:
        return "中低风险"
    if score >= 45:
        return "中等风险"
    return "高风险"


def _conclusion(window: int, score: float, distance: float, direction: str) -> str:
    _, position = MA_CONFIG[window]
    if score >= 75 and abs(distance) <= 3 and direction != "向下":
        return f"{position}，当前接近均线且历史胜率较好。"
    if distance > 6:
        return f"{position}，但当前距离均线偏远，等待回踩更稳。"
    if direction == "向下":
        return f"{position}，但均线方向转弱，先观察企稳。"
    return f"{position}，可作为辅助参考。"


def _stars(score: float) -> str:
    full = int(round(score / 20))
    full = max(0, min(5, full))
    return "★" * full + "☆" * (5 - full)


def _parse_pct(value: str) -> float:
    try:
        return float(value.replace("%", ""))
    except ValueError:
        return 0.0
