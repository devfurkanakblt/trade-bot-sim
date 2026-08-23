from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger


def build_scheduler(minute_tick_fn, hourly_snapshot_fn, daily_report_fn) -> BlockingScheduler:
    # All jobs share one SQLite connection and the in-memory portfolios.
    # Pinning the executor to one worker serializes them even after a delayed
    # start or misfire causes two schedules to become due together.
    scheduler = BlockingScheduler(
        timezone="Europe/Istanbul",
        executors={"default": ThreadPoolExecutor(max_workers=1)},
    )
    # Binance's latest 1m kline is still forming until the minute boundary.
    # Running five seconds into each minute gives the API time to publish the
    # just-closed candle and prevents repeatedly evaluating the same candle.
    scheduler.add_job(
        minute_tick_fn,
        CronTrigger(second=5),
        id="minute_tick",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=30,
    )
    scheduler.add_job(
        hourly_snapshot_fn,
        CronTrigger(minute=2, second=0),
        id="hourly_snapshot",
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        daily_report_fn,
        CronTrigger(hour=0, minute=0, second=0),
        id="daily_report",
        coalesce=True,
        max_instances=1,
    )
    return scheduler
