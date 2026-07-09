from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from backend.services.analysis_service import analyze_realtime_stock_pool
from data.realtime_market import is_trading_time, market_session_status, now_cn
from utils.formatting import dataframe_to_csv_bytes, parse_stock_codes


st.set_page_config(page_title="实时盘中量化交易分析系统", layout="wide")


SUMMARY_COLUMNS = [
    "股票名称",
    "股票代码",
    "当前价格",
    "今日涨跌",
    "综合评分",
    "市场环境评分",
    "技术评分",
    "资金评分",
    "竞价评分",
    "风险评分",
    "风险等级",
    "建议操作",
    "数据源",
]


DETAIL_COLUMNS = {
    "date": "日期",
    "open": "开盘价",
    "close": "收盘价",
    "high": "最高价",
    "low": "最低价",
    "volume": "成交量",
    "amount": "成交额",
    "pct_change": "涨跌幅",
    "ma5": "5日均线",
    "ma10": "10日均线",
    "ma20": "20日均线",
    "ma30": "30日均线",
    "ma20_deviation_pct": "偏离20日均线",
    "ma30_deviation_pct": "偏离30日均线",
    "avg_price_20": "20日平均价",
    "avg_price_30": "30日平均价",
    "high_20": "近20日最高价",
    "low_20": "近20日最低价",
    "atr": "ATR波动率",
    "volume_avg_20": "20日平均成交量",
}


def main() -> None:
    st.title("实时盘中量化交易分析系统")
    st.caption("集合竞价 -> 开盘 -> 实时分时 -> 黄线突破概率 -> 10:50多空判断 -> 买入区域 -> 风险控制。")

    with st.sidebar:
        st.header("系统设置")
        show_candlestick = st.toggle("显示K线图", value=True)
        auto_refresh = st.toggle("交易时间自动刷新", value=True)
        refresh_interval = st.slider("刷新频率（秒）", min_value=5, max_value=30, value=15, step=5)
        st.caption("免费行情为轮询近实时数据，后续可在数据源层替换Level-2。")

    query_codes = str(st.query_params.get("codes", ""))
    default_codes = query_codes.replace(",", "\n") if query_codes else "002463\n600519\n000001"

    raw_codes = st.text_area(
        "输入股票代码",
        value=default_codes,
        height=110,
        help="支持换行、逗号、空格分隔，例如 002463, 600519, 000001。",
    )
    status_cols = st.columns(3)
    status_cols[0].metric("当前时间", now_cn().strftime("%H:%M:%S"))
    status_cols[1].metric("交易状态", market_session_status())
    status_cols[2].metric("刷新频率", f"{refresh_interval}秒" if auto_refresh else "手动")
    st.caption("提示：首次分析新股票会获取约260个交易日数据；交易时间内实时行情按设置自动刷新。")
    run_button = st.button("开始实时分析", type="primary", width="stretch")

    codes = parse_stock_codes(raw_codes)
    if not codes:
        st.info("请先输入至少一个6位A股股票代码。")
        return

    if run_button:
        st.query_params["run"] = "1"
        st.query_params["codes"] = ",".join(codes)

    should_run = run_button or st.query_params.get("run") == "1"
    if not should_run:
        st.info("股票池已准备好，点击上方“开始实时分析”。")
        st.dataframe(pd.DataFrame({"股票代码": codes}), width="stretch", hide_index=True)
        return

    if auto_refresh and is_trading_time():
        inject_auto_refresh(refresh_interval)

    with st.spinner("正在获取实时行情、市场环境、当日分钟线和历史概率..."):
        result = cached_analyze_realtime_stock_pool(tuple(codes), refresh_interval, cache_version="rt-v1")
    decisions, histories, errors, market = result.decisions, result.histories, result.errors, result.market

    if errors:
        st.warning("部分股票数据获取失败。免费行情接口偶尔会断开，系统已自动尝试备用源。")
        st.dataframe(pd.DataFrame(errors), width="stretch", hide_index=True)

    if not decisions:
        st.error("没有可展示的数据。请稍后重试，或减少股票数量后再次分析。")
        return

    decisions_df = pd.DataFrame(decisions).sort_values(["风险评分", "综合评分"], ascending=[True, False])
    selected_code = render_home(decisions_df, histories, market, show_candlestick)
    render_market(market)
    render_ranking(decisions_df)
    render_stock_detail(selected_code, decisions_df, histories, show_candlestick)


