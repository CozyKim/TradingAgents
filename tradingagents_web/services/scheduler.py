"""APScheduler wrapper.

The DB ``schedules`` table is the source of truth. On startup,
:meth:`SchedulerService.bootstrap` reads all ``active=True`` rows and
registers them with the in-process AsyncIOScheduler. CRUD endpoints
keep the scheduler in sync via :meth:`register` / :meth:`unregister`.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.models import Schedule

logger = logging.getLogger(__name__)

TriggerCallback = Callable[[int], Awaitable[None]]


class SchedulerService:
    """Owns a single AsyncIOScheduler instance."""

    def __init__(self, tz: str = "America/New_York", grace_seconds: int = 60) -> None:
        self.scheduler = AsyncIOScheduler(
            timezone=tz,
            job_defaults={
                "coalesce": True,
                "misfire_grace_time": grace_seconds,
                "max_instances": 1,
            },
        )
        self._tz = tz
        self._on_trigger: TriggerCallback | None = None

    def set_trigger_callback(self, cb: TriggerCallback) -> None:
        """Wire the coroutine that runs when any schedule fires."""
        self._on_trigger = cb

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def is_running(self) -> bool:
        return self.scheduler.running

    @staticmethod
    def _job_id(schedule_id: int) -> str:
        return f"sched-{schedule_id}"

    def get_job(self, schedule_id: int) -> Job | None:
        return self.scheduler.get_job(self._job_id(schedule_id))

    async def _fire(self, schedule_id: int) -> None:
        if self._on_trigger is None:
            logger.warning("Scheduler fired with no trigger callback (id=%s)", schedule_id)
            return
        try:
            await self._on_trigger(schedule_id)
        except Exception:  # noqa: BLE001
            logger.exception("Scheduler trigger callback failed (id=%s)", schedule_id)

    def register(self, schedule: Schedule) -> None:
        """Add or replace the APScheduler job for ``schedule``."""
        if not schedule.active:
            self.unregister(schedule.id)
            return
        tz = getattr(schedule, "timezone", None) or self._tz
        trigger = CronTrigger.from_crontab(schedule.cron_expr, timezone=tz)
        self.scheduler.add_job(
            self._fire,
            trigger=trigger,
            id=self._job_id(schedule.id),
            args=[schedule.id],
            replace_existing=True,
        )

    def unregister(self, schedule_id: int) -> None:
        try:
            self.scheduler.remove_job(self._job_id(schedule_id))
        except Exception:  # noqa: BLE001
            pass  # idempotent

    def next_run(self, schedule_id: int) -> datetime | None:
        job = self.get_job(schedule_id)
        return job.next_run_time if job else None

    def bootstrap(self, db: OrmSession) -> None:
        """Register every ``active=True`` schedule from DB into the scheduler."""
        rows = db.query(Schedule).filter(Schedule.active.is_(True)).all()
        for r in rows:
            self.register(r)
        logger.info("Bootstrap registered %d schedules", len(rows))


_singleton: SchedulerService | None = None


def get_scheduler() -> SchedulerService:
    """Module-global accessor (lifespan creates it on app startup)."""
    if _singleton is None:
        raise RuntimeError("SchedulerService is not initialized")
    return _singleton


def set_scheduler(svc: SchedulerService | None) -> None:
    """Inject (or clear) the global scheduler. Used by lifespan + tests."""
    global _singleton
    _singleton = svc
