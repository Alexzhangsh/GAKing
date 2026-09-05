# @ai-generated
"""
B16 商品预热定时任务手动调用验证脚本

六项定时任务功能校验：
1. warming_myq          喵有券渠道预热
2. warming_orderx        订单侠渠道预热
3. refresh_hot_myq       喵有券热门商品刷新
4. refresh_hot_orderx    订单侠热门商品刷新
5. refresh_normal_myq    喵有券普通商品刷新
6. refresh_normal_orderx 订单侠普通商品刷新
7. cleanup_expired_goods 冷品清理（过期标记 + 软删除）

运行方式（在 backend/ 目录下）：
    PYTHONPATH=. ENVIRONMENT=production .venv/bin/python -m tests.manual_b16_jobs
"""
import asyncio
import json
import logging
import sys
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("b16_manual_test")


def init_infra() -> None:
    from src.config.env_config import EnvConfig
    from src.db.init_db import DatabaseManager
    from src.common.redis_client import RedisClient

    EnvConfig.load()
    EnvConfig.validate()
    DatabaseManager.initialize()
    RedisClient.initialize()


async def run_task(task_name: str, func) -> dict:
    """执行单个任务并收集结果"""
    logger.info("=" * 60)
    logger.info(">>> 开始执行: %s", task_name)
    start = time.time()
    try:
        result = await func()
        elapsed = time.time() - start
        logger.info("<<< 完成执行: %s | 耗时=%.2fs | 结果=%s", task_name, elapsed, json.dumps(result, ensure_ascii=False, default=str))
        return {
            "task_name": task_name,
            "status": result.get("status", "unknown"),
            "elapsed": round(elapsed, 2),
            "result": result,
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - start
        logger.error("<<< 失败执行: %s | 耗时=%.2fs | 错误=%s", task_name, elapsed, str(e), exc_info=True)
        return {
            "task_name": task_name,
            "status": "error",
            "elapsed": round(elapsed, 2),
            "result": None,
            "error": str(e),
        }


async def main() -> None:
    from src.scheduler.goods_warming_jobs import (
        warming_myq,
        warming_orderx,
        refresh_hot_myq,
        refresh_hot_orderx,
        refresh_normal_myq,
        refresh_normal_orderx,
        cleanup_expired_goods,
    )
    from src.common.redis_client import RedisClient
    from src.db.init_db import DatabaseManager

    init_infra()

    tasks = [
        ("1. warming_myq", warming_myq),
        ("2. warming_orderx", warming_orderx),
        ("3. refresh_hot_myq", refresh_hot_myq),
        ("4. refresh_hot_orderx", refresh_hot_orderx),
        ("5. refresh_normal_myq", refresh_normal_myq),
        ("6. refresh_normal_orderx", refresh_normal_orderx),
        ("7. cleanup_expired_goods", cleanup_expired_goods),
    ]

    results = []
    for name, func in tasks:
        result = await run_task(name, func)
        results.append(result)
        # 任务间隔 2 秒，避免锁冲突
        await asyncio.sleep(2)

    # 汇总报告
    logger.info("")
    logger.info("=" * 60)
    logger.info("B16 定时任务手动调用测试报告")
    logger.info("=" * 60)
    logger.info("测试时间: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("测试任务数: %d", len(tasks))
    logger.info("-" * 60)

    passed = 0
    failed = 0
    skipped = 0

    for r in results:
        status = r["status"]
        icon = "✅" if status == "success" else "⏭️" if status == "skipped" else "❌"
        logger.info(
            "%s %s | status=%s | elapsed=%ss | %s",
            icon,
            r["task_name"],
            status,
            r["elapsed"],
            r["error"] or "",
        )
        if status == "success":
            passed += 1
        elif status == "skipped":
            skipped += 1
        else:
            failed += 1

    logger.info("-" * 60)
    logger.info("总计: 通过=%d 跳过=%d 失败=%d", passed, skipped, failed)
    logger.info("=" * 60)

    # 输出 JSON 结果供报告使用
    print("\n___JSON_RESULT___")
    print(json.dumps(results, ensure_ascii=False, default=str, indent=2))

    await RedisClient.close()
    await DatabaseManager.dispose()


if __name__ == "__main__":
    asyncio.run(main())