def render_home(
    decisions_df: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    market: dict[str, object],
    show_candlestick: bool,
) -> str:
    st.subheader("实时交易决策")
    options = [f"{row['股票名称']}（{row['股票代码']}）" for _, row in decisions_df.iterrows()]
    selected_label = st.selectbox("选择分析股票", options)
    selected_code = selected_label.split("（")[-1].replace("）", "")
    decision = decisions_df[decisions_df["股票代码"] == selected_code].iloc[0]
    realtime = decision.get("实时交易决策", {})

    st.markdown(f"### {decision['股票名称']}（{decision['股票代码']}）")
    top = st.columns(5)
    top[0].metric("当前价格", f"{realtime.get('当前价格', decision['当前价格'])}")
    top[1].metric("实时涨跌", str(realtime.get("实时涨跌", decision["今日涨跌"])))
    top[2].metric("市场环境", str(realtime.get("市场环境", market["status"])))
    top[3].metric("综合评分", f"{realtime.get('综合评分', decision['综合评分'])}分")
    top[4].metric("风险等级", str(realtime.get("风险等级", decision["风险等级"])))

    score_cols = st.columns(4)
    score_cols[0].metric("技术趋势", f"{decision['技术评分']}分")
    score_cols[1].metric("资金评分", f"{decision['资金评分']}分")
    score_cols[2].metric("竞价评分", f"{decision['竞价评分']}分")
    score_cols[3].metric("风险评分", f"{decision['风险评分']}分")

    st.success(f"最终建议：{realtime.get('最终建议', decision['建议操作'])}")
    st.info(f"{realtime.get('建议说明', '市场环境会参与个股综合评分。')} 风险控制：{realtime.get('风险控制', '等待确认。')}")

    realtime_cols = st.columns(4)
    realtime_cols[0].metric("集合竞价", str(realtime.get("集合竞价", "中性")))
    realtime_cols[1].metric("分时黄线", str(realtime.get("分时黄线", "数据不足")))
    realtime_cols[2].metric("10:50方向", str(realtime.get("10:50方向", "震荡")))
    realtime_cols[3].metric("上涨/下跌概率", f"{realtime.get('上涨概率', '0.0%')} / {realtime.get('下跌概率', '0.0%')}")

    ma_cols = st.columns(4)
    ma_cols[0].write(f"5日均线：{realtime.get('5日均线', '数据不足')}")
    ma_cols[1].write(f"10日均线：{realtime.get('10日均线', '数据不足')}")
    ma_cols[2].write(f"20日均线：{realtime.get('20日均线', '数据不足')}")
    ma_cols[3].write(f"30日均线：{realtime.get('30日均线', '数据不足')}")

    buy = decision["买入策略"]
    buy_cols = st.columns(4)
    buy_cols[0].metric("保守买入区域", str(buy["保守买入区域"]))
    buy_cols[1].metric("平衡买入区域", str(buy["平衡买入区域"]))
    buy_cols[2].metric("突破确认价格", str(buy["突破确认价格"]))
    buy_cols[3].metric("风险追高价格", str(buy["风险追高价格"]))
    st.caption(f"价格依据：{buy['计算依据']}。{buy['价格合理性']}")

    render_ma_strategy_summary(decision)
    render_realtime_intraday_summary(decision)
    render_morning_summary(decision)

    st.plotly_chart(
        make_price_chart(histories[selected_code], selected_label, show_candlestick),
        use_container_width=True,
        key=f"首页价格走势_{selected_code}",
    )
    return selected_code


def render_ma_strategy_summary(decision: pd.Series) -> None:
    st.subheader("四周期买入评估")
    ma_eval = decision["四周期买入评估"]
    table = ma_eval["评估表"]
    cards = st.columns(4)
    for index, row in table.reset_index(drop=True).iterrows():
        with cards[index]:
            st.metric(row["均线周期"], row["星级"])
            st.write(row["交易定位"])
            st.write(f"买入评分：{row['买入评分']}分")
            st.write(f"风险等级：{row['风险等级']}")

    st.markdown("**四周期买入排名**")
    st.dataframe(ma_eval["四周期买入排名"], width="stretch", hide_index=True)


def render_morning_summary(decision: pd.Series) -> None:
    st.subheader("早盘方向预测")
    morning = decision["早盘方向预测"]
    cols = st.columns(6)
    cols[0].metric("集合竞价", str(morning["集合竞价"]))
    cols[1].metric("开盘表现", "强势" if float(morning["开盘涨跌幅"]) >= 0 else "弱势")
    cols[2].metric("10:50", str(morning["均价线状态"]))
    cols[3].metric("上涨概率", str(morning["上涨概率"]))
    cols[4].metric("下跌概率", str(morning["下跌概率"]))
    cols[5].metric("最终判断", str(morning["最终判断"]))
    st.caption(f"失效条件：{morning['失效条件']} 数据口径：{morning['数据口径']}")


