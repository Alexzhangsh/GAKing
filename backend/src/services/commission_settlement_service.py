# @ai-generated
"""
B07 佣金结算业务服务层
职责：编排规则引擎 + 结算专属 DAO + 现有 DAO，实现批量结算/退款扣减/重算/查询
不包含数据存取逻辑（下沉 DAO），不包含 HTTP 处理（上浮 API 层）
金额统一 Decimal 精确计算
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config.b07_constants import (
    TASK_BATCH_SETTLE_BATCH_SIZE,
    TASK_REFUND_DEDUCT_BATCH_SIZE,
    UserType,
)
from src.config.constants import OrderStatus
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.commission_settlement_dao import (
    FLOW_TYPE_DEDUCT,
    FLOW_TYPE_ORDER,
    TRANSFER_STATUS_PENDING,
    TRANSFER_STATUS_SUCCESS,
    CommissionSettlementDAO,
)
from src.dao.order_dao import OrderDAO
from src.services.commission_rule_engine import (
    CommissionRuleEngine,
    CommissionSplit,
    get_member_commission_rate,
    resolve_user_type_async,
)

logger = logging.getLogger("service.commission_settlement")


class CommissionSettlementService:
    """佣金结算业务服务

    通过构造函数注入 OrderDAO / CommissionFlowDAO / CommissionSettlementDAO / CommissionRuleEngine
    所有 DAO 共享同一 session（由 API 层的 get_db 注入）
    """

    def __init__(
        self,
        order_dao: OrderDAO,
        flow_dao: CommissionFlowDAO,
        settlement_dao: CommissionSettlementDAO,
        rule_engine: CommissionRuleEngine,
    ):
        self.order_dao = order_dao
        self.flow_dao = flow_dao
        self.settlement_dao = settlement_dao
        self.rule_engine = rule_engine

    # ── 0. 分佣比例解析（会员档位优先） ──────────────────────────

    async def _resolve_split(self, order) -> CommissionSplit:
        """解析订单佣金拆分比例

        X02-1 会员档位佣金策略：
        1. 用户存在生效会员记录 → 直接使用会员套餐分佣比例（user_rate=档位比例）
        2. 否则按渠道配置 + 用户类型（NORMAL/VIP）解析
        """
        # X02-1：会员套餐分佣
        member_rate = await get_member_commission_rate(order.user_id)
        if member_rate is not None:
            user_rate = member_rate
            platform_rate = Decimal("1.0") - member_rate
            logger.info(
                "[settle] 会员档位分佣 order_id=%s user_id=%s user_rate=%s platform_rate=%s",
                order.id, order.user_id, user_rate, platform_rate,
            )
            return CommissionSplit(user_rate=user_rate, platform_rate=platform_rate)

        user_type = await resolve_user_type_async(order.user_id)
        return await self.rule_engine.get_rates(order.channel_code, user_type)

    # ── 1. 批量结算 ────────────────────────────────────────────

    async def batch_settle_orders(
        self,
        limit: int = TASK_BATCH_SETTLE_BATCH_SIZE,
    ) -> Dict[str, Any]:
        """批量结算 SETTLED 订单无 ORDER 流水的订单

        逐单 try/except，单条失败不阻断整体执行
        幂等：已有 ORDER 流水的订单自动跳过

        Args:
            limit: 单轮处理上限
        Returns:
            {status, total, success_count, failed_count, skipped_count, details}
        """
        orders, total = await self.settlement_dao.list_settled_orders_without_flow(
            page=1, page_size=limit
        )

        if not orders:
            logger.info("[batch_settle] 无待结算订单")
            return {
                "status": "success",
                "total": 0,
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "details": [],
            }

        success_count = 0
        failed_count = 0
        skipped_count = 0
        details: List[Dict[str, Any]] = []

        for order in orders:
            try:
                result = await self.settle_single_order(order.id)
                if result["status"] == "skipped":
                    skipped_count += 1
                else:
                    success_count += 1
                details.append(result)
            except Exception as e:
                failed_count += 1
                logger.error(
                    "[batch_settle] 单笔结算失败 order_id=%s error=%s",
                    order.id,
                    e,
                    exc_info=True,
                )
                details.append(
                    {
                        "order_id": order.id,
                        "status": "failed",
                        "message": str(e),
                    }
                )

        status = "success" if failed_count == 0 else "partial"
        logger.info(
            "[batch_settle] 完成 total=%s success=%s failed=%s skipped=%s",
            total,
            success_count,
            failed_count,
            skipped_count,
        )
        return {
            "status": status,
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "details": details,
        }

    async def settle_single_order(self, order_id: int) -> Dict[str, Any]:
        """单订单结算（幂等核心）

        流程：
        1. 查订单，校验 SETTLED 状态
        2. 查现有流水，幂等校验
        3. 规则引擎计算佣金
        4. 原子入账（FOR UPDATE + 插入流水 + 更新余额）

        Args:
            order_id: 订单 ID
        Returns:
            {status, order_id, flow_id, amount, transfer_batch_id}
        Raises:
            ValueError: 订单不存在/状态非 SETTLED/金额 <= 0
        """
        order = await self.order_dao.get_by_id(order_id)
        if order is None:
            raise ValueError(f"订单不存在: order_id={order_id}")

        if order.order_status != int(OrderStatus.SETTLED):
            raise ValueError(
                f"订单状态非 SETTLED: order_id={order_id}, status={order.order_status}"
            )

        # 幂等校验：查现有 ORDER 类型流水
        existing_flows = await self.flow_dao.list_by_order_id(order_id)
        order_flows = [f for f in existing_flows if f.flow_type == FLOW_TYPE_ORDER]

        if order_flows:
            # 已有 ORDER 流水
            flow = order_flows[0]
            if flow.transfer_status == TRANSFER_STATUS_SUCCESS:
                logger.info(
                    "[settle] 订单已结算，幂等跳过 order_id=%s flow_id=%s",
                    order_id,
                    flow.id,
                )
                return {
                    "status": "skipped",
                    "order_id": order_id,
                    "flow_id": flow.id,
                    "amount": float(flow.amount),
                    "transfer_batch_id": flow.transfer_batch_id,
                    "message": "订单已结算，幂等跳过",
                }

        # 规则引擎计算佣金（会员档位分佣优先）
        split = await self._resolve_split(order)
        result = self.rule_engine.calculate(Decimal(str(order.total_commission)), split)
        user_commission = result.user_commission

        # 校准订单佣金字段（规则变更时可能与 B05 落库值不一致）
        if Decimal(str(order.user_commission)) != user_commission:
            logger.info(
                "[settle] 佣金校准 order_id=%s old=%s new=%s",
                order_id,
                order.user_commission,
                user_commission,
            )
            await self.order_dao.update_by_id(
                order_id,
                {
                    "user_commission": user_commission,
                    "platform_commission": result.platform_commission,
                },
            )

        # 生成转账批次 ID
        transfer_batch_id = (
            f"B07_SETTLE_{datetime.now().strftime('%Y%m%d%H%M%S')}_{order_id}"
        )

        # 原子入账
        flow = await self.settlement_dao.settle_order_commission_atomic(
            order, user_commission, transfer_batch_id
        )

        logger.info(
            "[settle] 结算成功 order_id=%s flow_id=%s amount=%s",
            order_id,
            flow.id,
            user_commission,
        )
        return {
            "status": "success",
            "order_id": order_id,
            "flow_id": flow.id,
            "amount": float(user_commission),
            "transfer_batch_id": transfer_batch_id,
        }

    # ── 2. 退款扣减 ────────────────────────────────────────────

    async def process_refund_deductions(
        self,
        limit: int = TASK_REFUND_DEDUCT_BATCH_SIZE,
    ) -> Dict[str, Any]:
        """批量退款扣减

        Args:
            limit: 单轮处理上限
        Returns:
            {status, total, success_count, failed_count, skipped_count, details}
        """
        orders, total = await self.settlement_dao.list_refunded_orders_without_deduct(
            page=1, page_size=limit
        )

        if not orders:
            logger.info("[refund_deduct] 无待扣减订单")
            return {
                "status": "success",
                "total": 0,
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "details": [],
            }

        success_count = 0
        failed_count = 0
        skipped_count = 0
        details: List[Dict[str, Any]] = []

        for order in orders:
            try:
                result = await self.process_single_refund(order.id)
                if result["status"] == "skipped":
                    skipped_count += 1
                else:
                    success_count += 1
                details.append(result)
            except Exception as e:
                failed_count += 1
                logger.error(
                    "[refund_deduct] 单笔扣减失败 order_id=%s error=%s",
                    order.id,
                    e,
                    exc_info=True,
                )
                details.append(
                    {
                        "order_id": order.id,
                        "status": "failed",
                        "message": str(e),
                    }
                )

        status = "success" if failed_count == 0 else "partial"
        logger.info(
            "[refund_deduct] 完成 total=%s success=%s failed=%s skipped=%s",
            total,
            success_count,
            failed_count,
            skipped_count,
        )
        return {
            "status": status,
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "details": details,
        }

    async def process_single_refund(self, order_id: int) -> Dict[str, Any]:
        """单订单退款扣减（幂等）

        分支：
        - 无 ORDER 流水 → 跳过（佣金从未发放）
        - 已有 DEDUCT 流水 → 幂等跳过
        - ORDER 流水 PENDING → 标记 FAILED（在途扣减）
        - ORDER 流水 SUCCESS → 扣减余额 + DEDUCT 流水

        Args:
            order_id: 订单 ID
        Returns:
            {status, order_id, deduct_flow_id, deduct_amount}
        Raises:
            ValueError: 订单不存在/状态非 REFUNDED
        """
        order = await self.order_dao.get_by_id(order_id)
        if order is None:
            raise ValueError(f"订单不存在: order_id={order_id}")

        if order.order_status != int(OrderStatus.REFUNDED):
            raise ValueError(
                f"订单状态非 REFUNDED: order_id={order_id}, status={order.order_status}"
            )

        # 查全部流水
        flows = await self.flow_dao.list_by_order_id(order_id)
        order_flows = [f for f in flows if f.flow_type == FLOW_TYPE_ORDER]
        deduct_flows = [f for f in flows if f.flow_type == FLOW_TYPE_DEDUCT]

        # 无 ORDER 流水 → 佣金从未发放，无需扣减
        if not order_flows:
            return {
                "status": "skipped",
                "order_id": order_id,
                "reason": "no_order_flow",
                "message": "订单无佣金流水，无需扣减",
            }

        # 已有 DEDUCT 流水 → 幂等跳过
        if deduct_flows:
            return {
                "status": "skipped",
                "order_id": order_id,
                "reason": "already_deducted",
                "message": "已存在扣减流水，幂等跳过",
            }

        # 执行扣减
        original_flow = order_flows[0]
        deduct_flow = await self.settlement_dao.deduct_on_refund_atomic(
            order, original_flow
        )

        if deduct_flow is None:
            # PENDING 分支：标记 FAILED，无 DEDUCT 流水
            return {
                "status": "success",
                "order_id": order_id,
                "deduct_flow_id": None,
                "deduct_amount": float(original_flow.amount),
                "message": "在途流水标记 FAILED，未动余额",
            }

        # SUCCESS 分支：扣减余额 + DEDUCT 流水
        return {
            "status": "success",
            "order_id": order_id,
            "deduct_flow_id": deduct_flow.id,
            "deduct_amount": float(deduct_flow.amount),
            "message": "已到账佣金扣减成功",
        }

    # ── 3. 佣金重算 ────────────────────────────────────────────

    async def recalculate_order_commission(
        self,
        order_id: int,
    ) -> Dict[str, Any]:
        """重算订单佣金（锁定保护）

        已有 ORDER 类型流水 → 锁定拒绝
        无 ORDER 流水 → 按规则引擎重算并更新订单佣金字段

        Args:
            order_id: 订单 ID
        Returns:
            {order_id, old_user_commission, new_user_commission, ...}
        Raises:
            ValueError: 订单不存在/已锁定
        """
        order = await self.order_dao.get_by_id(order_id)
        if order is None:
            raise ValueError(f"订单不存在: order_id={order_id}")

        # 锁定校验：已有 ORDER 流水则不可重算
        flows = await self.flow_dao.list_by_order_id(order_id)
        if any(f.flow_type == FLOW_TYPE_ORDER for f in flows):
            raise ValueError(f"订单已生成佣金流水，锁定不可重算: order_id={order_id}")

        # 规则引擎重算（会员档位分佣优先）
        split = await self._resolve_split(order)
        result = self.rule_engine.calculate(Decimal(str(order.total_commission)), split)

        old_user = Decimal(str(order.user_commission))
        old_platform = Decimal(str(order.platform_commission))

        # 更新订单佣金字段
        await self.order_dao.update_by_id(
            order_id,
            {
                "user_commission": result.user_commission,
                "platform_commission": result.platform_commission,
            },
        )

        logger.info(
            "[recalculate] 重算完成 order_id=%s old_user=%s new_user=%s",
            order_id,
            old_user,
            result.user_commission,
        )
        return {
            "order_id": order_id,
            "old_user_commission": float(old_user),
            "new_user_commission": float(result.user_commission),
            "old_platform_commission": float(old_platform),
            "new_platform_commission": float(result.platform_commission),
            "user_rate": float(result.user_rate),
            "platform_rate": float(result.platform_rate),
        }

    # ── 4. 查询接口 ────────────────────────────────────────────

    async def list_settlement_flows(
        self,
        user_id: Optional[int] = None,
        order_id: Optional[int] = None,
        flow_type: Optional[str] = None,
        transfer_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """查询佣金流水（多条件筛选+分页）

        Returns:
            {list, total, page, page_size}
        """
        items, total = await self.settlement_dao.list_flows_with_filters(
            user_id=user_id,
            order_id=order_id,
            flow_type=flow_type,
            transfer_status=transfer_status,
            page=page,
            page_size=page_size,
        )
        return {
            "list": [f.to_dict() for f in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def list_settlement_orders(
        self,
        order_status: Optional[int] = None,
        channel_code: Optional[str] = None,
        has_flow: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """查询结算状态订单

        Returns:
            {list, total, page, page_size}
        """
        items, total = await self.settlement_dao.list_settlement_orders_with_filters(
            order_status=order_status,
            channel_code=channel_code,
            has_flow=has_flow,
            page=page,
            page_size=page_size,
        )
        return {
            "list": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
