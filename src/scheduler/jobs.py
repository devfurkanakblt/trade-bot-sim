from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger


def build_scheduler(hourly_tick_fn, daily_report_fn) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="Europe/Istanbul")
    scheduler.add_job(hourly_tick_fn, CronTrigger(minute=0))
    scheduler.add_job(daily_report_fn, CronTrigger(hour=0, minute=0))
    return scheduler