def render_realtime_intraday_summary(decision: pd.Series) -> None:
    realtime = decision.get("实时交易决策", {})
    intraday = realtime.get("分时黄线分析", {}) if isinstance(realtime, dict) else {}
    direction = realtime.get("10:50多空确认", {}) if isinstance(realtime, dict) else {}
    st.subheader("分时黄线实时分析")
    cols = st.columns(6)
    cols[0].metric("当前价格", str(intraday.get("当前价格", "数据不足")))
    cols[1].metric("分时均价", str(intraday.get("分时均价线", "数据不足")))
    cols[2].metric("偏离黄线", str(intraday.get("偏离黄线", "数据不足")))
    cols[3].metric("黄线状态", str(intraday.get("黄线状态", "数据不足")))
    cols[4].metric("黄线方向", str(intraday.get("黄线方向", "数据不足")))
    cols[5].metric("成交量变化", str(intraday.get("成交量变化", "数据不足")))
    stable = st.columns(3)
    stable[0].metric("站稳5分钟", str(intraday.get("站稳5分钟", "数据不足")))
    stable[1].metric("站稳10分钟", str(intraday.get("站稳10分钟", "数据不足")))
    stable[2].metric("站稳15分钟", str(intraday.get("站稳15分钟", "数据不足")))
    st.subheader("10:50多空确认")
    direction_cols = st.columns(5)
    direction_cols[0].metric("多方", str(direction.get("上涨概率", "0.0%")))
    direction_cols[1].metric("空方", str(direction.get("下跌概率", "0.0%")))
    direction_cols[2].metric("多方评分", str(direction.get("多方评分", 0)))
    direction_cols[3].metric("空方评分", str(direction.get("空方评分", 0)))
    direction_cols[4].metric("最终判断", str(direction.get("最终判断", "震荡")))
    st.caption(str(direction.get("判断依据", "")))


def render_market(market: dict[str, object]) -> None:
    st.subheader("市场实时环境")
    col1, col2, col3 = st.columns(3)
    col1.metric("市场环境评分", f"{market['score']}分")
    col2.metric("市场状态", str(market["status"]))
    col3.metric("交易状态", str(market.get("交易状态", market_session_status())))
    indexes = market.get("indexes")
    if isinstance(indexes, pd.DataFrame) and not indexes.empty:
        st.dataframe(indexes, width="stretch", hide_index=True)
    if market.get("errors"):
        with st.expander("查看市场数据获取提示"):
            st.write(market["errors"])
    if market.get("数据限制") or market.get("limitations"):
        st.caption(str(market.get("数据限制") or market.get("limitations")))


def render_ranking(decisions_df: pd.DataFrame) -> None:
    st.subheader("股票风险排行榜")
    ranking = decisions_df[["股票名称", "股票代码", "当前价格", "风险评分", "风险等级", "建议操作"]].copy()
    st.dataframe(ranking, width="stretch", hide_index=True)
    st.download_button(
        "导出分析结果",
        data=dataframe_to_csv_bytes(decisions_df[SUMMARY_COLUMNS]),
        file_name="个人量化股票分析结果.csv",
        mime="text/csv",
    )


