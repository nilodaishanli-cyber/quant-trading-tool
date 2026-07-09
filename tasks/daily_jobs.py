from __future__ import annotations

from utils.logger import get_logger


logger = get_logger(__name__)


def update_market_data() -> None:
    logger.info("08:50 更新市场数据：待接入数据库缓存写入")


def update_auction_data() -> None:
    logger.info("09:25 更新集合竞价数据：待接入 Level-2 或第三方数据源")


def generate_morning_signal() -> None:
    logger.info("10:50 生成早盘多空判断：待读取个人股票池并落库")


def generate_daily_report() -> None:
    logger.info("15:30 生成当天复盘报告：待接入报告生成服务")
