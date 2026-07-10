from __future__ import annotations

import pandas as pd


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
