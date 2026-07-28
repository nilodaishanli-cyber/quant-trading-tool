from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from data.data_source import get_data_source
from data.providers.akshare_provider import fetch_stock_history, fetch_stock_names
from data.realtime_market import market_session_status
from models.decision import build_decision, build_realtime_decision
from models.indicators import add_indicators
from models.market import analyze_realtime_market
from models.market_environment import fetch_market_environment


@dataclass
class AnalysisResult:
    decisions: list[dict[str, Any]]
    histories: dict[str, pd.DataFrame]
    market: dict[str, Any]
    errors: list[dict[str, str]]


def analyze_stock_pool(codes: list[str]) -> AnalysisResult:
    market = fetch_market_environment(days=45)
    market_score = float(market["score"])
    decisions: list[dict[str, Any]] = []
    histories: dict[str, pd.DataFrame] = {}
    errors: list[dict[str, str]] = []

    for code in codes:
        decision, history, error = analyze_single_stock(code, market_score)
        if error:
            errors.append(error)
            continue
        histories[code] = history
        decisions.append(decision)

    decisions = sorted(decisions, key=lambda item: (float(item["风险评分"]), -float(item["综合评分"])))
    return AnalysisResult(decisions=decisions, histories=histories, market=market, errors=errors)


def analyze_single_stock(code: str, market_score: float) -> tuple[dict[str, Any], pd.DataFrame, dict[str, str] | None]:
    names = fetch_stock_names([code])
    result = fetch_stock_history(code, days=260)
    if result.error:
        return {}, pd.DataFrame(), {"股票代码": code, "错误原因": result.error}
    history = add_indicators(result.data)
    decision = build_decision(code, names.get(code, "名称待获取"), history, market_score, result.source)
    return decision, history, None


def analyze_realtime_stock_pool(codes: list[str]) -> AnalysisResult:
    source = get_data_source()
    historical_market = fetch_market_environment(days=45)
    realtime_market = analyze_realtime_market()
    market = realtime_market if not realtime_market.get("errors") else historical_market
    market_score = float(market["score"])
    quotes_result = source.realtime_quotes(codes)
    quotes = _quotes_by_code(quotes_result.data)
    decisions: list[dict[str, Any]] = []
    histories: dict[str, pd.DataFrame] = {}
    errors: list[dict[str, str]] = []

    for code in codes:
        decision, history, error = analyze_single_stock(code, market_score)
        if error:
            errors.append(error)
            continue
        try:
            minutes = source.intraday_minutes(code)
            realtime_decision = build_realtime_decision(
                decision,
                history,
                quotes.get(code),
                minutes,
                market,
            )
            decision["实时交易决策"] = realtime_decision
            decision["分时分钟数据"] = minutes
            histories[code] = history
            decisions.append(decision)
        except Exception as exc:  # noqa: BLE001 - keep other stocks available.
            errors.append({"股票代码": code, "错误原因": f"实时分析失败: {str(exc)[:180]}"})

    if quotes_result.error:
        errors.append({"股票代码": "实时行情", "错误原因": quotes_result.error})

    market = dict(market)
    market["交易状态"] = market_session_status()
    market["数据限制"] = quotes_result.limitations
    decisions = sorted(decisions, key=lambda item: (float(item["风险评分"]), -float(item["综合评分"])))
    return AnalysisResult(decisions=decisions, histories=histories, market=market, errors=errors)


def analyze_historical_stock_pool(codes: list[str], market_score: float) -> AnalysisResult:
    decisions: list[dict[str, Any]] = []
    histories: dict[str, pd.DataFrame] = {}
    errors: list[dict[str, str]] = []
    for code in codes:
        decision, history, error = analyze_single_stock(code, market_score)
        if error:
            errors.append(error)
            continue
        histories[code] = history
        decisions.append(decision)
    decisions = sorted(decisions, key=lambda item: (float(item["风险评分"]), -float(item["综合评分"])))
    return AnalysisResult(decisions=decisions, histories=histories, market={}, errors=errors)


def get_realtime_quotes(codes: list[str]):
    return get_data_source().realtime_quotes(codes)


def get_intraday_minutes(code: str) -> pd.DataFrame:
    return get_data_source().intraday_minutes(code)


def merge_realtime_analysis(
    base_decisions: list[dict[str, Any]],
    histories: dict[str, pd.DataFrame],
    market: dict[str, Any],
    quotes: pd.DataFrame,
    minutes_by_code: dict[str, pd.DataFrame],
    quote_error: str | None = None,
) -> AnalysisResult:
    quote_map = _quotes_by_code(quotes)
    decisions: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for base in base_decisions:
        code = str(base["股票代码"])
        history = histories.get(code)
        if history is None or history.empty:
            errors.append({"股票代码": code, "错误原因": "历史数据缺失，无法生成实时决策。"})
            continue
        try:
            decision = dict(base)
            realtime_decision = build_realtime_decision(
                decision,
                history,
                quote_map.get(code),
                minutes_by_code.get(code, pd.DataFrame()),
                market,
            )
            decision["实时交易决策"] = realtime_decision
            decision["分时分钟数据"] = minutes_by_code.get(code, pd.DataFrame())
            decisions.append(decision)
        except Exception as exc:  # noqa: BLE001 - isolate one stock failure.
            errors.append({"股票代码": code, "错误原因": f"实时分析失败: {str(exc)[:180]}"})

    if quote_error:
        errors.append({"股票代码": "实时行情", "错误原因": quote_error})

    merged_market = dict(market)
    merged_market["交易状态"] = market_session_status()
    decisions = sorted(decisions, key=lambda item: (float(item["风险评分"]), -float(item["综合评分"])))
    return AnalysisResult(decisions=decisions, histories=histories, market=merged_market, errors=errors)


def get_market_context() -> dict[str, Any]:
    return fetch_market_environment(days=45)


def get_realtime_market_context() -> dict[str, Any]:
    market = analyze_realtime_market()
    market["交易状态"] = market_session_status()
    return market


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    clean = df.copy()
    for column in clean.columns:
        if pd.api.types.is_datetime64_any_dtype(clean[column]):
            clean[column] = clean[column].dt.strftime("%Y-%m-%d")
    clean = clean.where(pd.notna(clean), None)
    return clean.to_dict(orient="records")


def serialize_analysis(result: AnalysisResult) -> dict[str, Any]:
    market = dict(result.market)
    indexes = market.get("indexes")
    if isinstance(indexes, pd.DataFrame):
        market["indexes"] = dataframe_to_records(indexes)

    histories = {
        code: dataframe_to_records(history.tail(260))
        for code, history in result.histories.items()
    }
    decisions = [_serialize_decision(decision) for decision in result.decisions]
    return {
        "market": market,
        "decisions": decisions,
        "histories": histories,
        "errors": result.errors,
    }


def _serialize_decision(decision: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in decision.items():
        if isinstance(value, pd.DataFrame):
            serialized[key] = dataframe_to_records(value)
        elif isinstance(value, dict):
            serialized[key] = _serialize_nested(value)
        else:
            serialized[key] = value
    return serialized


def _serialize_nested(value: dict[str, Any]) -> dict[str, Any]:
    nested: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, pd.DataFrame):
            nested[key] = dataframe_to_records(item)
        elif isinstance(item, dict):
            nested[key] = _serialize_nested(item)
        else:
            nested[key] = item
    return nested


def _quotes_by_code(data: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if data.empty:
        return {}
    return {
        str(row["股票代码"]).zfill(6): row.to_dict()
        for _, row in data.iterrows()
    }
