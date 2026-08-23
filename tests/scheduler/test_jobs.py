from src.scheduler.jobs import build_scheduler


def noop():
    pass


def test_tick_job_runs_once_per_minute_after_candle_close():
    scheduler = build_scheduler(noop, noop, noop)
    tick_job = scheduler.get_job("minute_tick")
    assert "second='5'" in str(tick_job.trigger)


def test_build_scheduler_registers_three_jobs():
    scheduler = build_scheduler(noop, noop, noop)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 3


def test_scheduler_uses_istanbul_timezone():
    scheduler = build_scheduler(noop, noop, noop)
    assert str(scheduler.timezone) == "Europe/Istanbul"


def test_daily_job_trigger_fires_at_midnight():
    scheduler = build_scheduler(noop, noop, noop)
    daily_job = scheduler.get_job("daily_report")
    assert "minute='0'" in str(daily_job.trigger)


def test_hourly_snapshot_runs_at_minute_two():
    scheduler = build_scheduler(noop, noop, noop)
    snapshot_job = scheduler.get_job("hourly_snapshot")
    assert "minute='2'" in str(snapshot_job.trigger)
    assert "second='0'" in str(snapshot_job.trigger)


def test_default_executor_is_limited_to_a_single_worker():
    # Delayed jobs may become due together, so the default executor must stay
    # pinned to one worker around shared SQLite and in-memory portfolio state.
    scheduler = build_scheduler(noop, noop, noop)
    executor = scheduler._executors["default"]
    assert executor._pool._max_workers == 1
