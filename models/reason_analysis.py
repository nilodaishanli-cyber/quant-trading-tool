from __future__ import annotations

import pandas as pd


def analyze_today_reason(df: pd.DataFrame, market_score: float) -> dict[str, object]:
    data = df.sort_values("date")
    latest = data.iloc[-1]
    pct_change = float(latest.get("pct_change", 0) or 0)
    volume_avg = data["volume"].tail(20).mean()
    volume_ratio = float(latest["volume"] / volume_avg) if volume_avg else 1.0
    close = float(latest["close"])
    ma20 = float(data["close"].rolling(20, min_periods=1).mean().iloc[-1])

    market_contribution = max(0, min(60, market_score - 40))
    volume_contribution = max(0, min(50, (volume_ratio - 1) * 30))
    trend_contribution = 30 if close >= ma20 else 10
    total = market_contribution + volume_contribution + trend_contribution
    if total <= 0:
        weights = (34, 33, 33)
    else:
        weights = (
            round(market_contribution / total * 100),
            round(trend_contribution / total * 100),
            round(volume_contribution / total * 100),
        )

    direction = "上涨" if pct_change >= 0 else "下跌"
    return {
        "今日涨跌原因": f"今日{direction}主要由市场环境、个股趋势和成交量共同影响。",
        "市场影响": _market_text(market_score),
        "行业影响": "第一版暂未接入行业指数，当前用市场环境近似评估，后续可接申万行业指数。",
        "个股趋势": "价格站上20日均线，趋势偏强。" if close >= ma20 else "价格低于20日均线，趋势仍需修复。",
        "成交量变化": f"当前成交量约为20日均量的 {volume_ratio:.2f} 倍。",
        "市场贡献": f"{weights[0]}%",
        "行业贡献": "暂未接入",
        "个股资金": f"{weights[2]}%",
    }


def _market_text(score: float) -> str:
    if score >= 65:
        return "市场处于强势区间，对个股有正向推动。"
    if score <= 40:
        return "市场偏弱，对个股形成压力。"
    return "市场震荡，对个股影响中性。"
