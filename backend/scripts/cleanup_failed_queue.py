#!/usr/bin/env python3
# @ai-generated
"""
S04 P2-3 渠道失败队列积压处理脚本

积压分析（2026-08-14）：
  渠道    | 失败队列长度 | 原因
  myq     | 269         | 服务器IP 183.195.100.175 未加入喵有券API白名单（需联系喵有券运营）
  orderx  | 250         | 渠道停用，无有效密钥（8月11日历史积压）
  dta     | 232         | 渠道停用，无有效密钥（8月11日历史积压）

处理策略：
  1. 订单侠(orderx) + 大淘客(dta)：渠道S04停用，积压数据永不可达 ⇒ 清理失效队列
  2. 喵有券(myq)：IP白名单问题解决后，调用补发脚本重试

运行方式：
  cd backend && python3 scripts/cleanup_failed_queue.py

运行环境：本地开发环境（需Redis + 远程DB可达）
"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.redis_client import RedisClient
from src.config.constants import CACHE_KEY_ORDER_SYNC_FAILED
from src.config.env_config import EnvConfig
from src.config.constants import CACHE_TTL_ORDER_SYNC_FAILED

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("cleanup_failed_queue")


async def check_queue(channel_code: str) -> dict:
    """检查渠道失败队列长度"""
    failed_key = f"{CACHE_KEY_ORDER_SYNC_FAILED}{channel_code}"
    length = await RedisClient.llen(failed_key)
    # 取前3条样本看内容
    samples = []
    raw_list = await RedisClient.lrange(failed_key, 0, 2)
    for raw in raw_list:
        try:
            samples.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            samples.append({"raw_truncated": str(raw)[:200]})
    return {"channel": channel_code, "length": length, "samples": samples}


async def cleanup_stale_channel(channel_code: str, reason: str) -> dict:
    """清理停用渠道的过期失败队列

    操作：删除 Redis key，使队列不可恢复
    """
    failed_key = f"{CACHE_KEY_ORDER_SYNC_FAILED}{channel_code}"
    before = await RedisClient.llen(failed_key)
    await RedisClient.delete(failed_key)
    after = await RedisClient.llen(failed_key)
    logger.info("[清理] %s: 删除前=%s 删除后=%s 原因=%s", channel_code, before, after, reason)
    return {"channel": channel_code, "before": before, "after": after, "reason": reason}


async def retry_failed_queue(channel_code: str, max_items: int = 20) -> dict:
    """补发指定渠道的失败队列

    调用 OrderSyncService.manual_retry_failed 补发。
    注意：需确保渠道API可用（密钥有效、IP白名单已配置）。
    """
    from src.db.init_db import DatabaseManager
    from src.dao.order_sync_dao import OrderSyncDAO
    from src.services.order_sync_service import OrderSyncService

    async with DatabaseManager.get_session() as session:
        dao = OrderSyncDAO(session)
        svc = OrderSyncService(dao)
        result = await svc.manual_retry_failed(
            channel_code=channel_code,
            batch_size=max_items,
        )
    logger.info(
        "[补发] %s: 尝试=%s 成功=%s 仍失败=%s 状态=%s",
        channel_code,
        result.get("retried_count"),
        result.get("success_count"),
        result.get("still_failed_count"),
        result.get("status"),
    )
    return result


async def main() -> None:
    EnvConfig.load()
    RedisClient.initialize()

    logger.info("=" * 60)
    logger.info("S04 P2-3 渠道失败队列积压处理")
    logger.info("=" * 60)

    # 1. 检查各渠道队列状态
    logger.info("\n--- 1. 检查失败队列现状 ---")
    for code in ["myq", "orderx", "dta"]:
        info = await check_queue(code)
        logger.info("  %s: %s 条", info["channel"], info["length"])
        if info["samples"]:
            sample = info["samples"][0]
            logger.info("    样本错误: %s", sample.get("error", sample.get("raw_truncated", "N/A"))[:120])

    # 2. 清理停用渠道的过期积压
    logger.info("\n--- 2. 清理停用渠道过期积压 ---")
    results = []
    results.append(await cleanup_stale_channel(
        "orderx",
        "S04 停用渠道，无有效密钥，历史积压永不可达",
    ))
    results.append(await cleanup_stale_channel(
        "dta",
        "S04 停用渠道，无有效密钥，历史积压永不可达",
    ))

    # 3. 关于喵有券补发说明
    logger.info("\n--- 3. 喵有券失败队列（保留，待 IP 白名单解决后补发） ---")
    myq_info = await check_queue("myq")
    logger.info("  myq: %s 条（保留）", myq_info["length"])
    logger.info("  原因: 服务器IP 183.195.100.175 未加入喵有券API白名单")
    logger.info("  操作: 联系喵有券运营将IP加入白名单后，执行补发：")
    logger.info("    cd backend && python3 -c \"")
    logger.info("    import asyncio")
    logger.info("    from scripts.cleanup_failed_queue import retry_failed_queue")
    logger.info("    from src.config.env_config import EnvConfig")
    logger.info("    from src.common.redis_client import RedisClient")
    logger.info("    EnvConfig.load(); RedisClient.initialize()")
    logger.info("    asyncio.run(retry_failed_queue('myq', 100))")
    logger.info("    \"")

    logger.info("\n" + "=" * 60)
    logger.info("清理完成。结果汇总：")
    for r in results:
        logger.info("  %s: 已清理 %s 条记录", r["channel"], r["before"])
    logger.info("  myq: %s 条保留，待 IP 白名单解决后手动补发", myq_info["length"])
    logger.info("=" * 60)

    await RedisClient.close()


if __name__ == "__main__":
    asyncio.run(main())