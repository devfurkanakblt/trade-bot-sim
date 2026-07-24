from src.scheduler.jobs import build_scheduler


def noop():
    pass


def test_tick_job_uses_five_second_interval_trigger():
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = build_scheduler(noop, noop)
    tick_job = scheduler.get_jobs()[0]
    assert isinstance(tick_job.trigger, IntervalTrigger)
    assert tick_job.trigger.interval.total_seconds() == 5


def test_build_scheduler_registers_two_jobs():
    scheduler = build_scheduler(noop, noop)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 2


def test_scheduler_uses_istanbul_timezone():
    scheduler = build_scheduler(noop, noop)
    assert str(scheduler.timezone) == "Europe/Istanbul"


def test_daily_job_trigger_fires_at_midnight():
    scheduler = build_scheduler(noop, noop)
    daily_job = next(j for j in scheduler.get_jobs() if j.func is noop and "hour='0'" in str(j.trigger))
    assert "minute='0'" in str(daily_job.trigger)


def test_default_executor_is_limited_to_a_single_worker():
    # At 00:00 the hourly tick (minute=0) and the daily report (hour=0,
    # minute=0) triggers both match, so APScheduler's default multi-worker
    # thread pool could run them concurrently against the shared SQLite
    # connection and in-memory portfolio state. The default executor must be
    # pinned to a single worker thread so job runs are always serialized.
    scheduler = build_scheduler(noop, noop)
    executor = scheduler._executors["default"]
    assert executor._pool._max_workers == 1