def render_stock_detail(
    selected_code: str,
    decisions_df: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    show_candlestick: bool,
) -> None:
    decision = decisions_df[decisions_df["股票代码"] == selected_code].iloc[0]
    history = histories[selected_code]

    st.subheader("集合竞价分析")
    auction = decision["竞价分析"]
    auction_cols = st.columns(6)
    auction_cols[0].metric("昨日收盘价", str(auction["昨日收盘价"]))
    auction_cols[1].metric("今日竞价价格", str(auction["今日竞价价格"]))
    auction_cols[2].metric("竞价涨跌幅", f"{auction['竞价涨跌幅']}%")
    auction_cols[3].metric("竞价成交量", f"{auction['竞价成交量']:.0f}")
    auction_cols[4].metric("竞价成交额", f"{auction['竞价成交额']:.0f}")
    auction_cols[5].metric("竞价量比", str(auction["竞价量比"]))
    st.write(f"今日可能走势：{auction['今日可能走势']}")
    st.write(
        f"历史相似情况：过去60个交易日出现 {auction['历史相似次数']} 次，"
        f"顺势概率 {auction['顺势概率']}%。"
    )
    st.caption(str(auction["数据说明"]))
    period_stats = auction.get("历史分周期统计")
    if isinstance(period_stats, pd.DataFrame) and not period_stats.empty:
        st.markdown("**集合竞价历史分周期概率**")
        st.dataframe(period_stats, width="stretch", hide_index=True)

    st.subheader("早盘方向确认")
    morning = decision["早盘方向预测"]
    morning_cols = st.columns(5)
    morning_cols[0].metric("开盘涨跌幅", f"{morning['开盘涨跌幅']}%")
    morning_cols[1].metric("开盘5分钟走势", str(morning["开盘5分钟走势"]))
    morning_cols[2].metric("开盘15分钟走势", str(morning["开盘15分钟走势"]))
    morning_cols[3].metric("分时均价线", str(morning["分时均价线"]))
    morning_cols[4].metric("买卖力量", str(morning["买卖力量变化"]))
    st.write(f"当前价格：{morning['当前价格']}，均价线状态：{morning['均价线状态']}，成交量变化：{morning['成交量变化']}。")

    st.subheader("分时均价线突破概率模型")
    st.dataframe(pd.DataFrame([morning["分时突破模型"]]), width="stretch", hide_index=True)
    realtime = decision.get("实时交易决策", {})
    intraday = realtime.get("分时黄线分析", {}) if isinstance(realtime, dict) else {}
    yellow_probability = intraday.get("突破概率表")
    if isinstance(yellow_probability, pd.DataFrame) and not yellow_probability.empty:
        st.markdown("**黄线突破/跌破历史概率**")
        st.dataframe(yellow_probability, width="stretch", hide_index=True)

    st.subheader("跌破均价线风险模型")
    st.dataframe(pd.DataFrame([morning["跌破均价线模型"]]), width="stretch", hide_index=True)

    st.subheader("均线买入评估明细")
    st.dataframe(decision["四周期买入评估"]["评估表"], width="stretch", hide_index=True)

    st.subheader("历史概率数据库")
    st.dataframe(decision["历史概率数据库"], width="stretch", hide_index=True)

    st.subheader("历史走势统计")
    st.dataframe(decision["历史走势统计"], width="stretch", hide_index=True)
    similar = decision["历史相似走势"]
    st.info(f"{similar['历史相似走势']}，次日上涨概率 {similar['次日上涨概率']}%。")

    st.subheader("今日涨跌原因")
    reason = decision["今日涨跌原因"]
    reason_cols = st.columns(3)
    reason_cols[0].metric("市场贡献", str(reason["市场贡献"]))
    reason_cols[1].metric("行业贡献", str(reason["行业贡献"]))
    reason_cols[2].metric("个股资金", str(reason["个股资金"]))
    st.write(reason["今日涨跌原因"])
    st.write(f"市场影响：{reason['市场影响']}")
    st.write(f"行业影响：{reason['行业影响']}")
    st.write(f"个股趋势：{reason['个股趋势']}")
    st.write(f"成交量变化：{reason['成交量变化']}")

    st.subheader("历史回测")
    st.dataframe(pd.DataFrame([decision["历史回测"]]), width="stretch", hide_index=True)

    with st.expander("展开查看详细数据"):
        detail = history.tail(30).rename(columns=DETAIL_COLUMNS)
        st.dataframe(detail, width="stretch", hide_index=True)
        st.plotly_chart(
            make_price_chart(history, f"{decision['股票名称']}（{selected_code}）", show_candlestick),
            use_container_width=True,
            key=f"详细价格走势_{selected_code}",
        )


@st.cache_data(ttl=5, show_spinner=False)
def cached_analyze_realtime_stock_pool(codes: tuple[str, ...], refresh_interval: int, cache_version: str):
    del refresh_interval, cache_version
    return analyze_realtime_stock_pool(list(codes))


def inject_auto_refresh(seconds: int) -> None:
    components.html(
        f"""
        <script>
        setTimeout(function() {{
            window.parent.location.reload();
        }}, {int(seconds) * 1000});
        </script>
        """,
        height=0,
    )


def make_price_chart(history: pd.DataFrame, title: str, show_candlestick: bool) -> go.Figure:
    recent = history.tail(80)
    fig = go.Figure()
    if show_candlestick:
        fig.add_trace(
            go.Candlestick(
                x=recent["date"],
                open=recent["open"],
                high=recent["high"],
                low=recent["low"],
                close=recent["close"],
                name="价格K线",
            )
        )
    else:
        fig.add_trace(go.Scatter(x=recent["date"], y=recent["close"], mode="lines+markers", name="收盘价"))

    for column, label in [("ma5", "5日均线"), ("ma10", "10日均线"), ("ma20", "20日均线"), ("ma30", "30日均线")]:
        fig.add_trace(go.Scatter(x=recent["date"], y=recent[column], mode="lines", name=label))

    fig.update_layout(
        title=f"{title} 价格走势",
        xaxis_title="日期",
        yaxis_title="价格",
        height=520,
        margin=dict(l=10, r=10, t=50, b=10),
        xaxis_rangeslider_visible=False,
    )
    return fig


if __name__ == "__main__":
    main()
