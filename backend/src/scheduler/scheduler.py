# @ai-generated
import asyncio
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.config.env_config import EnvConfig
from src.common.lock_util import LockUtil
from src.config.constants import LockTimeout


class TaskScheduler:
    _scheduler: AsyncIOScheduler = None
    _lock_key_prefix = "scheduler:task:"

    @classmethod
    def initialize(cls) -> None:
        if cls._scheduler is not None:
            return
        
        cls._scheduler = AsyncIOScheduler(
            timezone='Asia/Shanghai',
            job_defaults={
                'max_instances': 1,
                'coalesce': False,
            }
        )

    @classmethod
    def start(cls) -> None:
        if cls._scheduler is None:
            cls.initialize()
        cls._scheduler.start()

    @classmethod
    def shutdown(cls, wait: bool = True) -> None:
        if cls._scheduler is not None:
            cls._scheduler.shutdown(wait=wait)
            cls._scheduler = None

    @classmethod
    def add_cron_task(cls, func, name: str, cron_expr: str, **kwargs) -> None:
        if cls._scheduler is None:
            cls.initialize()
        
        trigger = CronTrigger.from_crontab(cron_expr, timezone='Asia/Shanghai')
        cls._scheduler.add_job(
            func,
            trigger=trigger,
            id=name,
            name=name,
            **kwargs
        )

    @classmethod
    def add_interval_task(cls, func, name: str, minutes: int = 60, **kwargs) -> None:
        if cls._scheduler is None:
            cls.initialize()
        
        trigger = IntervalTrigger(minutes=minutes, timezone='Asia/Shanghai')
        cls._scheduler.add_job(
            func,
            trigger=trigger,
            id=name,
            name=name,
            **kwargs
        )

    @classmethod
    def remove_task(cls, name: str) -> bool:
        if cls._scheduler is None:
            return False
        
        try:
            cls._scheduler.remove_job(name)
            return True
        except Exception:
            return False

    @classmethod
    def pause_task(cls, name: str) -> bool:
        if cls._scheduler is None:
            return False
        
        try:
            cls._scheduler.pause_job(name)
            return True
        except Exception:
            return False

    @classmethod
    def resume_task(cls, name: str) -> bool:
        if cls._scheduler is None:
            return False
        
        try:
            cls._scheduler.resume_job(name)
            return True
        except Exception:
            return False

    @classmethod
    def get_task_status(cls, name: str) -> Optional[str]:
        if cls._scheduler is None:
            return None
        
        job = cls._scheduler.get_job(name)
        if job:
            return job.next_run_time.isoformat() if job.next_run_time else 'paused'
        return None

    @classmethod
    def get_all_tasks(cls) -> list:
        if cls._scheduler is None:
            return []
        
        jobs = cls._scheduler.get_jobs()
        return [{
            'id': job.id,
            'name': job.name,
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
            'status': 'running' if job.next_run_time else 'paused'
        } for job in jobs]

    @classmethod
    async def with_task_lock(cls, task_name: str, func, *args, **kwargs):
        lock_key = f"{cls._lock_key_prefix}{task_name}"
        owner = await LockUtil.acquire_lock(lock_key, timeout=LockTimeout.TASK)
        
        if not owner:
            return None
        
        try:
            return await func(*args, **kwargs)
        finally:
            await LockUtil.release_lock(lock_key, owner)