from __future__ import annotations

import pandas as pd

from src.indicators import add_indicators


def build_buy_strategy(df: pd.DataFrame) -> dict[str, object]:
    data = add_indicators(df)
    latest = data.iloc[-1]
    current = float(latest["close"])
    ma20 = float(latest["ma20"])
    ma30 = float(latest["ma30"])
    atr = float(latest["atr"])
    support = float(latest["low_20"])
    high_20 = float(latest["high_20"])
    recent = data.tail(20)
    volume_sum = float(recent["volume"].sum())
    if volume_sum > 0:
        volume_area = float((recent["close"] * recent["volume"]).sum() / volume_sum)
    else:
        volume_area = float(recent["close"].mean())

    conservative_low = max(min(support, ma30 - 0.5 * atr), 0)
    conservative_high = max(min(ma30, ma20 - 0.3 * atr), conservative_low)
    balanced_low = max(min(ma30, ma20 - 0.4 * atr), 0)
    balanced_high = max(min(ma20 + 0.2 * atr, current), balanced_low)
    breakout = max(high_20, ma20 + 1.0 * atr)
    chase = max(high_20 + 0.8 * atr, current + 1.2 * atr)

    return {
        "保守买入区域": _price_range(conservative_low, conservative_high),
        "平衡买入区域": _price_range(balanced_low, balanced_high),
        "突破确认价格": round(breakout, 2),
        "风险追高价格": round(chase, 2),
        "计算依据": "20日均线、30日均线、ATR波动率、近20日支撑位、成交密集区域",
        "价格合理性": (
            f"当前价格围绕20日均线 {ma20:.2f}、30日均线 {ma30:.2f} 和成交密集区域 {volume_area:.2f} "
            f"评估。靠近支撑位 {support:.2f} 时安全边际更高，突破 {breakout:.2f} 后趋势确认度更强。"
        ),
    }


def _price_range(low: float, high: float) -> str:
    return f"{low:.2f} - {high:.2f}"
