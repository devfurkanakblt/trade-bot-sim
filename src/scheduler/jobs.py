from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


def build_scheduler(minute_tick_fn, daily_report_fn) -> BlockingScheduler:
    # At 00:00 both the minute tick and the daily report (hour=0, minute=0)
    # triggers match, so APScheduler's default multi-worker executor could run
    # them concurrently on the shared SQLite connection and in-memory portfolio
    # state. Pinning the default executor to a single worker thread serializes
    # all job runs, so the two jobs can never execute at the same time.
    scheduler = BlockingScheduler(
        timezone="Europe/Istanbul",
        executors={"default": ThreadPoolExecutor(max_workers=1)},
    )
    scheduler.add_job(minute_tick_fn, IntervalTrigger(minutes=1))
    scheduler.add_job(daily_report_fn, CronTrigger(hour=0, minute=0))
    return scheduler
