from __future__ import annotations

import numpy as np
import pandas as pd

from models.auction import analyze_auction
from models.probability import forward_returns_after_condition, outcome_stats, yellow_line_probability_database


def analyze_morning_direction(df: pd.DataFrame) -> dict[str, object]:
    data = df.sort_values("date").copy().reset_index(drop=True)
    if len(data) < 30:
        return _empty()

    auction = analyze_auction(data)
    latest = data.iloc[-1]
    previous = data.iloc[-2]
    current_price = float(latest["close"])
    intraday_avg = _intraday_average_price(latest)
    above_avg = current_price >= intraday_avg
    opening_pct = (float(latest["open"]) / float(previous["close"]) - 1) * 100 if previous["close"] else 0
    opening_5 = _opening_strength(latest, fraction=0.25)
    opening_15 = _opening_strength(latest, fraction=0.5)
    volume_ratio = _volume_ratio(data)
    buy_sell_power = _buy_sell_power(latest, intraday_avg)

    long_model = average_line_breakout_model(data)
    short_model = average_line_breakdown_model(data)
    long_probability = float(str(long_model["上涨概率"]).replace("%", ""))
    short_probability = float(str(short_model["继续下跌概率"]).replace("%", ""))
    auction_bias = _auction_bias(float(auction["竞价涨跌幅"]), float(auction["竞价量比"]))
    opening_status = "强势" if opening_pct >= 0 and opening_15 >= 0 else "弱势"
    avg_line_status = "站上均价线" if above_avg else "跌破均价线"
    final = _final_signal(auction_bias, opening_status, above_avg, long_probability, short_probability)

    return {
        "集合竞价": auction_bias,
        "昨日收盘价": auction["昨日收盘价"],
        "今日集合竞价价格": auction["今日竞价价格"],
        "集合竞价涨跌幅": auction["竞价涨跌幅"],
        "集合竞价成交量": auction["竞价成交量"],
        "集合竞价成交额": auction["竞价成交额"],
        "竞价量比": auction["竞价量比"],
        "开盘涨跌幅": round(opening_pct, 2),
        "开盘5分钟走势": f"{opening_5:.2f}%",
        "开盘15分钟走势": f"{opening_15:.2f}%",
        "当前价格": round(current_price, 2),
        "分时均价线": round(intraday_avg, 2),
        "均价线状态": avg_line_status,
        "成交量变化": f"{volume_ratio:.2f}倍",
        "买卖力量变化": buy_sell_power,
        "上涨概率": f"{long_probability:.1f}%",
        "下跌概率": f"{short_probability:.1f}%",
        "最终判断": final,
        "失效条件": _failure_conditions(final),
        "分时突破模型": long_model,
        "跌破均价线模型": short_model,
        "数据口径": "未接入实时分时源时，10:30-10:50使用日内均价估算模型；接入分钟线后可替换为真实分时均价线。",
    }


def analyze_intraday_vwap(
    history: pd.DataFrame,
    minutes: pd.DataFrame,
    realtime_quote: dict[str, object] | None = None,
) -> dict[str, object]:
    if minutes is None or minutes.empty:
        latest = history.sort_values("date").iloc[-1]
        current = _quote_value(realtime_quote, "当前价格", float(latest["close"]))
        avg_line = _intraday_average_price(latest)
        status = "站上黄线" if current >= avg_line else "跌破黄线"
        return {
            "当前价格": round(current, 2),
            "分时均价线": round(avg_line, 2),
            "偏离黄线": f"{_distance_pct(current, avg_line):.2f}%",
            "黄线状态": status,
            "黄线方向": "数据不足",
            "成交量变化": "数据不足",
            "站稳5分钟": "数据不足",
            "站稳10分钟": "数据不足",
            "站稳15分钟": "数据不足",
            "突破概率表": yellow_line_probability_database(history),
            "数据口径": "当前免费接口未返回当日分钟线，分时黄线使用日线VWAP代理；接入Level-2或稳定分钟源后可替换。",
        }

    data = minutes.sort_values("时间").copy().reset_index(drop=True)
    data["累计成交量"] = data["成交量"].cumsum()
    data["累计成交额"] = data["成交额"].cumsum()
    data["典型价格"] = (data["最高价"] + data["最低价"] + data["收盘价"]) / 3
    missing_amount = data["累计成交额"].iloc[-1] <= 0
    if missing_amount:
        data["分时均价线"] = (data["典型价格"] * data["成交量"]).cumsum() / data["累计成交量"].replace(0, np.nan)
    else:
        data["分时均价线"] = data["累计成交额"] / data["累计成交量"].replace(0, np.nan) / 100
    data["分时均价线"] = data["分时均价线"].ffill().fillna(data["收盘价"])

    latest = data.iloc[-1]
    current = _quote_value(realtime_quote, "当前价格", float(latest["收盘价"]))
    avg_line = float(latest["分时均价线"])
    status = "站上黄线" if current >= avg_line else "跌破黄线"
    direction = _line_direction(data["分时均价线"])
    volume_change = _minute_volume_change(data)
    above = data["收盘价"] >= data["分时均价线"]
    return {
        "当前价格": round(current, 2),
        "分时均价线": round(avg_line, 2),
        "偏离黄线": f"{_distance_pct(current, avg_line):.2f}%",
        "黄线状态": status,
        "黄线方向": direction,
        "成交量变化": volume_change,
        "站稳5分钟": _stable_status(above, 5),
        "站稳10分钟": _stable_status(above, 10),
        "站稳15分钟": _stable_status(above, 15),
        "分钟数据": data,
        "突破概率表": yellow_line_probability_database(history),
        "数据口径": "当前黄线由当日1分钟成交量和成交额计算；免费接口为轮询数据，非Level-2逐笔推送。",
    }


