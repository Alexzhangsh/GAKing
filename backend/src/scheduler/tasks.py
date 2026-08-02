# @ai-generated
import logging
import traceback
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

# 修复点(2026-08-01): system_config_util / channel_mapping_util 内部仍引用
# 已迁移至 src/models/system/ 的 GakingSystemConfig / GakingChannelMapping，
# 触发 ImportError 导致项目无法启动。本次仅在本文件移除这两个 util 导入，
# 对应缓存刷新函数降级为空骨架，待 util 模块修复后恢复。
from src.common.lock_util import LockUtil
from src.scheduler.scheduler import TaskScheduler
from src.scheduler.scheduler_jobs import register_scheduler_jobs
from src.config.env_config import EnvConfig
from src.db.init_db import DatabaseManager
from src.db.models import GakingTaskStatus

logger = logging.getLogger(__name__)


async def _record_task_status(db: AsyncSession, task_name: str, status: str, message: str = "", 
                             retry_count: int = 0, error_stack: str = ""):
    try:
        status_record = GakingTaskStatus(
            task_name=task_name,
            status=status,
            message=message,
            retry_count=retry_count,
            error_stack=error_stack[:4000] if error_stack else ""
        )
        db.add(status_record)
        await db.commit()
        logger.debug(f"Task status recorded: {task_name} -> {status}")
    except Exception as e:
        logger.error(f"Failed to record task status: {str(e)}")


async def _run_with_retry_and_status(task_name: str, func, *args, **kwargs):
    max_retry = EnvConfig.SCHEDULER_RETRY_MAX
    retry_count = 0
    
    async with DatabaseManager.get_session() as db:
        await _record_task_status(db, task_name, "running", "任务开始执行")
    
    while retry_count <= max_retry:
        try:
            async with LockUtil.acquire(f"scheduler:{task_name}", timeout=60):
                result = await func(*args, **kwargs)
                
                async with DatabaseManager.get_session() as db:
                    await _record_task_status(db, task_name, result.get("status", "success"), 
                                            result.get("message", ""), retry_count)
                
                return result
        except Exception as e:
            retry_count += 1
            error_stack = traceback.format_exc()
            logger.error(f"Task {task_name} failed (retry {retry_count}/{max_retry}): {str(e)}")
            
            async with DatabaseManager.get_session() as db:
                await _record_task_status(db, task_name, "failed", str(e), retry_count, error_stack)
            
            if retry_count >= max_retry:
                logger.error(f"Task {task_name} exhausted all retries")
                return {"status": "failed", "message": f"任务执行失败，已重试{max_retry}次: {str(e)}"}


async def refresh_system_config_cache():
    # TODO: 系统配置缓存刷新逻辑【待 SystemConfigUtil 模型迁移修复后恢复】
    logger.info(f"System config cache refresh skipped (skeleton) at {datetime.now()}")
    return {"status": "success", "message": "系统配置缓存刷新（预留）"}


async def refresh_channel_mapping_cache():
    # TODO: 渠道映射缓存刷新逻辑【待 ChannelMappingUtil 模型迁移修复后恢复】
    logger.info(f"Channel mapping cache refresh skipped (skeleton) at {datetime.now()}")
    return {"status": "success", "message": "渠道映射缓存刷新（预留）"}


async def sync_order_status():
    try:
        if not EnvConfig.SCHEDULER_ENABLE:
            return {"status": "skipped", "message": "定时任务未启用"}
        
        logger.info(f"Order status sync task started at {datetime.now()}")
        
        # TODO: 渠道专属订单状态同步逻辑【待渠道适配】
        # - 调用各渠道API获取订单状态
        # - 更新本地订单状态
        # - 处理订单结算逻辑
        
        logger.info(f"Order status sync task completed at {datetime.now()}")
        return {"status": "success", "message": "订单状态同步完成（预留）"}
    except Exception as e:
        logger.error(f"Failed to sync order status: {str(e)}")
        return {"status": "failed", "message": str(e)}


async def clean_expired_data():
    try:
        logger.info(f"Expired data cleaning task started at {datetime.now()}")
        
        # TODO: 清理过期数据逻辑
        # - 清理过期的临时文件
        # - 清理过期的日志记录
        # - 清理过期的缓存数据
        
        logger.info(f"Expired data cleaning task completed at {datetime.now()}")
        return {"status": "success", "message": "过期数据清理完成（预留）"}
    except Exception as e:
        logger.error(f"Failed to clean expired data: {str(e)}")
        return {"status": "failed", "message": str(e)}


def register_tasks():
    if not EnvConfig.SCHEDULER_ENABLE:
        logger.info("Scheduler is disabled, skip registering tasks")
        return
    
    TaskScheduler.add_cron_task(
        func=_run_with_retry_and_status,
        name="refresh_system_config_cache",
        cron_expr=EnvConfig.SCHEDULER_CRON_SYNC_CONFIG,
        args=("refresh_system_config_cache", refresh_system_config_cache),
    )
    
    TaskScheduler.add_cron_task(
        func=_run_with_retry_and_status,
        name="refresh_channel_mapping_cache",
        cron_expr=EnvConfig.SCHEDULER_CRON_UPDATE_CHANNEL_MAPPING,
        args=("refresh_channel_mapping_cache", refresh_channel_mapping_cache),
    )
    
    TaskScheduler.add_cron_task(
        func=_run_with_retry_and_status,
        name="sync_order_status",
        cron_expr=EnvConfig.SCHEDULER_CRON_SYNC_ORDER_STATUS,
        args=("sync_order_status", sync_order_status),
    )
    
    TaskScheduler.add_cron_task(
        func=_run_with_retry_and_status,
        name="clean_expired_data",
        cron_expr=EnvConfig.SCHEDULER_CRON_CLEAN_EXPIRED_DATA,
        args=("clean_expired_data", clean_expired_data),
    )

    # 业务定时任务（超时关单 / 每日佣金对账）：注册逻辑见 scheduler_jobs.py
    register_scheduler_jobs()

    logger.info("All scheduled tasks registered")