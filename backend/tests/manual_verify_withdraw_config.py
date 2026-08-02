# @ai-generated
"""临时验证脚本：PayConfigUtil 动态配置 + 兜底降级"""
import asyncio

from sqlalchemy import text

from src.common.pay_config_util import PayConfigUtil
from src.common.redis_client import RedisClient
from src.db.init_db import DatabaseManager


async def main() -> None:
    DatabaseManager.initialize()
    RedisClient.initialize()

    # 清空旧配置行 + 清缓存
    async with DatabaseManager.get_session() as s:
        await s.execute(text("DELETE FROM gaking_pay_config"))
        await s.commit()
    await RedisClient.delete("gaking:prod:config:withdraw")

    # ── 场景1：动态配置 rate=0.002(0.2%) min_fee=2.00 ──
    async with DatabaseManager.get_session() as s:
        await s.execute(
            text(
                "INSERT INTO gaking_pay_config (mch_id, status, withdraw_rate, withdraw_min_fee, is_delete, create_time, update_time) "
                "VALUES ('TESTMCH', 1, 0.002, 2.00, 0, NOW(), NOW())"
            )
        )
        await s.commit()
    cfg = await PayConfigUtil.get_withdraw_config()
    print(f"[动态] rate={cfg.rate} min_fee={cfg.min_fee} (期望 0.002 / 2.00)")

    # ── 场景2：字段置 NULL → 兜底常量 ──
    await PayConfigUtil.invalidate()
    async with DatabaseManager.get_session() as s:
        await s.execute(
            text("UPDATE gaking_pay_config SET withdraw_rate=NULL, withdraw_min_fee=NULL")
        )
        await s.commit()
    cfg2 = await PayConfigUtil.get_withdraw_config()
    print(f"[兜底] rate={cfg2.rate} min_fee={cfg2.min_fee} (期望 0.001 / 1.00)")

    # ── 场景3：无启用行（删除）→ 兜底常量 ──
    await PayConfigUtil.invalidate()
    async with DatabaseManager.get_session() as s:
        await s.execute(text("DELETE FROM gaking_pay_config"))
        await s.commit()
    cfg3 = await PayConfigUtil.get_withdraw_config()
    print(f"[无行] rate={cfg3.rate} min_fee={cfg3.min_fee} (期望 0.001 / 1.00)")

    await RedisClient.close()
    await DatabaseManager.dispose()


if __name__ == "__main__":
    asyncio.run(main())
