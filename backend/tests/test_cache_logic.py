# @ai-generated
"""
CPS 订单/佣金缓存逻辑验证（内存模拟 Redis）

验证 OrderDAO.get_order_detail_cached / CommissionFlowDAO.sum_commission_by_order_id
的读穿、命中、主动失效逻辑。用内存 dict 模拟 RedisClient，确保不依赖真实 Redis。
运行: PYTHONPATH=. .venv/bin/python tests/test_cache_logic.py
"""
import asyncio
import json
import logging
import sys
from typing import Any, Optional

from src.common import redis_client as rc_mod
from src.common.redis_client import RedisClient
from src.config.constants import (
    CACHE_KEY_COMMISSION_SUM,
    CACHE_KEY_ORDER_DETAIL,
    OrderStatus,
)
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.order_dao import OrderDAO
from src.db.init_db import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

# ── 内存 Redis 模拟 ──────────────────────────────────
_STORE: dict[str, str] = {}
_CALLS: dict[str, int] = {"get": 0, "set": 0, "delete": 0}


def _install_mock_redis() -> None:
    """用内存 dict 替换 RedisClient 的读写方法"""

    @classmethod
    async def get(cls, key: str) -> Optional[str]:  # type: ignore[override]
        _CALLS["get"] += 1
        return _STORE.get(key)

    @classmethod
    async def set(cls, key, value, expire=None, ex=None):  # type: ignore[override]
        _CALLS["set"] += 1
        _STORE[key] = value if isinstance(value, str) else str(value)
        return True

    @classmethod
    async def set_json(cls, key, value, expire=None):  # type: ignore[override]
        _CALLS["set"] += 1
        _STORE[key] = json.dumps(value, ensure_ascii=False)
        return True

    @classmethod
    async def set_empty_cache(cls, key):  # type: ignore[override]
        _CALLS["set"] += 1
        _STORE[key] = "__EMPTY__"
        return True

    @classmethod
    async def is_empty_cache(cls, key):  # type: ignore[override]
        return _STORE.get(key) == "__EMPTY__"

    @classmethod
    async def delete(cls, key):  # type: ignore[override]
        _CALLS["delete"] += 1
        return _STORE.pop(key, None) is not None

    @classmethod
    async def exists(cls, key):  # type: ignore[override]
        return 1 if key in _STORE else 0

    @classmethod
    async def ttl(cls, key):  # type: ignore[override]
        return 600 if key in _STORE else -2

    RedisClient.get = get  # type: ignore[assignment]
    RedisClient.set = set  # type: ignore[assignment]
    RedisClient.set_json = set_json  # type: ignore[assignment]
    RedisClient.set_empty_cache = set_empty_cache  # type: ignore[assignment]
    RedisClient.is_empty_cache = is_empty_cache  # type: ignore[assignment]
    RedisClient.delete = delete  # type: ignore[assignment]
    RedisClient.exists = exists  # type: ignore[assignment]
    RedisClient.ttl = ttl  # type: ignore[assignment]


PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  {detail}")


