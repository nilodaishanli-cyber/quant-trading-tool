from __future__ import annotations

import numpy as np
import pandas as pd

from models.auction import analyze_auction
from models.buy_strategy import build_buy_strategy
from models.backtest import simple_trend_backtest
from models.indicators import add_indicators
from models.intraday import analyze_morning_direction
from models.intraday import analyze_intraday_vwap, build_1050_direction
from models.ma_strategy import analyze_ma_buying
from models.probability import historical_probability_database
from models.probability_stats import find_similar_trends
from models.probability_stats import historical_statistics
from models.reason_analysis import analyze_today_reason
from models.risk import calculate_risk_and_buy_zone
from models.strategy import realtime_trade_strategy


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
        "历史走势统计": historical_statistics(data),
        "今日涨跌原因": analyze_today_reason(data, market_score),
        "历史回测": simple_trend_backtest(data),
        "买入策略": build_buy_strategy(data),
        "历史相似走势": similar,
        "详细风险": risk,
    }


def build_realtime_decision(
    base_decision: dict[str, object],
    history: pd.DataFrame,
    realtime_quote: dict[str, object] | None,
    intraday_minutes: pd.DataFrame,
    realtime_market: dict[str, object],
) -> dict[str, object]:
    market_score = float(realtime_market.get("score", base_decision.get("市场环境评分", 50)) or 50)
    auction = base_decision["竞价分析"]
    ma_buying = base_decision["四周期买入评估"]
    intraday = analyze_intraday_vwap(history, intraday_minutes, realtime_quote)
    direction_1050 = build_1050_direction(history, auction, intraday, market_score, ma_buying)
    strategy = realtime_trade_strategy(base_decision, intraday, direction_1050, market_score)
    quote = realtime_quote or {}
    current_price = _quote_float(quote, "当前价格", float(base_decision.get("当前价格", 0) or 0))
    realtime_pct = _quote_float(quote, "实时涨跌", _pct_to_float(str(base_decision.get("今日涨跌", "0%"))))
    return {
        "股票名称": base_decision["股票名称"],
        "股票代码": base_decision["股票代码"],
        "当前价格": round(current_price, 2),
        "实时涨跌": f"{realtime_pct:.2f}%",
        "开盘价": _quote_float(quote, "开盘价", 0),
        "最高价": _quote_float(quote, "最高价", 0),
        "最低价": _quote_float(quote, "最低价", 0),
        "成交量": _quote_float(quote, "成交量", 0),
        "成交额": _quote_float(quote, "成交额", 0),
        "换手率": _optional_pct(quote.get("换手率")),
        "市场环境": realtime_market.get("status", "震荡市场"),
        "市场环境评分": round(market_score, 1),
        "综合评分": strategy["实时综合评分"],
        "风险等级": base_decision["风险等级"],
        "风险评分": base_decision["风险评分"],
        "5日均线": _ma_status(ma_buying, "5日均线"),
        "10日均线": _ma_status(ma_buying, "10日均线"),
        "20日均线": _ma_status(ma_buying, "20日均线"),
        "30日均线": _ma_status(ma_buying, "30日均线"),
        "集合竞价": base_decision["早盘方向预测"].get("集合竞价", "中性"),
        "分时黄线": intraday["黄线状态"],
        "10:50方向": direction_1050["最终判断"],
        "上涨概率": direction_1050["上涨概率"],
        "下跌概率": direction_1050["下跌概率"],
        "最终建议": strategy["最终建议"],
        "建议说明": strategy["建议说明"],
        "风险控制": strategy["风险控制"],
        "实时行情": quote,
        "分时黄线分析": intraday,
        "10:50多空确认": direction_1050,
        "实时市场环境": realtime_market,
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


def _quote_float(quote: dict[str, object], key: str, fallback: float) -> float:
    try:
        value = quote.get(key, fallback)
        if pd.isna(value):
            return round(float(fallback), 2)
        return round(float(value), 2)
    except (TypeError, ValueError):
        return round(float(fallback), 2)


def _optional_pct(value: object) -> str:
    try:
        if pd.isna(value):
            return "数据源暂不支持"
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "数据源暂不支持"


def _ma_status(ma_buying: dict[str, object], period: str) -> str:
    table = ma_buying.get("评估表")
    if not isinstance(table, pd.DataFrame) or table.empty:
        return "数据不足"
    row = table[table["均线周期"] == period]
    if row.empty:
        return "数据不足"
    item = row.iloc[0]
    return f"{item['均线方向']}，距离{item['距离均线']}，评分{item['买入评分']}分"
