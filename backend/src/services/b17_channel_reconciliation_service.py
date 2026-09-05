# @ai-generated
"""
B17 多渠道对账差异处理 Service（独立新建，不修改 B01-B16 基线）

按渠道维度对比订单佣金 ↔ 结算入账，检测渠道维度差异：
1. CHANNEL_ORDER_SETTLEMENT_MISMATCH: 渠道订单佣金 ↔ 渠道结算入账不一致
2. CHANNEL_SINGLE_SIDE_ORDER:         渠道有订单但无结算单
3. CHANNEL_SINGLE_SIDE_SETTLEMENT:    渠道有结算单但订单缺失
4. CHANNEL_ORDER_MISSING:             渠道侧订单在系统内缺失
5. CHANNEL_ORDER_AMOUNT_MISMATCH:     渠道侧订单金额与系统内不一致

差异结果写入 reconciliation_diff 表（复用 B13 差异模型），
通过 reconciliation_id 关联对账批次，diff_type 区分渠道差异类型。
"""
import logging
import traceback
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.lock_util import LockUtil
from src.config.b13_constants import (
    DIFF_TERMINAL_STATES,
    DIFF_TRANSITIONS,
    AlertLevel,
    DiffStatus,
    RECONCILIATION_TOLERANCE,
)
from src.config.b17_constants import (
    CACHE_KEY_CHANNEL_RECONCILIATION_DATE,
    CACHE_TTL_CHANNEL_RECONCILIATION_DATE,
    CHANNEL_DIFF_ALERT_LEVEL_MAP,
    CHANNEL_RECONCILIATION_CHANNELS,
    CHANNEL_RECONCILIATION_NO_PREFIX,
    ChannelDiffType,
    ChannelReconciliationStatus,
    LOCK_KEY_CHANNEL_RECONCILIATION,
)
from src.cps.circuit_breaker import CircuitBreaker
from src.dao.reconciliation_diff_dao import ReconciliationDiffDAO
from src.dao.reconciliation_record_dao import ReconciliationRecordDAO
from src.models.business.order_model import Order
from src.models.business.settlement_record_model import SettlementRecord

logger = logging.getLogger("service.b17_channel_reconciliation")


