# @ai-generated
"""
定时任务手动调用验证脚本

用途：在不依赖 APScheduler 触发的情况下，直接调用 scheduler_jobs 中的任务函数，
      验证业务逻辑正确性（DB 查询 / 聚合 / 缓存失效链路）。

运行方式（在 backend/ 目录下）：
    .venv/bin/python -m tests.manual_scheduler_jobs            # 默认：Task1 试运行 + Task2 真实执行
    .venv/bin/python -m tests.manual_scheduler_jobs --task1-exec   # Task1 真实关闭（会改库，谨慎）

说明：
- Task1（超时关单）默认 DRY_RUN，仅查询并打印将被关闭的订单，不真正改库；
  加 --task1-exec 才会真正调用 OrderDAO.close_expired_unpaid_orders 执行关闭。
- Task2（每日佣金对账）为只读聚合 + 缓存失效，直接真实执行，无副作用。
- Redis 未连通时缓存失效仅打 warning，不影响主流程（RedisClient 各操作已兜底异常）。
"""
import argparse
import asyncio
import logging
from datetime import datetime, timedelta

from src.config.constants import OrderStatus, TASK_ORDER_EXPIRE_MINUTES
from src.config.env_config import EnvConfig
from src.dao.order_dao import OrderDAO
from src.db.init_db import DatabaseManager
from src.common.redis_client import RedisClient
from src.scheduler.scheduler_jobs import (
    close_expired_unpaid_orders,
    daily_commission_reconciliation,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("manual_test")


def init_infra() -> None:
    EnvConfig.load()
    EnvConfig.validate()
    DatabaseManager.initialize()
    RedisClient.initialize()


async def task1_dry_run() -> None:
    """Task1 试运行：只查询待关闭订单，不真正改库"""
    cutoff = datetime.now() - timedelta(minutes=TASK_ORDER_EXPIRE_MINUTES)
    logger.info("==== Task1 DRY-RUN: close_expired_unpaid_orders ====")
    logger.info("cutoff=%s, condition: order_status=PENDING(%s) & create_time<cutoff",
                cutoff, int(OrderStatus.PENDING))
    async with DatabaseManager.get_session() as db:
        order_dao = OrderDAO(db)
        # 复用 DAO 的查询语义：list_all 取待支付单，再按 create_time 过滤
        pending = await order_dao.list_all(filters={"order_status": int(OrderStatus.PENDING)})
    expired = [o for o in pending if o.create_time and o.create_time < cutoff]
    logger.info("待支付订单总数=%s, 其中超时待关闭=%s", len(pending), len(expired))
    for o in expired[:20]:
        logger.info("  将关闭: id=%s out_order_no=%s create_time=%s pay_amount=%s",
                    o.id, o.out_order_no, o.create_time, o.pay_amount)
    if len(expired) > 20:
        logger.info("  ... 另外 %s 笔略", len(expired) - 20)


async def task1_real_exec() -> None:
    """Task1 真实执行：调用任务函数（会改库）"""
    logger.info("==== Task1 REAL-EXEC: close_expired_unpaid_orders ====")
    result = await close_expired_unpaid_orders()
    logger.info("Task1 result: %s", result)


async def task2_exec() -> None:
    """Task2 真实执行：每日佣金对账（只读）"""
    logger.info("==== Task2 EXEC: daily_commission_reconciliation ====")
    result = await daily_commission_reconciliation()
    logger.info("Task2 result: %s", result)


async def main(task1_exec: bool) -> None:
    init_infra()
    try:
        if task1_exec:
            await task1_real_exec()
        else:
            await task1_dry_run()
        await task2_exec()
    finally:
        await RedisClient.close()
        await DatabaseManager.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="定时任务手动验证")
    parser.add_argument(
        "--task1-exec",
        action="store_true",
        help="Task1 真实执行关闭（默认 dry-run，不真正改库）",
    )
    args = parser.parse_args()
    asyncio.run(main(args.task1_exec))
