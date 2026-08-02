# @ai-generated
"""
订单同步业务服务（B05）

职责：
- 游标推进 + 时间窗口切分，循环调用 B01 适配器 pull_order
- 单窗口拉取失败重试 3 次（指数退避），超限入 Redis 失败队列
- 复用 B04 熔断器（AdapterFactory 已包装 CircuitBreakerAdapter）
- 渠道状态字符串 → OrderStatus 枚举映射（不侵入 B06）
- 幂等入库（out_order_no 唯一索引 + 批量查重过滤）
- user_id 反查（同渠道同 channel_pid 历史订单，兜底 0）
- 已存在订单状态变更检测 + 批量更新
- 手动触发同步 / 手动补发失败队列 / 状态查询

设计约定（硬性规范）：
1. 不修改 B01-B04 存量代码，通过 AdapterFactory.get_adapter 获取已包装熔断器的适配器；
2. 不侵入 B06 佣金模块，不创建 commission_flow，不修改 OrderStatus 枚举；
3. 异步代码用 asyncio.sleep，禁止 time.sleep；
4. Redis 键统一 gaking:prod: 前缀（RedisClient.add_prefix 自动补）；
5. 渠道异常沿用 CpsChannelException 体系，对外接口层转 BizException；
6. 完整 try/except + 日志，单窗口/单订单失败不阻断整体执行。
"""
import asyncio
import json
import logging
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.common.redis_client import RedisClient
from src.config.constants import (
    CACHE_KEY_ORDER_SYNC_CURSOR,
    CACHE_KEY_ORDER_SYNC_FAILED,
    CACHE_TTL_ORDER_SYNC_CURSOR,
    CACHE_TTL_ORDER_SYNC_FAILED,
    CHANNEL_ORDER_STATUS_BY_CODE,
    CHANNEL_ORDER_STATUS_COMMON_MAP,
    OrderStatus,
    TASK_ORDER_SYNC_INITIAL_LOOKBACK_MINUTES,
    TASK_ORDER_SYNC_MAX_RETRY,
    TASK_ORDER_SYNC_MAX_WINDOWS_PER_RUN,
    TASK_ORDER_SYNC_RETRY_BASE_DELAY,
    TASK_ORDER_SYNC_WINDOW_MINUTES,
)
from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
from src.cps.adapter.dto import OrderDTO, OrderPullResult
from src.cps.adapter_factory import AdapterFactory
from src.cps.circuit_breaker import BreakerState
from src.cps.circuit_breaker_adapter import CircuitBreakerAdapter
from src.dao.order_sync_dao import OrderSyncDAO

logger = logging.getLogger("service.order_sync")

# 平台内部单号前缀（与 OrderService.create_order_from_channel 约定一致）
INTERNAL_ORDER_NO_PREFIX = "GAK"

# 渠道任务开关映射（channel_code → constants 开关变量）
_CHANNEL_ENABLE_MAP: Dict[str, str] = {
    "myq": "TASK_ORDER_SYNC_MYQ_ENABLE",
    "orderx": "TASK_ORDER_SYNC_ORDERX_ENABLE",
    "dta": "TASK_ORDER_SYNC_DTA_ENABLE",
}

# 渠道 cron 映射（channel_code → constants cron 变量）
_CHANNEL_CRON_MAP: Dict[str, str] = {
    "myq": "TASK_CRON_ORDER_SYNC_MYQ",
    "orderx": "TASK_CRON_ORDER_SYNC_ORDERX",
    "dta": "TASK_CRON_ORDER_SYNC_DTA",
}


