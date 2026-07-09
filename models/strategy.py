from __future__ import annotations

import numpy as np


def realtime_trade_strategy(
    base_decision: dict[str, object],
    intraday: dict[str, object],
    direction_1050: dict[str, object],
    market_score: float,
) -> dict[str, object]:
    base_score = float(base_decision.get("综合评分", 50) or 50)
    risk_score = float(base_decision.get("风险评分", 50) or 50)
    long_score = float(direction_1050.get("多方评分", 50) or 50)
    yellow_status = str(intraday.get("黄线状态", "数据不足"))

    score = base_score * 0.45 + long_score * 0.3 + market_score * 0.15 + (100 - risk_score) * 0.1
    score = round(float(np.clip(score, 0, 100)), 1)
    suggestion = _suggestion(score, risk_score, yellow_status, str(direction_1050.get("最终判断", "震荡")))
    return {
        "实时综合评分": score,
        "最终建议": suggestion,
        "建议说明": _reason(score, risk_score, yellow_status, direction_1050),
        "风险控制": _risk_control(yellow_status, str(direction_1050.get("最终判断", "震荡"))),
    }


def _suggestion(score: float, risk: float, yellow_status: str, signal: str) -> str:
    if risk >= 70 or signal == "偏空":
        return "风险退出"
    if signal == "偏多" and yellow_status == "站上黄线" and score >= 70:
        return "趋势确认"
    if yellow_status == "站上黄线" and score >= 58:
        return "等待回踩"
    return "观察"


def _reason(score: float, risk: float, yellow_status: str, direction_1050: dict[str, object]) -> str:
    return (
        f"实时综合评分{score:.1f}分，风险评分{risk:.1f}分，"
        f"分时黄线{yellow_status}，10:50方向为{direction_1050.get('最终判断', '震荡')}。"
    )


def _risk_control(yellow_status: str, signal: str) -> str:
    if signal == "偏多":
        return "若跌破分时黄线且成交量放大，盘中信号失效。"
    if signal == "偏空":
        return "若重新站上分时黄线并放量，空方信号失效。"
    if yellow_status == "跌破黄线":
        return "优先控制仓位，等待重新站上黄线。"
    return "震荡环境下不追高，靠近买入区域再观察。"
