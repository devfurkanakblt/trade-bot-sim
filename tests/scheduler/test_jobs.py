from src.scheduler.jobs import build_scheduler


def noop():
    pass


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