def build_1050_direction(
    history: pd.DataFrame,
    auction: dict[str, object],
    intraday: dict[str, object],
    market_score: float,
    ma_buying: dict[str, object],
) -> dict[str, object]:
    base_long = 50.0
    auction_gap = float(auction.get("竞价涨跌幅", 0) or 0)
    auction_ratio = float(auction.get("竞价量比", 1) or 1)
    if auction_gap > 0.3:
        base_long += 8
    elif auction_gap < -0.3:
        base_long -= 8
    base_long += min(max(auction_ratio - 1, -1), 2) * 4
    base_long += (market_score - 50) * 0.28

    yellow_status = str(intraday.get("黄线状态", ""))
    yellow_direction = str(intraday.get("黄线方向", ""))
    if yellow_status == "站上黄线":
        base_long += 12
    elif yellow_status == "跌破黄线":
        base_long -= 12
    if yellow_direction == "向上":
        base_long += 6
    elif yellow_direction == "向下":
        base_long -= 6

    ma_table = ma_buying.get("评估表")
    if isinstance(ma_table, pd.DataFrame) and not ma_table.empty:
        base_long += (float(ma_table["买入评分"].mean()) - 50) * 0.18

    probability_table = intraday.get("突破概率表")
    if isinstance(probability_table, pd.DataFrame) and not probability_table.empty:
        breakthrough = probability_table[probability_table["场景"] == "价格放量突破分时黄线"]
        if not breakthrough.empty and "上涨概率" in breakthrough.columns:
            base_long += (_pct_to_float(str(breakthrough.iloc[-1]["上涨概率"])) - 50) * 0.16

    long_score = round(float(np.clip(base_long, 0, 100)), 1)
    short_score = round(100 - long_score, 1)
    final = "偏多" if long_score >= 62 else "偏空" if short_score >= 62 else "震荡"
    return {
        "模块名称": "10:50多空确认",
        "上涨概率": f"{long_score:.1f}%",
        "下跌概率": f"{short_score:.1f}%",
        "多方评分": long_score,
        "空方评分": short_score,
        "最终判断": final,
        "判断依据": f"集合竞价{_auction_bias(auction_gap, auction_ratio)}，分时黄线{yellow_status}，市场环境评分{market_score:.1f}分。",
        "失效条件": _failure_conditions(final),
    }


def average_line_breakout_model(df: pd.DataFrame) -> dict[str, object]:
    data = df.sort_values("date").copy()
    avg_line = data.apply(_intraday_average_price, axis=1)
    condition = (data["close"] > avg_line) & (data["open"] <= avg_line)
    returns = forward_returns_after_condition(data, condition, forward_days=1, period=250)
    stats = outcome_stats(returns)
    return {
        "场景": "价格突破并站稳日内均价线",
        "历史类似情况": stats["出现次数"],
        "成功上涨次数": stats["成功次数"],
        "失败次数": stats["失败次数"],
        "上涨概率": stats["胜率"],
        "平均涨幅": stats["平均收益"],
        "最大涨幅": stats["最大涨幅"],
        "最大回撤": stats["最大回撤"],
        "判断": "多方占优" if _pct_to_float(str(stats["胜率"])) >= 55 else "多空均衡",
    }


def average_line_breakdown_model(df: pd.DataFrame) -> dict[str, object]:
    data = df.sort_values("date").copy()
    avg_line = data.apply(_intraday_average_price, axis=1)
    condition = (data["close"] < avg_line) & (data["open"] >= avg_line)
    returns = -forward_returns_after_condition(data, condition, forward_days=1, period=250)
    stats = outcome_stats(returns)
    probability = stats["胜率"]
    return {
        "场景": "价格跌破日内均价线",
        "历史类似情况": stats["出现次数"],
        "继续下跌概率": probability,
        "平均跌幅": stats["平均收益"],
        "最大跌幅": stats["最大涨幅"],
        "最大反弹": stats["最大回撤"],
        "风险等级": _breakdown_risk(_pct_to_float(str(probability))),
        "判断": "空方占优" if _pct_to_float(str(probability)) >= 55 else "风险可控但需观察",
    }