async def main() -> int:
    _install_mock_redis()
    DatabaseManager.initialize()

    # 用已 commit 的种子订单 order_id=12（含一条 16.00 佣金流水）
    ORDER_ID = 12
    order_key = f"{CACHE_KEY_ORDER_DETAIL}{ORDER_ID}"
    sum_key = f"{CACHE_KEY_COMMISSION_SUM}{ORDER_ID}"

    async with DatabaseManager.get_session() as session:
        order_dao = OrderDAO(session)
        flow_dao = CommissionFlowDAO(session)

        print("\n【1】订单详情缓存 —— 读穿 + 命中")
        _STORE.clear(); _CALLS["get"] = _CALLS["set"] = 0
        d1 = await order_dao.get_order_detail_cached(ORDER_ID)
        check("首次未命中返回非空 dict", d1 is not None and "id" in d1)
        check("首次回填写入缓存", order_key in _STORE and _STORE[order_key] != "__EMPTY__")
        check("首次含 commission_flows 列表", len(d1.get("commission_flows", [])) >= 1)
        check("首次产生 1 次 SET", _CALLS["set"] == 1, f"实际 {_CALLS['set']}")

        _CALLS["get"] = _CALLS["set"] = 0
        d2 = await order_dao.get_order_detail_cached(ORDER_ID)
        check("二次命中返回同 ID", d2 is not None and d2["id"] == d1["id"])
        check("二次命中无 SET", _CALLS["set"] == 0, f"实际 {_CALLS['set']}")
        check("二次命中有 1 次 GET", _CALLS["get"] == 1, f"实际 {_CALLS['get']}")

        print("\n【2】订单详情缓存 —— 更新后主动失效")
        _CALLS["delete"] = 0
        await order_dao.update_by_id(ORDER_ID, {"transfer_status": "PROCESSING"})
        check("update_by_id 触发 DEL", _CALLS["delete"] == 1, f"实际 {_CALLS['delete']}")
        check("失效后缓存 key 已删除", order_key not in _STORE)

        _CALLS["get"] = _CALLS["set"] = 0
        d3 = await order_dao.get_order_detail_cached(ORDER_ID)
        check("失效后再次未命中回填", order_key in _STORE and _CALLS["set"] == 1)

        print("\n【3】佣金汇总缓存 —— 读穿 + 命中")
        _STORE.clear(); _CALLS["get"] = _CALLS["set"] = 0
        from decimal import Decimal
        s1 = await flow_dao.sum_commission_by_order_id(ORDER_ID)
        check("首次未命中返回 16.00", s1 == Decimal("16.00"), f"实际 {s1}")
        check("首次回填金额字符串", _STORE.get(sum_key) == "16.00")
        check("首次产生 1 次 SET", _CALLS["set"] == 1, f"实际 {_CALLS['set']}")

        _CALLS["get"] = _CALLS["set"] = 0
        s2 = await flow_dao.sum_commission_by_order_id(ORDER_ID)
        check("二次命中返回 16.00", s2 == Decimal("16.00"))
        check("二次命中无 SET", _CALLS["set"] == 0, f"实际 {_CALLS['set']}")

        print("\n【4】佣金汇总缓存 —— 流水结算后主动失效（含订单详情一并失效）")
        # 取一条真实 flow_id
        flows = await flow_dao.list_by_order_id(ORDER_ID)
        fid = flows[0].id if flows else None
        check("存在可结算流水", fid is not None)
        if fid:
            _STORE[order_key] = json.dumps({"id": ORDER_ID})  # 预置 order 缓存
            _CALLS["delete"] = 0
            await flow_dao.update_by_id(fid, {"transfer_status": "SUCCESS", "transfer_batch_id": "BATCH_X"})
            check("update_by_id 触发 2 次 DEL(汇总+详情)", _CALLS["delete"] == 2, f"实际 {_CALLS['delete']}")
            check("commission_sum 已失效", sum_key not in _STORE)
            check("order 详情已一并失效", order_key not in _STORE)

            _CALLS["get"] = _CALLS["set"] = 0
            s3 = await flow_dao.sum_commission_by_order_id(ORDER_ID)
            check("失效后再次未命中回填", _CALLS["set"] == 1)

        print("\n【5】空缓存防穿透 —— 不存在的订单")
        _STORE.clear(); _CALLS["get"] = _CALLS["set"] = 0
        d0 = await order_dao.get_order_detail_cached(999999)
        check("不存在订单返回 None", d0 is None)
        check("写入 __EMPTY__ 空标记", _STORE.get(f"{CACHE_KEY_ORDER_DETAIL}999999") == "__EMPTY__")
        _CALLS["get"] = _CALLS["set"] = 0
        d0b = await order_dao.get_order_detail_cached(999999)
        check("二次命中空标记仍返回 None", d0b is None)
        check("二次命中空标记无 SET", _CALLS["set"] == 0)

    print(f"\n═══ 结果: {PASS} 通过 / {FAIL} 失败 ═══")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    rc_mod.logger.disabled = True  # 抑制 RedisClient 噪音
    sys.exit(asyncio.run(main()))
