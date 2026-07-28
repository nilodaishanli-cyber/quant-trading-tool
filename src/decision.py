from __future__ import annotations

import numpy as np
import pandas as pd

from src.auction import analyze_auction
from src.buy_strategy import build_buy_strategy
from src.indicators import add_indicators
from src.intraday import analyze_morning_direction
from src.ma_strategy import analyze_ma_buying
from src.probability import historical_probability_database
from src.probability_stats import find_similar_trends
from src.risk import calculate_risk_and_buy_zone


def build_decision(
    code: str,
    name: str,
    history: pd.DataFrame,
    market_score: float,
    data_source: str | None,
) -> dict[str, object]:
    data = add_indicators(history)
    latest = data.iloc[-1]
    risk = calculate_risk_and_buy_zone(data)
    auction = analyze_auction(data)
    ma_buying = analyze_ma_buying(data)
    morning = analyze_morning_direction(data)
    probability_db = historical_probability_database(data)
    similar = find_similar_trends(data)
    technical_score = _technical_score(data)
    capital_score = _capital_score(data)
    auction_score = _auction_score(auction)
    morning_adjust = _morning_adjust(morning)
    comprehensive = round(
        technical_score * 0.34 + market_score * 0.2 + capital_score * 0.18 + auction_score * 0.16 + morning_adjust * 0.12,
        1,
    )
    adjusted_risk = _adjust_risk(float(risk["risk_score"]), market_score)
    return {
        "股票名称": name,
        "股票代码": code,
        "数据源": _source_name(data_source),
        "当前价格": round(float(latest["close"]), 2),
        "今日涨跌": _format_pct(latest.get("pct_change")),
        "综合评分": comprehensive,
        "市场环境评分": round(float(market_score), 1),
        "技术评分": technical_score,
        "资金评分": capital_score,
        "竞价评分": auction_score,
        "风险评分": adjusted_risk,
        "风险等级": _risk_level(adjusted_risk),
        "建议操作": _suggest_action(comprehensive, adjusted_risk),
        "竞价分析": auction,
        "四周期买入评估": ma_buying,
        "早盘方向预测": morning,
        "历史概率数据库": probability_db,
        "买入策略": build_buy_strategy(data),
        "历史相似走势": similar,
        "详细风险": risk,
    }


def _technical_score(data: pd.DataFrame) -> float:
    latest = data.iloc[-1]
    score = 50
    score += 12 if latest["close"] >= latest["ma20"] else -8
    score += 10 if latest["ma5"] >= latest["ma10"] else -6
    score += 8 if latest["ma10"] >= latest["ma20"] else -5
    score -= min(abs(float(latest["ma20_deviation_pct"])), 18) * 0.5
    return round(float(np.clip(score, 0, 100)), 1)


def _capital_score(data: pd.DataFrame) -> float:
    latest = data.iloc[-1]
    volume_avg = float(latest["volume_avg_20"] or 0)
    volume_ratio = float(latest["volume"] / volume_avg) if volume_avg else 1
    pct_change = _safe_float(latest.get("pct_change"), 0.0)
    score = 50 + min(max(volume_ratio - 1, -1), 2) * 18 + max(min(pct_change, 5), -5) * 3
    return round(float(np.clip(score, 0, 100)), 1)


def _auction_score(auction: dict[str, object]) -> float:
    probability = float(auction.get("顺势概率", 0) or 0)
    ratio = float(auction.get("竞价量比", 1) or 1)
    score = 45 + (probability - 50) * 0.5 + min(max(ratio - 1, -1), 3) * 8
    return round(float(np.clip(score, 0, 100)), 1)


def _morning_adjust(morning: dict[str, object]) -> float:
    up = _pct_to_float(str(morning.get("上涨概率", "50%")))
    down = _pct_to_float(str(morning.get("下跌概率", "50%")))
    signal = str(morning.get("最终判断", "震荡"))
    base = 50 + (up - down) * 0.35
    if signal == "偏多":
        base += 10
    elif signal == "偏空":
        base -= 10
    return round(float(np.clip(base, 0, 100)), 1)


def _adjust_risk(risk_score: float, market_score: float) -> float:
    market_adjust = (50 - market_score) * 0.25
    return round(float(np.clip(risk_score + market_adjust, 0, 100)), 1)


def _risk_level(score: float) -> str:
    if score < 25:
        return "低风险"
    if score < 45:
        return "中低风险"
    if score < 65:
        return "中等风险"
    if score < 80:
        return "较高风险"
    return "高风险"


def _suggest_action(score: float, risk: float) -> str:
    if risk >= 70:
        return "风险偏高，避免追高，等待回落。"
    if score >= 75 and risk <= 45:
        return "趋势较好，可按平衡买入区域分批关注。"
    if score >= 60:
        return "等待回调买入，突破确认后再加仓。"
    return "观望为主，等待趋势和成交量改善。"


def _source_name(source: str | None) -> str:
    return {
        "akshare/eastmoney": "东方财富行情",
        "akshare/tencent": "腾讯备用行情",
    }.get(source or "", "未知数据源")


def _pct_to_float(value: str) -> float:
    try:
        return float(value.replace("%", ""))
    except ValueError:
        return 50.0


def _safe_float(value: object, fallback: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _format_pct(value: object) -> str:
    try:
        if pd.isna(value):
            return "--"
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "--"