def _intraday_average_price(row: pd.Series) -> float:
    amount = float(row.get("amount", 0) or 0)
    volume = float(row.get("volume", 0) or 0)
    if amount > 0 and volume > 0:
        return amount / volume / 100
    return float((row["high"] + row["low"] + row["close"]) / 3)


def _opening_strength(row: pd.Series, fraction: float) -> float:
    open_price = float(row["open"])
    close_price = float(row["close"])
    proxy_price = open_price + (close_price - open_price) * fraction
    return (proxy_price / open_price - 1) * 100 if open_price else 0.0


def _volume_ratio(data: pd.DataFrame) -> float:
    avg = data["volume"].tail(20).mean()
    latest = float(data.iloc[-1]["volume"])
    return latest / avg if avg else 1.0


def _buy_sell_power(row: pd.Series, avg_line: float) -> str:
    close = float(row["close"])
    open_price = float(row["open"])
    if close >= avg_line and close >= open_price:
        return "买方增强"
    if close < avg_line and close < open_price:
        return "卖方增强"
    return "多空拉锯"


def _auction_bias(gap_pct: float, ratio: float) -> str:
    if gap_pct > 0.3 and ratio >= 1:
        return "偏多"
    if gap_pct < -0.3 and ratio >= 1:
        return "偏空"
    return "中性"


def _final_signal(auction_bias: str, opening_status: str, above_avg: bool, long_probability: float, short_probability: float) -> str:
    long_votes = int(auction_bias == "偏多") + int(opening_status == "强势") + int(above_avg) + int(long_probability >= 55)
    short_votes = int(auction_bias == "偏空") + int(opening_status == "弱势") + int(not above_avg) + int(short_probability >= 55)
    if long_votes >= 3 and long_votes > short_votes:
        return "偏多"
    if short_votes >= 3 and short_votes > long_votes:
        return "偏空"
    return "震荡"


def _failure_conditions(final_signal: str) -> str:
    if final_signal == "偏多":
        return "跌破分时均价线、成交量放大下跌、大盘转弱。"
    if final_signal == "偏空":
        return "重新站上分时均价线、放量拉升、大盘转强。"
    return "突破失败、成交量不足、指数方向突然转弱。"


def _breakdown_risk(probability: float) -> str:
    if probability >= 65:
        return "高风险"
    if probability >= 55:
        return "中高风险"
    if probability >= 45:
        return "中等风险"
    return "低风险"


def _pct_to_float(value: str) -> float:
    try:
        return float(value.replace("%", ""))
    except ValueError:
        return 0.0


def _quote_value(quote: dict[str, object] | None, key: str, fallback: float) -> float:
    if not quote:
        return fallback
    try:
        value = quote.get(key, fallback)
        if pd.isna(value):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _distance_pct(current: float, base: float) -> float:
    return (current / base - 1) * 100 if base else 0.0


def _line_direction(line: pd.Series) -> str:
    clean = line.dropna()
    if len(clean) < 6:
        return "数据不足"
    delta = float(clean.iloc[-1] - clean.iloc[-6])
    if delta > 0:
        return "向上"
    if delta < 0:
        return "向下"
    return "横盘"


def _minute_volume_change(data: pd.DataFrame) -> str:
    if len(data) < 10:
        return "数据不足"
    recent = float(data["成交量"].tail(5).mean())
    previous = float(data["成交量"].tail(20).head(15).mean())
    ratio = recent / previous if previous else 1.0
    if ratio >= 1.5:
        return f"明显放大（{ratio:.2f}倍）"
    if ratio <= 0.7:
        return f"明显缩量（{ratio:.2f}倍）"
    return f"基本稳定（{ratio:.2f}倍）"


def _stable_status(above: pd.Series, minutes: int) -> str:
    if len(above) < minutes:
        return "数据不足"
    return "是" if bool(above.tail(minutes).all()) else "否"


def _empty() -> dict[str, object]:
    return {
        "集合竞价": "数据不足",
        "开盘表现": "数据不足",
        "均价线状态": "数据不足",
        "上涨概率": "0.0%",
        "下跌概率": "0.0%",
        "最终判断": "震荡",
        "失效条件": "数据不足",
        "分时突破模型": {},
        "跌破均价线模型": {},
        "数据口径": "数据不足",
    }