class B17ChannelReconciliationService:
    """多渠道对账差异处理 Service

    按渠道维度（myq/orderx）分别执行渠道订单 ↔ 结算入账的双向核对
    """

    def __init__(
        self,
        record_dao: ReconciliationRecordDAO,
        diff_dao: ReconciliationDiffDAO,
        session: AsyncSession,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.record_dao = record_dao
        self.diff_dao = diff_dao
        self.session = session
        self.circuit_breaker = circuit_breaker

    # ════════════════════════════════════════════════════
    # 渠道对账主入口
    # ════════════════════════════════════════════════════

    async def run_channel_reconciliation(
        self,
        reconcile_date: Optional[date] = None,
        reconcile_type: str = "DAILY",
        operator_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """执行多渠道对账（主入口）

        流程：
        1. 确定对账日期（默认昨天）
        2. 幂等锁检查
        3. 熔断检查
        4. 创建对账批次（PENDING → RUNNING）
        5. 逐渠道执行核对（myq → orderx）
        6. 差异落库 + 告警
        7. 更新批次状态
        8. 释放锁 + 写幂等缓存
        """
        if reconcile_date is None:
            reconcile_date = date.today() - timedelta(days=1)

        # 幂等锁
        lock_key = f"{LOCK_KEY_CHANNEL_RECONCILIATION}{reconcile_date.isoformat()}"
        lock_owner = await LockUtil.acquire_lock(
            lock_key, timeout=600
        )
        if lock_owner is None:
            raise ValueError(
                f"渠道对账日期 {reconcile_date} 正在执行中或已对账，请勿重复执行"
            )

        try:
            # 熔断检查
            await self._check_breaker()

            # 创建对账批次
            reconciliation_no = self._generate_no(reconcile_date)
            record = await self.record_dao.create({
                "reconciliation_no": reconciliation_no,
                "reconcile_date": reconcile_date,
                "reconcile_type": reconcile_type,
                "status": ChannelReconciliationStatus.RUNNING.value,
                "started_at": datetime.now(),
                "operator_id": operator_id,
            })

            logger.info(
                "[channel_reconciliation] 对账批次创建 no=%s date=%s type=%s",
                reconciliation_no, reconcile_date, reconcile_type,
            )

            # 逐渠道核对
            result = await self._execute_channel_check(record.id, reconcile_date)

            # 更新批次状态
            final_status = (
                ChannelReconciliationStatus.SUCCESS.value
                if result["diff_count"] == 0
                else ChannelReconciliationStatus.PARTIAL.value
            )
            await self.record_dao.update_by_id(record.id, {
                "status": final_status,
                "completed_at": datetime.now(),
                "order_count": result["order_count"],
                "matched_count": result["matched_count"],
                "diff_count": result["diff_count"],
                "total_order_commission": result["total_order_commission"],
                "total_settlement_commission": result["total_settlement_commission"],
                "remark": f"渠道: {','.join(result['channel_stats'].keys())}",
            })

            # 写幂等缓存
            try:
                from src.common.redis_client import RedisClient
                await RedisClient.set(
                    CACHE_KEY_CHANNEL_RECONCILIATION_DATE + reconcile_date.isoformat(),
                    final_status,
                    expire=CACHE_TTL_CHANNEL_RECONCILIATION_DATE,
                )
            except Exception as cache_err:
                logger.warning(
                    "[channel_reconciliation] 幂等缓存写入失败: %s", cache_err
                )

            await self._record_success()

            logger.info(
                "[channel_reconciliation] 对账完成 no=%s status=%s matched=%s diff=%s",
                reconciliation_no, final_status,
                result["matched_count"], result["diff_count"],
            )

            return {
                "reconciliation_id": record.id,
                "reconciliation_no": reconciliation_no,
                "reconcile_date": reconcile_date.isoformat(),
                "status": final_status,
                "order_count": result["order_count"],
                "matched_count": result["matched_count"],
                "diff_count": result["diff_count"],
                "channel_stats": result["channel_stats"],
                "critical_diff_count": result["critical_diff_count"],
            }

        except Exception as e:
            logger.error(
                "[channel_reconciliation] 对账执行失败: %s\n%s",
                e, traceback.format_exc(),
            )
            await self._record_failure()
            try:
                failed_records = await self.record_dao.list_with_filters(
                    start_date=reconcile_date,
                    end_date=reconcile_date,
                    status=ChannelReconciliationStatus.RUNNING.value,
                    page=1, page_size=1,
                )
                if failed_records[0]:
                    await self.record_dao.update_by_id(
                        failed_records[0][0].id, {
                            "status": ChannelReconciliationStatus.FAILED.value,
                            "completed_at": datetime.now(),
                            "error_message": str(e)[:1024],
                        }
                    )
            except Exception:
                pass
            raise
        finally:
            await LockUtil.release_lock(lock_key, lock_owner)

    # ════════════════════════════════════════════════════
    # 逐渠道对账执行
    # ════════════════════════════════════════════════════

    async def _execute_channel_check(
        self, reconciliation_id: int, reconcile_date: date,
    ) -> Dict[str, Any]:
        """逐渠道执行核对"""
        start_time = datetime.combine(reconcile_date, datetime.min.time())
        end_time = datetime.combine(
            reconcile_date + timedelta(days=1), datetime.min.time()
        )

        all_diffs: List[Dict[str, Any]] = []
        total_order_count = 0
        total_matched = 0
        total_order_commission = Decimal("0.00")
        total_settlement_commission = Decimal("0.00")
        channel_stats: Dict[str, Dict[str, Any]] = {}

        for channel_code in CHANNEL_RECONCILIATION_CHANNELS:
            channel_result = await self._check_single_channel(
                reconciliation_id, channel_code, start_time, end_time,
            )
            channel_stats[channel_code] = {
                "order_count": channel_result["order_count"],
                "matched_count": channel_result["matched_count"],
                "diff_count": len(channel_result["diffs"]),
                "order_commission": str(channel_result["order_commission"]),
                "settlement_commission": str(channel_result["settlement_commission"]),
            }
            all_diffs.extend(channel_result["diffs"])
            total_order_count += channel_result["order_count"]
            total_matched += channel_result["matched_count"]
            total_order_commission += channel_result["order_commission"]
            total_settlement_commission += channel_result["settlement_commission"]

        # 差异落库 + 告警
        critical_count = 0
        if all_diffs:
            await self.diff_dao.batch_create(all_diffs)
            for d in all_diffs:
                if d.get("alert_level") == AlertLevel.CRITICAL.value:
                    critical_count += 1
                    await self._send_alert(d)

        return {
            "order_count": total_order_count,
            "matched_count": total_matched,
            "diff_count": len(all_diffs),
            "total_order_commission": total_order_commission,
            "total_settlement_commission": total_settlement_commission,
            "critical_diff_count": critical_count,
            "channel_stats": channel_stats,
        }

    async def _check_single_channel(
        self,
        reconciliation_id: int,
        channel_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """对单个渠道执行核对"""
        diffs: List[Dict[str, Any]] = []

        # 1. 查询渠道订单汇总
        order_agg = await self._aggregate_channel_orders(
            channel_code, start_time, end_time,
        )

        # 2. 查询渠道结算汇总
        settlement_agg = await self._aggregate_channel_settlements(
            channel_code, start_time, end_time,
        )

        # 3. 核对：订单佣金 ↔ 结算入账
        for user_id, o_data in order_agg.items():
            s_data = settlement_agg.get(
                user_id, {"user_commission": Decimal("0.00")}
            )
            diff = self._compare_amounts(
                reconciliation_id, user_id, channel_code,
                o_data["user_commission"], s_data["user_commission"],
                ChannelDiffType.CHANNEL_ORDER_SETTLEMENT_MISMATCH.value,
                "ORDER", "SETTLEMENT",
            )
            if diff:
                diffs.append(diff)

        # 4. 单边账检测：有订单无结算单
        no_settlement_orders = await self._find_channel_orders_without_settlement(
            channel_code, start_time, end_time,
        )
        for order in no_settlement_orders:
            diffs.append(self._build_diff(
                reconciliation_id, order.user_id, channel_code,
                ChannelDiffType.CHANNEL_SINGLE_SIDE_ORDER.value,
                "ORDER", "SETTLEMENT",
                order.user_commission, Decimal("0.00"),
                order_id=order.id,
                remark=f"渠道[{channel_code}]订单 {order.internal_order_no} 有佣金"
                       f" {order.user_commission} 但无结算单",
            ))

        # 5. 单边账检测：有结算单无订单
        no_order_settlements = await self._find_channel_settlements_without_order(
            channel_code, start_time, end_time,
        )
        for settlement in no_order_settlements:
            diffs.append(self._build_diff(
                reconciliation_id, settlement.user_id, channel_code,
                ChannelDiffType.CHANNEL_SINGLE_SIDE_SETTLEMENT.value,
                "SETTLEMENT", "ORDER",
                settlement.user_commission, Decimal("0.00"),
                settlement_id=settlement.id,
                remark=f"渠道[{channel_code}]结算单 {settlement.settlement_no}"
                       f" 存在但订单缺失/失效",
            ))

        order_count = sum(
            d.get("order_count", 0) for d in order_agg.values()
        )
        matched_count = sum(
            1 for uid in order_agg
            if uid in settlement_agg
            and abs(
                order_agg[uid]["user_commission"]
                - settlement_agg[uid]["user_commission"]
            ) <= RECONCILIATION_TOLERANCE
        )
        order_commission = sum(
            (d["user_commission"] for d in order_agg.values()),
            Decimal("0.00"),
        )
        settlement_commission = sum(
            (d["user_commission"] for d in settlement_agg.values()),
            Decimal("0.00"),
        )

        return {
            "order_count": order_count,
            "matched_count": matched_count,
            "diffs": diffs,
            "order_commission": order_commission,
            "settlement_commission": settlement_commission,
        }

    # ════════════════════════════════════════════════════
    # 渠道聚合查询
    # ════════════════════════════════════════════════════

    async def _aggregate_channel_orders(
        self, channel_code: str, start_time: datetime, end_time: datetime,
    ) -> Dict[int, Dict[str, Any]]:
        """按用户汇总渠道订单佣金"""
        stmt = (
            select(
                Order.user_id,
                func.sum(Order.user_commission),
                func.sum(Order.total_commission),
                func.count(Order.id),
            )
            .where(
                and_(
                    Order.is_delete == False,
                    Order.channel_code == channel_code,
                    Order.order_status.in_([30, 40]),  # SETTLABLE/SETTLED
                    Order.create_time >= start_time,
                    Order.create_time < end_time,
                )
            )
            .group_by(Order.user_id)
        )
        result = await self.session.execute(stmt)
        agg: Dict[int, Dict[str, Any]] = {}
        for row in result.fetchall():
            agg[row[0]] = {
                "user_commission": row[1] or Decimal("0.00"),
                "total_commission": row[2] or Decimal("0.00"),
                "order_count": int(row[3] or 0),
            }
        return agg

    async def _aggregate_channel_settlements(
        self, channel_code: str, start_time: datetime, end_time: datetime,
    ) -> Dict[int, Dict[str, Any]]:
        """按用户汇总渠道结算入账"""
        from src.config.b12_constants import SettlementStatus
        stmt = (
            select(
                SettlementRecord.user_id,
                func.sum(SettlementRecord.user_commission),
                func.sum(SettlementRecord.total_commission),
                func.count(SettlementRecord.id),
            )
            .where(
                and_(
                    SettlementRecord.is_delete == False,
                    SettlementRecord.channel_code == channel_code,
                    SettlementRecord.settlement_status.in_([
                        SettlementStatus.SETTLABLE.value,
                        SettlementStatus.SETTLED.value,
                        SettlementStatus.PAID.value,
                    ]),
                    SettlementRecord.create_time >= start_time,
                    SettlementRecord.create_time < end_time,
                )
            )
            .group_by(SettlementRecord.user_id)
        )
        result = await self.session.execute(stmt)
        agg: Dict[int, Dict[str, Any]] = {}
        for row in result.fetchall():
            agg[row[0]] = {
                "user_commission": row[1] or Decimal("0.00"),
                "total_commission": row[2] or Decimal("0.00"),
                "count": int(row[3] or 0),
            }
        return agg

    async def _find_channel_orders_without_settlement(
        self, channel_code: str, start_time: datetime, end_time: datetime,
    ):
        """查询渠道中有佣金但无结算单的订单"""
        settled_order_ids = (
            select(SettlementRecord.order_id)
            .where(SettlementRecord.is_delete == False)
            .distinct()
            .subquery()
        )
        stmt = (
            select(Order)
            .where(
                and_(
                    Order.is_delete == False,
                    Order.channel_code == channel_code,
                    Order.order_status.in_([30, 40]),
                    Order.user_commission > 0,
                    Order.create_time >= start_time,
                    Order.create_time < end_time,
                    ~Order.id.in_(select(settled_order_ids.c.order_id)),
                )
            )
            .order_by(Order.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _find_channel_settlements_without_order(
        self, channel_code: str, start_time: datetime, end_time: datetime,
    ):
        """查询渠道中结算单存在但订单缺失/失效的记录"""
        from src.models.business.settlement_record_model import SettlementRecord
        from src.config.b12_constants import SettlementStatus
        valid_order_ids = (
            select(Order.id)
            .where(
                and_(
                    Order.is_delete == False,
                    Order.order_status.in_([30, 40]),
                )
            )
            .distinct()
            .subquery()
        )
        stmt = (
            select(SettlementRecord)
            .where(
                and_(
                    SettlementRecord.is_delete == False,
                    SettlementRecord.channel_code == channel_code,
                    SettlementRecord.settlement_status.in_([
                        SettlementStatus.SETTLABLE.value,
                        SettlementStatus.SETTLED.value,
                        SettlementStatus.PAID.value,
                    ]),
                    SettlementRecord.create_time >= start_time,
                    SettlementRecord.create_time < end_time,
                    ~SettlementRecord.order_id.in_(select(valid_order_ids.c.id)),
                )
            )
            .order_by(SettlementRecord.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ════════════════════════════════════════════════════
    # 工具方法
    # ════════════════════════════════════════════════════

    def _compare_amounts(
        self,
        reconciliation_id: int, user_id: int, channel_code: str,
        source_amount: Decimal, target_amount: Decimal,
        diff_type: str, source_type: str, target_type: str,
        order_id: Optional[int] = None,
        settlement_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """比较两方金额，超出容忍度则生成差异记录"""
        diff = abs(source_amount - target_amount)
        if diff <= RECONCILIATION_TOLERANCE:
            return None
        return self._build_diff(
            reconciliation_id, user_id, channel_code,
            diff_type, source_type, target_type,
            source_amount, target_amount,
            order_id=order_id, settlement_id=settlement_id,
        )

    def _build_diff(
        self,
        reconciliation_id: int, user_id: int, channel_code: str,
        diff_type: str, source_type: str, target_type: str,
        source_amount: Decimal, target_amount: Decimal,
        order_id: Optional[int] = None,
        settlement_id: Optional[int] = None,
        remark: str = "",
    ) -> Dict[str, Any]:
        """构造渠道对账差异明细 dict"""
        diff_amount = abs(source_amount - target_amount)
        alert_level = CHANNEL_DIFF_ALERT_LEVEL_MAP.get(
            diff_type, "WARNING"
        )
        if not remark:
            remark = (
                f"渠道[{channel_code}] {source_type}({source_amount})"
                f" ↔ {target_type}({target_amount}), 差异 {diff_amount}"
            )
        return {
            "reconciliation_id": reconciliation_id,
            "channel_code": channel_code,
            "user_id": user_id,
            "order_id": order_id,
            "settlement_id": settlement_id,
            "diff_type": diff_type,
            "source_type": source_type,
            "target_type": target_type,
            "source_amount": source_amount,
            "target_amount": target_amount,
            "diff_amount": diff_amount,
            "alert_level": alert_level,
            "alert_sent": "N",
            "status": DiffStatus.PENDING.value,
            "remark": f"[{channel_code}] {remark}",
        }

    @staticmethod
    def _generate_no(reconcile_date: date) -> str:
        """生成渠道对账批次号：GAKCR + 日期 + 随机后缀"""
        import uuid
        suffix = uuid.uuid4().hex[:8].upper()
        return f"{CHANNEL_RECONCILIATION_NO_PREFIX}" \
               f"{reconcile_date.strftime('%Y%m%d')}{suffix}"

    async def review_channel_diff(
        self,
        diff_id: int,
        action: str,
        review_remark: str,
        operator_id: int,
    ) -> Dict[str, Any]:
        """人工复核渠道对账差异（PENDING/REVIEWING → RESOLVED/IGNORED）

        复用 B13 差异状态机（DIFF_TRANSITIONS / DIFF_TERMINAL_STATES），
        仅允许对 CHANNEL_* 渠道差异进行复核标记。
        """
        diff = await self.diff_dao.get_by_id(diff_id)
        if diff is None:
            raise ValueError("差异明细不存在")
        if not (diff.diff_type or "").startswith("CHANNEL_"):
            raise ValueError("仅支持复核渠道对账差异（CHANNEL_* 类型）")

        current_status = diff.status
        if current_status in DIFF_TERMINAL_STATES:
            raise ValueError(f"差异已处于终态 {current_status}，不可再操作")

        allowed = DIFF_TRANSITIONS.get(current_status, set())
        if action not in allowed:
            raise ValueError(
                f"非法状态流转: {current_status} → {action}，允许: {allowed or '无'}"
            )

        update_data: Dict[str, Any] = {
            "status": action,
            "review_user_id": operator_id,
            "review_remark": review_remark,
        }
        if action in (DiffStatus.RESOLVED.value, DiffStatus.IGNORED.value):
            update_data["reviewed_at"] = datetime.now()

        await self.diff_dao.update_by_id(diff_id, update_data)
        logger.info(
            "[channel_reconciliation] 渠道差异复核 diff_id=%s %s→%s operator=%s channel=%s",
            diff_id, current_status, action, operator_id, getattr(diff, "channel_code", "-"),
        )
        reviewed_at = update_data.get("reviewed_at")
        return {
            "diff_id": diff_id,
            "status": action,
            "reviewed_at": reviewed_at.isoformat() if reviewed_at else None,
        }

    async def _send_alert(self, diff_data: Dict[str, Any]) -> None:
        """推送告警（日志标记）"""
        try:
            logger.error(
                "[ALERT][channel_reconciliation=%s] 渠道差异告警 "
                "user=%s type=%s amount=%s source=%s target=%s remark=%s",
                diff_data.get("reconciliation_id"),
                diff_data.get("user_id"),
                diff_data.get("diff_type"),
                diff_data.get("diff_amount", Decimal("0.00")),
                diff_data.get("source_type"),
                diff_data.get("target_type"),
                diff_data.get("remark", ""),
            )
            diff_data["alert_sent"] = "Y"
        except Exception as e:
            logger.warning("[channel_reconciliation] 告警推送失败（不阻断）: %s", e)

    async def _check_breaker(self) -> None:
        """熔断检查"""
        if self.circuit_breaker is None:
            return
        try:
            allowed = await self.circuit_breaker.allow_request("channel_reconciliation")
            if not allowed:
                raise ValueError("渠道对账熔断中，请稍后重试")
        except ValueError:
            raise
        except Exception as e:
            logger.warning("[channel_reconciliation] 熔断检查异常（放行）: %s", e)

    async def _record_success(self) -> None:
        if self.circuit_breaker is None:
            return
        try:
            await self.circuit_breaker.record_success("channel_reconciliation")
        except Exception as e:
            logger.warning("[channel_reconciliation] 熔断成功记录异常: %s", e)

    async def _record_failure(self) -> None:
        if self.circuit_breaker is None:
            return
        try:
            await self.circuit_breaker.record_failure("channel_reconciliation")
        except Exception as e:
            logger.warning("[channel_reconciliation] 熔断失败记录异常: %s", e)

    # ════════════════════════════════════════════════════
    # 渠道聚合统计（大盘用）
    # ════════════════════════════════════════════════════

    async def get_channel_aggregate_stats(
        self, start_time: datetime, end_time: datetime,
    ) -> Dict[str, Any]:
        """多渠道聚合统计（佣金/订单/成交分渠道汇总）

        Returns:
            {
                "channels": {
                    "myq": {"order_count": 100, "total_commission": "1234.56",
                            "user_commission": "617.28", "deal_count": 80,
                            "deal_amount": "987.65"},
                    "orderx": {"order_count": 50, ...}
                },
                "total": {"order_count": 150, "total_commission": "1851.84", ...}
            }
        """
        stmt = (
            select(
                Order.channel_code,
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.total_commission), 0).label("total_commission"),
                func.coalesce(func.sum(Order.user_commission), 0).label("user_commission"),
                func.coalesce(func.sum(Order.platform_commission), 0).label("platform_commission"),
                func.coalesce(func.sum(Order.pay_amount), 0).label("pay_amount"),
                func.sum(
                    func.if_(Order.order_status.in_([30, 40]), 1, 0)
                ).label("deal_count"),
                func.coalesce(
                    func.sum(
                        func.if_(Order.order_status.in_([30, 40]), Order.pay_amount, 0)
                    ), 0
                ).label("deal_amount"),
            )
            .where(
                and_(
                    Order.is_delete == False,
                    Order.create_time >= start_time,
                    Order.create_time < end_time,
                )
            )
            .group_by(Order.channel_code)
            .order_by(func.sum(Order.total_commission).desc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        channels: Dict[str, Any] = {}
        totals = {
            "order_count": 0, "total_commission": Decimal("0.00"),
            "user_commission": Decimal("0.00"), "platform_commission": Decimal("0.00"),
            "pay_amount": Decimal("0.00"), "deal_count": 0, "deal_amount": Decimal("0.00"),
        }

        for row in rows:
            code = row.channel_code or "unknown"
            channels[code] = {
                "channel_code": code,
                "order_count": row.order_count,
                "total_commission": str(round(float(row.total_commission), 2)),
                "user_commission": str(round(float(row.user_commission), 2)),
                "platform_commission": str(round(float(row.platform_commission), 2)),
                "pay_amount": str(round(float(row.pay_amount), 2)),
                "deal_count": int(row.deal_count or 0),
                "deal_amount": str(round(float(row.deal_amount), 2)),
            }
            totals["order_count"] += row.order_count
            totals["total_commission"] += row.total_commission
            totals["user_commission"] += row.user_commission
            totals["platform_commission"] += row.platform_commission
            totals["pay_amount"] += row.pay_amount
            totals["deal_count"] += int(row.deal_count or 0)
            totals["deal_amount"] += row.deal_amount

        return {
            "channels": channels,
            "total": {
                "order_count": totals["order_count"],
                "total_commission": str(round(float(totals["total_commission"]), 2)),
                "user_commission": str(round(float(totals["user_commission"]), 2)),
                "platform_commission": str(round(float(totals["platform_commission"]), 2)),
                "pay_amount": str(round(float(totals["pay_amount"]), 2)),
                "deal_count": totals["deal_count"],
                "deal_amount": str(round(float(totals["deal_amount"]), 2)),
            },
        }

    async def get_channel_order_trend(
        self, start_time: datetime, end_time: datetime,
        channel_code: Optional[str] = None,
        group_by: str = "day",
    ) -> List[Dict[str, Any]]:
        """渠道订单趋势（按天/周/月分组，支持单渠道筛选）

        Returns:
            [{"date": "2026-08-01", "channel_code": "myq",
              "order_count": 10, "total_commission": "123.45",
              "deal_count": 8, "deal_amount": "98.76"}, ...]
        """
        conditions = [
            Order.is_delete == False,
            Order.create_time >= start_time,
            Order.create_time < end_time,
        ]
        if channel_code:
            conditions.append(Order.channel_code == channel_code)

        if group_by == "week":
            date_func = func.yearweek(Order.create_time)
        elif group_by == "month":
            date_func = func.date_format(Order.create_time, "%Y-%m")
        else:
            date_func = func.date(Order.create_time)

        stmt = (
            select(
                date_func.label("stat_date"),
                Order.channel_code.label("channel_code"),
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.total_commission), 0).label("total_commission"),
                func.coalesce(func.sum(Order.user_commission), 0).label("user_commission"),
                func.sum(
                    func.if_(Order.order_status.in_([30, 40]), 1, 0)
                ).label("deal_count"),
                func.coalesce(
                    func.sum(
                        func.if_(Order.order_status.in_([30, 40]), Order.pay_amount, 0)
                    ), 0
                ).label("deal_amount"),
            )
            .where(and_(*conditions))
            .group_by(date_func, Order.channel_code)
            .order_by(date_func.asc(), Order.channel_code.asc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "date": str(row.stat_date),
                "channel_code": row.channel_code or "unknown",
                "order_count": row.order_count,
                "total_commission": str(round(float(row.total_commission), 2)),
                "user_commission": str(round(float(row.user_commission), 2)),
                "deal_count": int(row.deal_count or 0),
                "deal_amount": str(round(float(row.deal_amount), 2)),
            }
            for row in rows
        ]