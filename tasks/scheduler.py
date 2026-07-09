from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler

from tasks.daily_jobs import generate_daily_report, generate_morning_signal, update_auction_data, update_market_data
from utils.logger import get_logger


logger = get_logger(__name__)


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(update_market_data, "cron", hour=8, minute=50, id="update_market_data")
    scheduler.add_job(update_auction_data, "cron", hour=9, minute=25, id="update_auction_data")
    scheduler.add_job(generate_morning_signal, "cron", hour=10, minute=50, id="generate_morning_signal")
    scheduler.add_job(generate_daily_report, "cron", hour=15, minute=30, id="generate_daily_report")
    return scheduler


if __name__ == "__main__":
    logger.info("启动定时任务服务")
    build_scheduler().start()
