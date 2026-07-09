from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from data.providers.akshare_provider import to_prefixed_market_symbol


CN_TZ = ZoneInfo("Asia/Shanghai")
INDEX_SYMBOLS = {
    "000001": "上证指数",
    "399001": "深证成指",
    "399006": "创业板指数",
    "000688": "科创50指数",
}


@dataclass
class RealtimeFetchResult:
    data: pd.DataFrame
    error: str | None = None
    source: str = "AkShare免费实时行情"
    limitations: str = "免费接口为近实时轮询数据，非交易所Level-2推送；盘口委托、未匹配竞价量需后续接入专业数据源。"


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def is_trading_time(moment: datetime | None = None) -> bool:
    current = moment.astimezone(CN_TZ) if moment else now_cn()
    if current.weekday() >= 5:
        return False
    current_time = current.time()
    return time(9, 30) <= current_time <= time(11, 30) or time(13, 0) <= current_time <= time(15, 0)


def market_session_status(moment: datetime | None = None) -> str:
    current = moment.astimezone(CN_TZ) if moment else now_cn()
    current_time = current.time()
    if current.weekday() >= 5:
        return "市场关闭"
    if time(9, 15) <= current_time < time(9, 30):
        return "集合竞价"
    if time(9, 30) <= current_time <= time(11, 30):
        return "上午交易"
    if time(11, 30) < current_time < time(13, 0):
        return "午间休市"
    if time(13, 0) <= current_time <= time(15, 0):
        return "下午交易"
    return "市场关闭"


def fetch_realtime_quotes(codes: list[str]) -> RealtimeFetchResult:
    if not codes:
        return RealtimeFetchResult(data=pd.DataFrame())
    errors: list[str] = []
    try:
        data = _fetch_tencent_realtime_quotes(codes)
        if data.empty:
            raise ValueError("腾讯实时行情接口未返回匹配股票")
        data["更新时间"] = now_cn().strftime("%Y-%m-%d %H:%M:%S")
        return RealtimeFetchResult(data=data, source="腾讯免费实时行情")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"腾讯实时接口失败: {_short_error(exc)}")

    try:
        import akshare as ak

        raw = ak.stock_zh_a_spot_em()
        data = _normalize_stock_spot(raw)
        data = data[data["股票代码"].isin(codes)].reset_index(drop=True)
        if data.empty:
            raise ValueError("实时行情接口未返回匹配股票")
        data["更新时间"] = now_cn().strftime("%Y-%m-%d %H:%M:%S")
        return RealtimeFetchResult(data=data)
    except Exception as exc:  # noqa: BLE001 - keep UI usable with historical fallback.
        errors.append(f"东方财富实时接口失败: {_short_error(exc)}")

    try:
        data = _fetch_segment_realtime_quotes(codes)
        if data.empty:
            raise ValueError("分市场实时行情接口未返回匹配股票")
        data["更新时间"] = now_cn().strftime("%Y-%m-%d %H:%M:%S")
        return RealtimeFetchResult(data=data, source="AkShare分市场实时行情")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"分市场实时接口失败: {_short_error(exc)}")
        return RealtimeFetchResult(data=pd.DataFrame(), error="；".join(errors))


def fetch_realtime_indexes() -> RealtimeFetchResult:
    try:
        import akshare as ak

        raw = ak.stock_zh_index_spot_em()
        data = _normalize_index_spot(raw)
        data = data[data["指数代码"].isin(INDEX_SYMBOLS)].copy()
        if data.empty:
            raise ValueError("实时指数接口未返回核心指数")
        data["指数名称"] = data["指数代码"].map(INDEX_SYMBOLS).fillna(data["指数名称"])
        data["更新时间"] = now_cn().strftime("%Y-%m-%d %H:%M:%S")
        return RealtimeFetchResult(data=data.reset_index(drop=True), source="AkShare实时指数行情")
    except Exception as exc:  # noqa: BLE001
        return RealtimeFetchResult(data=pd.DataFrame(), error=_short_error(exc), source="AkShare实时指数行情")


def _fetch_segment_realtime_quotes(codes: list[str]) -> pd.DataFrame:
    import akshare as ak

    frames: list[pd.DataFrame] = []
    if any(code.startswith("6") for code in codes):
        frames.append(_normalize_stock_spot(ak.stock_sh_a_spot_em()))
    if any(code.startswith(("0", "3")) for code in codes):
        frames.append(_normalize_stock_spot(ak.stock_sz_a_spot_em()))
    if any(code.startswith(("4", "8")) for code in codes):
        frames.append(_normalize_stock_spot(ak.stock_bj_a_spot_em()))
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True)
    return data[data["股票代码"].isin(codes)].reset_index(drop=True)


