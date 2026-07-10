from __future__ import annotations

import pandas as pd

from models.indicators import add_indicators


def build_holding_analysis(holdings: pd.DataFrame, decisions: list[dict[str, object]]) -> pd.DataFrame:
    if holdings.empty:
        return pd.DataFrame()
    decision_map = {str(item.get("股票代码", "")): item for item in decisions}
    rows: list[dict[str, object]] = []
    for _, holding in holdings.iterrows():
        code = str(holding["股票代码"])
        decision = decision_map.get(code, {})
        realtime = decision.get("实时交易决策", {}) if isinstance(decision, dict) else {}
        current_price = _float(realtime.get("当前价格", decision.get("当前价格", 0)))
        cost = _float(holding["成本价格"])
        quantity = int(holding["持仓数量"])
        market_value = current_price * quantity
        cost_value = cost * quantity
        profit_amount = market_value - cost_value
        profit_pct = (current_price / cost - 1) * 100 if cost else 0.0
        score = _float(realtime.get("综合评分", decision.get("综合评分", 0)))
        risk = _float(decision.get("风险评分", 0))
        technical = _float(decision.get("技术评分", 0))
        capital = _float(decision.get("资金评分", 0))
        rows.append(
            {
                "股票代码": code,
                "股票名称": str(holding["股票名称"] or decision.get("股票名称", "名称待获取")),
                "成本价格": round(cost, 2),
                "持仓数量": quantity,
                "当前价格": round(current_price, 2),
                "持仓市值": round(market_value, 2),
                "盈亏金额": round(profit_amount, 2),
                "盈亏比例": f"{profit_pct:.2f}%",
                "距离成本涨跌幅": f"{profit_pct:.2f}%",
                "综合评分": round(score, 1),
                "风险评分": round(risk, 1),
                "技术趋势": round(technical, 1),
                "资金评分": round(capital, 1),
                "个人化建议": _holding_advice(score, risk, technical, capital, profit_pct),
                "建议原因": _advice_reason(score, risk, technical, capital, profit_pct),
            }
        )
    return pd.DataFrame(rows)


def build_holding_atr_risk(
    holdings: pd.DataFrame,
    decisions: list[dict[str, object]],
    histories: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    if holdings.empty:
        return pd.DataFrame()
    decision_map = {str(item.get("股票代码", "")): item for item in decisions}
    rows: list[dict[str, object]] = []
    for _, holding in holdings.iterrows():
        code = str(holding["股票代码"])
        history = histories.get(code)
        if history is None or history.empty:
            continue
        decision = decision_map.get(code, {})
        realtime = decision.get("实时交易决策", {}) if isinstance(decision, dict) else {}
        data = add_indicators(history).sort_values("date").tail(250).copy()
        if data.empty:
            continue
        current_price = _float(realtime.get("当前价格", decision.get("当前价格", data.iloc[-1]["close"])))
        if current_price <= 0:
            current_price = _float(data.iloc[-1]["close"])
        latest = data.iloc[-1]
        atr_value = _float(latest["atr"])
        current_atr_pct = atr_value / current_price * 100 if current_price else 0.0
        atr_pct_history = (data["atr"] / data["close"] * 100).dropna()
        percentile = _historical_percentile(atr_pct_history, current_atr_pct)
        risk_level = _atr_risk_level(percentile)

        cost = _float(holding["成本价格"])
        quantity = int(holding["持仓数量"])
        profit_pct = (current_price / cost - 1) * 100 if cost else 0.0
        normal_low = max(current_price - atr_value, 0)
        normal_high = current_price + atr_value
        suggested_stop = _suggest_stop_price(cost, current_price, atr_value, profit_pct, percentile)
        risk_distance = current_price - suggested_stop
        rows.append(
            {
                "股票代码": code,
                "股票名称": str(holding["股票名称"] or decision.get("股票名称", "名称待获取")),
                "成本价": round(cost, 2),
                "持仓数量": quantity,
                "当前价格": round(current_price, 2),
                "盈亏比例": f"{profit_pct:.2f}%",
                "ATR(14)": round(atr_value, 2),
                "ATR波动率": f"{current_atr_pct:.2f}%",
                "历史波动分位": f"{percentile:.1f}%",
                "风险等级": risk_level,
                "正常波动区间": f"{normal_low:.2f} - {normal_high:.2f}",
                "风险距离": f"{risk_distance:.2f}",
                "建议止损范围": _stop_range_text(suggested_stop, atr_value),
                "风险说明": _atr_risk_reason(percentile, profit_pct, risk_level),
            }
        )
    return pd.DataFrame(rows)


def _holding_advice(score: float, risk: float, technical: float, capital: float, profit_pct: float) -> str:
    if profit_pct <= -8 and (score < 55 or risk >= 60):
        return "止损"
    if risk >= 70 or (score < 45 and technical < 45):
        return "减仓"
    if score >= 72 and risk <= 45 and technical >= 60 and capital >= 50:
        return "加仓观察"
    return "持有"


def _advice_reason(score: float, risk: float, technical: float, capital: float, profit_pct: float) -> str:
    return (
        f"当前盈亏{profit_pct:.2f}%，综合评分{score:.1f}分，"
        f"风险评分{risk:.1f}分，技术趋势{technical:.1f}分，资金评分{capital:.1f}分。"
    )


def _float(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(str(value).replace("%", ""))
    except (TypeError, ValueError):
        return 0.0


def _historical_percentile(history: pd.Series, current_value: float) -> float:
    clean = history.dropna()
    if clean.empty:
        return 0.0
    return round(float((clean <= current_value).mean() * 100), 1)


def _atr_risk_level(percentile: float) -> str:
    if percentile < 40:
        return "低波动"
    if percentile < 70:
        return "正常"
    if percentile < 90:
        return "偏高"
    return "极高"


def _suggest_stop_price(cost: float, current_price: float, atr_value: float, profit_pct: float, percentile: float) -> float:
    if current_price <= 0:
        return 0.0
    if profit_pct > 8:
        atr_multiple = 2.5 if percentile >= 70 else 2.0
        return max(cost, current_price - atr_multiple * atr_value)
    if profit_pct >= 0:
        atr_multiple = 2.0 if percentile >= 70 else 1.5
        return max(cost * 0.97, current_price - atr_multiple * atr_value)
    atr_multiple = 1.2 if percentile >= 70 else 1.0
    return max(current_price - atr_multiple * atr_value, cost * 0.92)


def _stop_range_text(stop_price: float, atr_value: float) -> str:
    low = max(stop_price - 0.3 * atr_value, 0)
    high = max(stop_price + 0.3 * atr_value, low)
    return f"{low:.2f} - {high:.2f}"


def _atr_risk_reason(percentile: float, profit_pct: float, risk_level: str) -> str:
    base = f"当前波动高于过去{percentile:.1f}%的交易日，属于{risk_level}。"
    if profit_pct > 0 and percentile >= 70:
        return base + "当前盈利有安全垫，但近期波动扩大，止损不建议设置过近。"
    if profit_pct < 0 and percentile >= 70:
        return base + "持仓处于亏损且波动偏高，应控制回撤并避免盲目补仓。"
    if percentile < 40:
        return base + "波动处于低位，止损可结合成本价和技术支撑设置。"
    return base + "建议按正常波动区间观察，不因单日噪音频繁操作。"