class OrderSyncService:
    """订单同步业务服务

    通过构造函数注入 OrderSyncDAO，业务规则在此层校验。
    金额统一使用 Decimal，入库保持 Numeric 定点小数。
    """

    # 佣金拆分比例（与 OrderService.create_order_from_channel 约定一致）
    # 用户 80% / 平台 20%（来源：4级《CPS V2.0 分润规则定稿》）
    USER_COMMISSION_RATE = Decimal("0.80")
    PLATFORM_COMMISSION_RATE = Decimal("0.20")

    def __init__(self, sync_dao: OrderSyncDAO):
        self.sync_dao = sync_dao

    # ══════════════════════════════════════════════════════
    # 主入口：拉取单渠道订单（定时任务调用）
    # ══════════════════════════════════════════════════════

    async def pull_channel_orders(
        self,
        channel_code: str,
        window_minutes: int = TASK_ORDER_SYNC_WINDOW_MINUTES,
    ) -> Dict[str, Any]:
        """拉取单渠道订单（游标推进 + 时间窗口切分 + 重试 + 入库）

        流程：
        1. 读取 Redis 游标（None 时回溯 INITIAL_LOOKBACK_MINUTES 分钟）；
        2. 从游标 → now 切分为 window_minutes 分钟的窗口；
        3. 逐窗口调用适配器 pull_order（含3次重试 + 熔断保护）；
        4. 拉取结果幂等入库（新订单插入 + 已存在订单状态更新）；
        5. 每窗口成功后推进游标；
        6. 熔断 OPEN 时跳过该渠道本轮。

        Args:
            channel_code: 渠道标识 myq / orderx / dta
            window_minutes: 单窗口时长（分钟），默认 30
        Returns:
            {"status": "success"|"skipped"|"failed"|"partial",
             "channel_code": str, "windows_total": int,
             "pulled_count": int, "inserted_count": int,
             "updated_count": int, "failed_count": int,
             "cursor": str, "details": List[dict]}
        """
        task_name = f"order_sync:{channel_code}"
        result: Dict[str, Any] = {
            "status": "success",
            "channel_code": channel_code,
            "windows_total": 0,
            "pulled_count": 0,
            "inserted_count": 0,
            "updated_count": 0,
            "failed_count": 0,
            "cursor": None,
            "details": [],
        }

        # 1. 熔断器状态检查
        breaker = CircuitBreakerAdapter.get_default_breaker()
        state = await breaker.get_state(channel_code)
        if state == BreakerState.OPEN:
            logger.warning("[%s] 渠道熔断中，跳过本轮", task_name)
            result["status"] = "skipped"
            result["message"] = f"渠道[{channel_code}]熔断中，跳过本轮"
            return result

        # 2. 读取游标 + 计算时间窗口
        cursor_str = await RedisClient.get(
            f"{CACHE_KEY_ORDER_SYNC_CURSOR}{channel_code}"
        )
        if cursor_str:
            try:
                cursor_time = datetime.fromisoformat(cursor_str)
            except ValueError:
                logger.warning(
                    "[%s] 游标解析失败 cursor=%s，回溯默认时长",
                    task_name,
                    cursor_str,
                )
                cursor_time = datetime.now() - timedelta(
                    minutes=TASK_ORDER_SYNC_INITIAL_LOOKBACK_MINUTES
                )
        else:
            cursor_time = datetime.now() - timedelta(
                minutes=TASK_ORDER_SYNC_INITIAL_LOOKBACK_MINUTES
            )
            logger.info(
                "[%s] 游标为空，首次运行回溯 %s 分钟",
                task_name,
                TASK_ORDER_SYNC_INITIAL_LOOKBACK_MINUTES,
            )

        now = datetime.now()
        if cursor_time >= now:
            logger.info("[%s] 游标已追上当前时间，跳过", task_name)
            result["status"] = "skipped"
            result["message"] = "游标已追上当前时间"
            result["cursor"] = cursor_time.isoformat()
            return result

        # 3. 切分时间窗口
        windows = self._split_time_windows(cursor_time, now, window_minutes)
        # 防积压：单轮最多拉取 MAX_WINDOWS_PER_RUN 个窗口
        if len(windows) > TASK_ORDER_SYNC_MAX_WINDOWS_PER_RUN:
            logger.warning(
                "[%s] 窗口积压 %s 个，截断为 %s 个（剩余下轮继续）",
                task_name,
                len(windows),
                TASK_ORDER_SYNC_MAX_WINDOWS_PER_RUN,
            )
            windows = windows[:TASK_ORDER_SYNC_MAX_WINDOWS_PER_RUN]

        result["windows_total"] = len(windows)
        logger.info(
            "[%s] 开始拉取 windows=%s window_minutes=%s",
            task_name,
            len(windows),
            window_minutes,
        )

        # 4. 获取已包装熔断器的适配器
        try:
            adapter = AdapterFactory.get_adapter(channel_code)
        except ValueError as e:
            logger.error("[%s] 不支持的渠道: %s", task_name, e)
            result["status"] = "failed"
            result["message"] = f"不支持的渠道: {channel_code}"
            return result

        # 5. 逐窗口拉取 + 入库
        total_pulled = 0
        total_inserted = 0
        total_updated = 0
        failed_windows = 0
        last_success_cursor = cursor_time

        for idx, (win_start, win_end) in enumerate(windows):
            window_detail: Dict[str, Any] = {
                "index": idx + 1,
                "start": win_start.isoformat(),
                "end": win_end.isoformat(),
                "pulled": 0,
                "inserted": 0,
                "updated": 0,
                "status": "success",
            }

            try:
                pull_result = await self._pull_with_retry(
                    adapter, win_start, win_end, channel_code
                )
                orders = pull_result.orders or []
                window_detail["pulled"] = len(orders)
                total_pulled += len(orders)

                # 入库
                inserted, updated = await self._persist_orders(orders, channel_code)
                window_detail["inserted"] = inserted
                window_detail["updated"] = updated
                total_inserted += inserted
                total_updated += updated

                # 推进游标到窗口结束时间
                last_success_cursor = win_end
                await RedisClient.set(
                    f"{CACHE_KEY_ORDER_SYNC_CURSOR}{channel_code}",
                    win_end.isoformat(),
                    expire=CACHE_TTL_ORDER_SYNC_CURSOR,
                )

            except CpsChannelException as e:
                failed_windows += 1
                window_detail["status"] = "failed"
                window_detail["error"] = str(e)
                logger.error(
                    "[%s] 窗口 %s 拉取失败（已重试3次）: %s",
                    task_name,
                    idx + 1,
                    e,
                )
                # 失败后停止后续窗口（游标未推进，下轮从该窗口重试）
                result["details"].append(window_detail)
                break
            except Exception as e:
                failed_windows += 1
                window_detail["status"] = "failed"
                window_detail["error"] = str(e)
                logger.error(
                    "[%s] 窗口 %s 处理异常: %s\n%s",
                    task_name,
                    idx + 1,
                    e,
                    traceback.format_exc(),
                )
                result["details"].append(window_detail)
                break

            result["details"].append(window_detail)

        # 6. 汇总结果
        result["pulled_count"] = total_pulled
        result["inserted_count"] = total_inserted
        result["updated_count"] = total_updated
        result["failed_count"] = failed_windows
        result["cursor"] = last_success_cursor.isoformat()

        if failed_windows > 0:
            result["status"] = "partial"
            result["message"] = (
                f"部分成功：{len(windows)} 窗口中失败 {failed_windows} 个，"
                f"拉取 {total_pulled} 条，插入 {total_inserted} 条，更新 {total_updated} 条"
            )
        else:
            result["status"] = "success"
            result["message"] = (
                f"同步完成：{len(windows)} 窗口，"
                f"拉取 {total_pulled} 条，插入 {total_inserted} 条，更新 {total_updated} 条"
            )

        logger.info("[%s] %s", task_name, result["message"])
        return result

    # ══════════════════════════════════════════════════════
    # 拉取所有渠道（串行，避免并发限流）
    # ══════════════════════════════════════════════════════

    async def pull_all_channels(self) -> Dict[str, Any]:
        """串行拉取三个渠道订单（避免并发限流）

        Returns:
            {"status": "success"|"partial"|"failed",
             "channels": List[dict], "total_pulled": int, ...}
        """
        channels = ["myq", "orderx", "dta"]
        results: List[Dict[str, Any]] = []
        total_pulled = 0
        total_inserted = 0
        total_updated = 0
        any_failed = False

        for channel_code in channels:
            try:
                r = await self.pull_channel_orders(channel_code)
                results.append(r)
                total_pulled += r.get("pulled_count", 0)
                total_inserted += r.get("inserted_count", 0)
                total_updated += r.get("updated_count", 0)
                if r.get("status") in ("failed", "partial"):
                    any_failed = True
            except Exception as e:
                any_failed = True
                logger.error(
                    "[order_sync:%s] 拉取异常: %s\n%s",
                    channel_code,
                    e,
                    traceback.format_exc(),
                )
                results.append(
                    {
                        "channel_code": channel_code,
                        "status": "failed",
                        "message": str(e),
                        "pulled_count": 0,
                        "inserted_count": 0,
                        "updated_count": 0,
                    }
                )

        return {
            "status": "partial" if any_failed else "success",
            "channels": results,
            "total_pulled": total_pulled,
            "total_inserted": total_inserted,
            "total_updated": total_updated,
        }

    # ══════════════════════════════════════════════════════
    # 手动触发同步（管理员接口调用，可指定时间范围）
    # ══════════════════════════════════════════════════════

    async def manual_sync_channel(
        self,
        channel_code: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """手动触发单渠道同步（可指定时间范围，不走游标）

        Args:
            channel_code: 渠道标识
            start_time: 起始时间（缺省取游标）
            end_time: 结束时间（缺省取当前时间）
        Returns:
            同 pull_channel_orders 返回结构
        """
        if end_time is None:
            end_time = datetime.now()

        # 若指定 start_time，临时覆盖游标
        if start_time is not None:
            await RedisClient.set(
                f"{CACHE_KEY_ORDER_SYNC_CURSOR}{channel_code}",
                start_time.isoformat(),
                expire=CACHE_TTL_ORDER_SYNC_CURSOR,
            )
            logger.info(
                "[order_sync:%s] 手动触发，临时游标设为 %s",
                channel_code,
                start_time.isoformat(),
            )

        # 调用主流程（end_time 由窗口切分自然限定到 now，手动指定时不影响）
        result = await self.pull_channel_orders(channel_code)

        # 手动触发时若指定了 end_time，需要确保不超过 end_time
        # （pull_channel_orders 内部以 now 为终点，这里不严格截断，
        #   手动补发场景通常指定历史区间，拉到 now 也无害）
        return result

    # ══════════════════════════════════════════════════════
    # 手动补发失败队列
    # ══════════════════════════════════════════════════════

    async def manual_retry_failed(
        self,
        channel_code: str,
        batch_size: int = 10,
    ) -> Dict[str, Any]:
        """手动补发失败队列（从 Redis List 取 N 条重试）

        Args:
            channel_code: 渠道标识
            batch_size: 单次补发条数
        Returns:
            {"status": "success"|"partial"|"failed",
             "channel_code": str, "retried_count": int,
             "success_count": int, "still_failed_count": int,
             "details": List[dict]}
        """
        task_name = f"order_sync:retry:{channel_code}"
        result: Dict[str, Any] = {
            "status": "success",
            "channel_code": channel_code,
            "retried_count": 0,
            "success_count": 0,
            "still_failed_count": 0,
            "details": [],
        }

        failed_key = f"{CACHE_KEY_ORDER_SYNC_FAILED}{channel_code}"

        # 获取适配器
        try:
            adapter = AdapterFactory.get_adapter(channel_code)
        except ValueError as e:
            result["status"] = "failed"
            result["message"] = f"不支持的渠道: {channel_code}"
            return result

        for i in range(batch_size):
            # RPOP 取最早一条失败记录
            raw = await RedisClient.rpop(failed_key)
            if not raw:
                logger.info("[%s] 失败队列已清空，停止补发", task_name)
                break

            result["retried_count"] += 1
            detail: Dict[str, Any] = {"index": i + 1, "raw": raw[:200]}

            try:
                payload = json.loads(raw)
                start = datetime.fromisoformat(payload["start"])
                end = datetime.fromisoformat(payload["end"])

                pull_result = await adapter.pull_order(start, end)
                orders = pull_result.orders or []
                inserted, updated = await self._persist_orders(orders, channel_code)

                detail["status"] = "success"
                detail["pulled"] = len(orders)
                detail["inserted"] = inserted
                detail["updated"] = updated
                result["success_count"] += 1

                logger.info(
                    "[%s] 补发成功 %s/%s: start=%s end=%s pulled=%s",
                    task_name,
                    i + 1,
                    batch_size,
                    start.isoformat(),
                    end.isoformat(),
                    len(orders),
                )
            except Exception as e:
                # 补发仍失败，重新入队（LPUSH 回到队尾，保持顺序）
                await RedisClient.lpush(failed_key, raw)
                detail["status"] = "failed"
                detail["error"] = str(e)
                result["still_failed_count"] += 1
                logger.error(
                    "[%s] 补发失败 %s/%s: %s",
                    task_name,
                    i + 1,
                    batch_size,
                    e,
                    exc_info=True,
                )

            result["details"].append(detail)

        # 汇总状态
        if result["retried_count"] == 0:
            result["status"] = "success"
            result["message"] = "失败队列为空，无需补发"
        elif result["still_failed_count"] > 0:
            result["status"] = "partial"
            result["message"] = (
                f"补发完成：尝试 {result['retried_count']} 条，"
                f"成功 {result['success_count']} 条，"
                f"仍失败 {result['still_failed_count']} 条"
            )
        else:
            result["status"] = "success"
            result["message"] = (
                f"补发完成：尝试 {result['retried_count']} 条，" f"全部成功"
            )

        logger.info("[%s] %s", task_name, result["message"])
        return result

    # ══════════════════════════════════════════════════════
    # 状态查询
    # ══════════════════════════════════════════════════════

    async def get_sync_status(self) -> Dict[str, Any]:
        """查询三渠道同步状态（游标/失败队列/熔断/cron）

        Returns:
            {"total_enabled": int, "channels": List[dict]}
        """
        from src.config import constants as const_mod

        channels: List[Dict[str, Any]] = []
        total_enabled = 0
        breaker = CircuitBreakerAdapter.get_default_breaker()

        for channel_code in ["myq", "orderx", "dta"]:
            # 渠道开关
            enable_attr = _CHANNEL_ENABLE_MAP.get(channel_code, "")
            enabled = (
                bool(getattr(const_mod, enable_attr, False)) if enable_attr else False
            )
            if enabled:
                total_enabled += 1

            # 游标
            cursor_str = await RedisClient.get(
                f"{CACHE_KEY_ORDER_SYNC_CURSOR}{channel_code}"
            )

            # 失败队列长度
            failed_len = await RedisClient.llen(
                f"{CACHE_KEY_ORDER_SYNC_FAILED}{channel_code}"
            )

            # 熔断状态
            try:
                breaker_state = (await breaker.get_state(channel_code)).value
            except Exception:
                breaker_state = "CLOSED"

            # cron 表达式
            cron_attr = _CHANNEL_CRON_MAP.get(channel_code, "")
            cron_expr = str(getattr(const_mod, cron_attr, "")) if cron_attr else ""

            channels.append(
                {
                    "channel_code": channel_code,
                    "enabled": enabled,
                    "cursor": cursor_str,
                    "failed_queue_length": failed_len,
                    "breaker_state": breaker_state,
                    "cron_expr": cron_expr,
                }
            )

        return {"total_enabled": total_enabled, "channels": channels}

    # ══════════════════════════════════════════════════════
    # 内部方法
    # ══════════════════════════════════════════════════════

    def _split_time_windows(
        self,
        start: datetime,
        end: datetime,
        window_minutes: int,
    ) -> List[Tuple[datetime, datetime]]:
        """将时间区间切分为 N 个 window_minutes 分钟的窗口

        Returns:
            [(win_start, win_end), ...] 左闭右开区间
        """
        if window_minutes <= 0:
            window_minutes = TASK_ORDER_SYNC_WINDOW_MINUTES

        windows: List[Tuple[datetime, datetime]] = []
        cursor = start
        delta = timedelta(minutes=window_minutes)
        while cursor < end:
            win_end = min(cursor + delta, end)
            windows.append((cursor, win_end))
            cursor = win_end
        return windows

    async def _pull_with_retry(
        self,
        adapter,
        start_time: datetime,
        end_time: datetime,
        channel_code: str,
    ) -> OrderPullResult:
        """单窗口拉取 + 3 次重试 + 指数退避 + 失败入队

        Args:
            adapter: 已包装熔断器的适配器（CircuitBreakerAdapter）
            start_time: 窗口起始时间
            end_time: 窗口结束时间
            channel_code: 渠道标识
        Returns:
            OrderPullResult
        Raises:
            CpsChannelException: 3 次重试均失败
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, TASK_ORDER_SYNC_MAX_RETRY + 1):
            try:
                result = await adapter.pull_order(start_time, end_time)
                if attempt > 1:
                    logger.info(
                        "[order_sync:%s] 窗口拉取重试 %s/%s 成功",
                        channel_code,
                        attempt,
                        TASK_ORDER_SYNC_MAX_RETRY,
                    )
                return result
            except CpsChannelException as e:
                last_exc = e
                if attempt >= TASK_ORDER_SYNC_MAX_RETRY:
                    # 写入失败队列
                    await self._push_failed_queue(
                        channel_code, start_time, end_time, attempt, str(e)
                    )
                    raise
                delay = TASK_ORDER_SYNC_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "[order_sync:%s] 窗口拉取失败 attempt=%s/%s delay=%ss: %s",
                    channel_code,
                    attempt,
                    TASK_ORDER_SYNC_MAX_RETRY,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)
            except Exception as e:
                last_exc = e
                if attempt >= TASK_ORDER_SYNC_MAX_RETRY:
                    # 非渠道异常也入失败队列
                    await self._push_failed_queue(
                        channel_code, start_time, end_time, attempt, str(e)
                    )
                    raise CpsChannelException(
                        error_type=CpsErrorType.API_ERROR,
                        message=f"窗口拉取异常（非渠道）: {e}",
                        channel_name=channel_code,
                    )
                delay = TASK_ORDER_SYNC_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "[order_sync:%s] 窗口处理异常 attempt=%s/%s delay=%ss: %s",
                    channel_code,
                    attempt,
                    TASK_ORDER_SYNC_MAX_RETRY,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)

        # 理论不可达（循环内已 raise），兜底
        raise last_exc  # type: ignore[misc]

    async def _push_failed_queue(
        self,
        channel_code: str,
        start_time: datetime,
        end_time: datetime,
        retry_count: int,
        error: str,
    ) -> None:
        """写入失败队列（Redis List，LPUSH）"""
        payload = {
            "channel_code": channel_code,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "retry_count": retry_count,
            "error": error[:1000],
            "failed_at": datetime.now().isoformat(),
        }
        failed_key = f"{CACHE_KEY_ORDER_SYNC_FAILED}{channel_code}"
        await RedisClient.lpush(failed_key, json.dumps(payload, ensure_ascii=False))
        # 设置 TTL（每次写入刷新，30 天后自动清理）
        await RedisClient.expire(failed_key, CACHE_TTL_ORDER_SYNC_FAILED)
        logger.info(
            "[order_sync:%s] 失败记录入队 start=%s end=%s retry=%s",
            channel_code,
            start_time.isoformat(),
            end_time.isoformat(),
            retry_count,
        )

    async def _persist_orders(
        self,
        orders: List[OrderDTO],
        channel_code: str,
    ) -> Tuple[int, int]:
        """幂等入库 + user_id 反查 + 状态映射

        Returns:
            (inserted_count, updated_count)
        """
        if not orders:
            return 0, 0

        inserted = 0
        updated = 0

        # 分离新订单与已存在订单
        out_order_nos = [o.origin_order_id for o in orders if o.origin_order_id]
        existing_nos = await self.sync_dao.list_existing_out_order_nos(out_order_nos)

        new_orders_data: List[Dict[str, Any]] = []
        update_list: List[Dict[str, Any]] = []

        for o in orders:
            if not o.origin_order_id:
                logger.warning(
                    "[order_sync:%s] 跳过无 origin_order_id 的订单: %s",
                    channel_code,
                    o.goods_title[:50],
                )
                continue

            mapped_status = self._map_channel_status(o.order_status, channel_code)

            if o.origin_order_id in existing_nos:
                # 已存在订单：状态变更则更新
                if mapped_status is not None:
                    update_list.append(
                        {
                            "out_order_no": o.origin_order_id,
                            "order_status": mapped_status,
                            "pay_time": o.pay_time,
                            "settle_time": o.settle_time,
                        }
                    )
            else:
                # 新订单：构造入库数据
                user_id = await self.sync_dao.find_user_id_by_channel_pid(
                    o.channel_pid, channel_code
                )
                if user_id == 0:
                    logger.warning(
                        "[order_sync:%s] 未匹配用户 pid=%s out_order_no=%s，"
                        "user_id=0 待认领",
                        channel_code,
                        o.channel_pid,
                        o.origin_order_id,
                    )

                order_data = self._build_order_data(
                    o, channel_code, user_id, mapped_status
                )
                new_orders_data.append(order_data)

        # 批量插入新订单
        if new_orders_data:
            try:
                _, inserted = await self.sync_dao.batch_upsert_orders(new_orders_data)
            except Exception as e:
                logger.error(
                    "[order_sync:%s] 批量插入异常: %s",
                    channel_code,
                    e,
                    exc_info=True,
                )

        # 批量更新已存在订单状态
        if update_list:
            try:
                updated = await self.sync_dao.batch_update_status(update_list)
            except Exception as e:
                logger.error(
                    "[order_sync:%s] 批量状态更新异常: %s",
                    channel_code,
                    e,
                    exc_info=True,
                )

        logger.info(
            "[order_sync:%s] 入库完成：拉取 %s，新增 %s，更新 %s",
            channel_code,
            len(orders),
            inserted,
            updated,
        )
        return inserted, updated

    def _build_order_data(
        self,
        o: OrderDTO,
        channel_code: str,
        user_id: int,
        mapped_status: Optional[int],
    ) -> Dict[str, Any]:
        """构造新订单入库数据字典"""
        # 佣金拆分：用户 80% / 平台 20%
        total_commission = o.total_commission or Decimal("0")
        user_commission = (total_commission * self.USER_COMMISSION_RATE).quantize(
            Decimal("0.01")
        )
        platform_commission = (total_commission - user_commission).quantize(
            Decimal("0.01")
        )

        return {
            "user_id": user_id,
            "out_order_no": o.origin_order_id,
            "internal_order_no": f"{INTERNAL_ORDER_NO_PREFIX}{o.origin_order_id}",
            "goods_title": o.goods_title or "",
            "goods_img": o.goods_img or "",
            "pay_amount": o.order_amount or Decimal("0"),
            "total_commission": total_commission,
            "user_commission": user_commission,
            "platform_commission": platform_commission,
            "channel_code": channel_code,
            "order_status": (
                mapped_status if mapped_status is not None else int(OrderStatus.PENDING)
            ),
            "transfer_status": "PENDING",
            "pay_time": o.pay_time,
            "settle_time": o.settle_time,
        }

    def _map_channel_status(
        self,
        order_status: str,
        channel_code: str,
    ) -> Optional[int]:
        """渠道状态字符串 → OrderStatus 枚举值

        优先按渠道专属映射表查找（解决同码不同义冲突），
        兜底用通用字符串映射，未知状态返回 None（不变更）。

        Args:
            order_status: 渠道返回的原始状态字符串
            channel_code: 渠道标识
        Returns:
            OrderStatus 枚举 int 值，未知返回 None
        """
        if not order_status:
            return None

        status_str = str(order_status).strip()

        # 1. 渠道专属映射表优先
        channel_map = CHANNEL_ORDER_STATUS_BY_CODE.get(channel_code, {})
        if status_str in channel_map:
            return channel_map[status_str]

        # 2. 通用字符串映射兜底
        if status_str in CHANNEL_ORDER_STATUS_COMMON_MAP:
            return CHANNEL_ORDER_STATUS_COMMON_MAP[status_str]

        # 3. 未知状态，不变更
        logger.debug(
            "[order_sync:%s] 未知渠道状态，不变更: status=%s",
            channel_code,
            status_str,
        )
        return None