def _fetch_tencent_realtime_quotes(codes: list[str]) -> pd.DataFrame:
    symbols = ",".join(to_prefixed_market_symbol(code) for code in codes)
    response = requests.get("https://qt.gtimg.cn/q=" + symbols, timeout=8)
    response.raise_for_status()
    response.encoding = "gbk"
    rows: list[dict[str, object]] = []
    for line in response.text.splitlines():
        if '="' not in line:
            continue
        payload = line.split('="', 1)[1].rstrip('";')
        parts = payload.split("~")
        if len(parts) < 39:
            continue
        rows.append(
            {
                "股票代码": parts[2].zfill(6),
                "股票名称": parts[1],
                "当前价格": _to_float(parts[3]),
                "实时涨跌": _to_float(parts[32]),
                "开盘价": _to_float(parts[5]),
                "最高价": _to_float(parts[33]),
                "最低价": _to_float(parts[34]),
                "成交量": _to_float(parts[36]),
                "成交额": _to_float(parts[37]) * 10000,
                "换手率": _to_float(parts[38]),
            }
        )
    return pd.DataFrame(rows)


def fetch_intraday_minutes(code: str) -> pd.DataFrame:
    try:
        import akshare as ak

        today = date.today().strftime("%Y-%m-%d")
        raw = ak.stock_zh_a_hist_min_em(
            symbol=code,
            period="1",
            start_date=f"{today} 09:30:00",
            end_date=f"{today} 15:00:00",
            adjust="",
        )
        data = _normalize_minute_frame(raw)
        if not data.empty:
            return data
    except Exception:
        pass

    try:
        import akshare as ak

        raw = ak.stock_zh_a_minute(symbol=to_prefixed_market_symbol(code), period="1", adjust="")
        return _normalize_minute_frame(raw)
    except Exception:
        return pd.DataFrame(columns=["时间", "开盘价", "收盘价", "最高价", "最低价", "成交量", "成交额"])


def _normalize_stock_spot(raw: pd.DataFrame) -> pd.DataFrame:
    rename = {
        "代码": "股票代码",
        "code": "股票代码",
        "symbol": "股票代码",
        "名称": "股票名称",
        "name": "股票名称",
        "最新价": "当前价格",
        "trade": "当前价格",
        "price": "当前价格",
        "涨跌幅": "实时涨跌",
        "changepercent": "实时涨跌",
        "今开": "开盘价",
        "open": "开盘价",
        "最高": "最高价",
        "high": "最高价",
        "最低": "最低价",
        "low": "最低价",
        "成交量": "成交量",
        "volume": "成交量",
        "成交额": "成交额",
        "amount": "成交额",
        "换手率": "换手率",
        "turnoverratio": "换手率",
    }
    data = raw.rename(columns=rename).copy()
    required = ["股票代码", "股票名称", "当前价格", "实时涨跌", "开盘价", "最高价", "最低价", "成交量", "成交额"]
    for column in required:
        if column not in data.columns:
            data[column] = None
    if "换手率" not in data.columns:
        data["换手率"] = None
    for column in ["当前价格", "实时涨跌", "开盘价", "最高价", "最低价", "成交量", "成交额", "换手率"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["股票代码"] = data["股票代码"].astype(str).str.replace(r"^(sh|sz|bj)", "", regex=True).str.zfill(6)
    return data[required + ["换手率"]]


def _normalize_index_spot(raw: pd.DataFrame) -> pd.DataFrame:
    rename = {
        "代码": "指数代码",
        "名称": "指数名称",
        "最新价": "当前点位",
        "涨跌幅": "实时涨跌",
        "成交量": "成交量",
        "成交额": "成交额",
    }
    data = raw.rename(columns=rename).copy()
    required = ["指数代码", "指数名称", "当前点位", "实时涨跌", "成交量", "成交额"]
    for column in required:
        if column not in data.columns:
            data[column] = None
    for column in ["当前点位", "实时涨跌", "成交量", "成交额"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["指数代码"] = data["指数代码"].astype(str).str.zfill(6)
    return data[required]


def _normalize_minute_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["时间", "开盘价", "收盘价", "最高价", "最低价", "成交量", "成交额"])
    rename = {
        "时间": "时间",
        "日期": "时间",
        "day": "时间",
        "开盘": "开盘价",
        "open": "开盘价",
        "收盘": "收盘价",
        "close": "收盘价",
        "最高": "最高价",
        "high": "最高价",
        "最低": "最低价",
        "low": "最低价",
        "成交量": "成交量",
        "volume": "成交量",
        "成交额": "成交额",
        "amount": "成交额",
    }
    data = raw.rename(columns=rename).copy()
    for column in ["时间", "开盘价", "收盘价", "最高价", "最低价", "成交量", "成交额"]:
        if column not in data.columns:
            data[column] = 0
    data["时间"] = pd.to_datetime(data["时间"], errors="coerce")
    for column in ["开盘价", "收盘价", "最高价", "最低价", "成交量", "成交额"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)
    return data.dropna(subset=["时间"]).sort_values("时间").reset_index(drop=True)[
        ["时间", "开盘价", "收盘价", "最高价", "最低价", "成交量", "成交额"]
    ]


def _short_error(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    return (message or exc.__class__.__name__)[:200]


def _to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
