# @ai-generated
"""
佣金分润业务服务层（C 端查询 + 历史兼容写入）

职责：佣金流水查询、序列化输出、历史兼容的流水生成/结算标记
DB 操作全部下沉至 CommissionFlowDAO / OrderDAO，禁止直接写 SQL

⚠️ 重大变更说明（B07 整改）：
- 佣金比例常量已统一下沉至 src/config/b07_constants.py（DEFAULT_USER_COMMISSION_RATE /
  DEFAULT_PLATFORM_COMMISSION_RATE），本文件不再重复定义。
- 佣金规则引擎（含渠道专属配置）由 B07 的 CommissionRuleEngine 统一承载。
- 新业务（批量结算/退款扣减/重算）必须使用 B07 的 CommissionSettlementService
  （路由 /api/v1/admin/commission-settlement）。
- 已删除与 B07 重复或无调用方的冗余方法：
  * update_settle_status（与 B07 settle_single_order 重复）
  * batch_bind_flows_to_order（无外部调用方）
  * serialize_flows（无外部调用方）
- 保留方法仅用于 cps_commission 路由（/api/v1/cps/commission）的历史兼容：
  * generate_commission_flows 生成 PENDING 流水（与 B07 直接生成 SUCCESS 流水语义不同）
  * batch_mark_settled 将 PENDING 流水标记为 SUCCESS
  * summarize_order_commission / serialize_flow_by_ids 纯查询（B07 暂无等价方法）
- 后续 C 端登录体系完善后将统一移除写入方法，查询方法迁移至 B07。
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List

from src.dao.order_dao import OrderDAO
from src.dao.commission_flow_dao import CommissionFlowDAO

logger = logging.getLogger("service.commission")

# 流水类型枚举（仅保留本文件实际使用的 ORDER；DEDUCT/SUPPLEMENT 由 B07 commission_settlement_dao 定义）
FLOW_TYPE_ORDER = "ORDER"  # 订单佣金

# 转账状态枚举（仅保留本文件实际使用的 PENDING/SUCCESS；
# PROCESSING/FAILED 由 B07 commission_settlement_dao 定义，本文件不再重复）
TRANSFER_STATUS_PENDING = "PENDING"
TRANSFER_STATUS_SUCCESS = "SUCCESS"


class CommissionService:
    """佣金分润业务服务

    通过构造函数注入 OrderDAO / CommissionFlowDAO
    金额统一使用 Decimal 精确计算，入库保持 Numeric 定点小数
    分/元转换在 Service 层处理
    """

    def __init__(self, order_dao: OrderDAO, flow_dao: CommissionFlowDAO):
        self.order_dao = order_dao
        self.flow_dao = flow_dao

    # ── 1. 根据订单拆分生成多条佣金流水记录 ────────────────

    async def generate_commission_flows(
        self,
        order_id: int,
    ) -> List[Dict[str, Any]]:
        """根据订单拆分生成佣金流水记录

        业务规则：
        1. 订单必须存在且状态为 SETTLABLE（可结算）
        2. 幂等：已存在该订单的 ORDER 类型流水则跳过
        3. 生成用户佣金流水（flow_type=ORDER，金额=user_commission）
        4. 平台佣金不入流水（平台抽成不发放给用户，仅记录在订单字段）

        Args:
            order_id: 订单 ID
        Returns:
            生成的流水字典列表
        Raises:
            ValueError: 订单不存在或状态不允许结算
        """
        order = await self.order_dao.get_by_id(order_id)
        if order is None:
            raise ValueError(f"订单不存在: order_id={order_id}")

        # 幂等校验：查询是否已有该订单的 ORDER 类型流水
        existing_flows = await self.flow_dao.list_by_order_id(order_id)
        has_order_flow = any(f.flow_type == FLOW_TYPE_ORDER for f in existing_flows)
        if has_order_flow:
            logger.info("订单佣金流水已存在，幂等跳过: order_id=%s", order_id)
            return [f.to_dict() for f in existing_flows]

        # 佣金金额（来自订单字段，已是 Decimal）
        user_commission = Decimal(str(order.user_commission))

        # 生成用户佣金流水
        flow_data = {
            "order_id": order_id,
            "user_id": order.user_id,
            "flow_type": FLOW_TYPE_ORDER,
            "amount": user_commission,
            "before_balance": Decimal("0.00"),
            "after_balance": user_commission,
            "transfer_batch_id": "",
            "transfer_status": TRANSFER_STATUS_PENDING,
            "remark": f"订单佣金结算: {order.internal_order_no}",
        }
        flows = await self.flow_dao.batch_create([flow_data])
        logger.info(
            "佣金流水生成成功: order_id=%s, user_commission=%s, flow_id=%s",
            order_id,
            user_commission,
            flows[0].id if flows else None,
        )
        return [f.to_dict() for f in flows]

    # ── 2. 单订单佣金总额统计 ──────────────────────────────

    async def summarize_order_commission(
        self,
        order_id: int,
    ) -> Dict[str, Any]:
        """单订单佣金总额统计

        使用 SQL SUM 聚合查询该订单全部流水的总金额

        Args:
            order_id: 订单 ID
        Returns:
            {"order_id": id, "total_amount": Decimal, "flow_count": N}
        """
        total_amount = await self.flow_dao.sum_commission_by_order_id(order_id)
        flows = await self.flow_dao.list_by_order_id(order_id)

        result = {
            "order_id": order_id,
            "total_amount": float(total_amount),
            "flow_count": len(flows),
        }
        logger.info(
            "订单佣金统计: order_id=%s, total=%s, count=%s",
            order_id,
            total_amount,
            len(flows),
        )
        return result

    # ── 3. 批量结算标记（历史兼容，新业务请用 B07） ────────
    # ⚠️ B07 整改：update_settle_status / batch_bind_flows_to_order 已删除
    #    （无外部调用方且与 B07 CommissionSettlementService 重复）。
    #    batch_mark_settled 保留是因为 cps_commission /settle 路由仍在调用，
    #    其语义是将 PENDING 流水标记为 SUCCESS，与 B07 直接生成 SUCCESS 流水不同。

    async def batch_mark_settled(
        self,
        flow_ids: List[int],
        transfer_batch_id: str,
    ) -> int:
        """批量结算标记（将多条流水标记为已结算 SUCCESS）

        ⚠️ @deprecated 历史兼容接口：新业务请使用 B07 的
        CommissionSettlementService.batch_settle_orders
        （路由 POST /api/v1/admin/commission-settlement/settle/batch）。

        Args:
            flow_ids: 佣金流水 ID 列表
            transfer_batch_id: 微信转账批次 ID
        Returns:
            实际更新的流水记录数
        Raises:
            ValueError: flow_ids 为空或 transfer_batch_id 为空
        """
        if not flow_ids:
            raise ValueError("flow_ids 不能为空")
        if not transfer_batch_id:
            raise ValueError("transfer_batch_id 不能为空")

        update_data = {
            "transfer_status": TRANSFER_STATUS_SUCCESS,
            "transfer_batch_id": transfer_batch_id,
        }
        updated_count = 0
        for fid in flow_ids:
            result = await self.flow_dao.update_by_id(fid, update_data)
            if result is not None:
                updated_count += 1

        logger.info(
            "批量结算标记: batch_id=%s, settled=%s/%s",
            transfer_batch_id,
            updated_count,
            len(flow_ids),
        )
        return updated_count

    # ── 4. 佣金数据 to_dict 序列化输出 ────────────────────
    # ⚠️ B07 整改：serialize_flows（按 order_id 序列化）已删除（无外部调用方）。
    #    保留 serialize_flow_by_ids 是因为 cps_commission /serialize 路由仍在调用。

    async def serialize_flow_by_ids(
        self,
        flow_ids: List[int],
    ) -> List[Dict[str, Any]]:
        """按 ID 列表序列化佣金流水

        Args:
            flow_ids: 流水 ID 列表
        Returns:
            流水字典列表
        """
        result: List[Dict[str, Any]] = []
        for fid in flow_ids:
            flow = await self.flow_dao.get_by_id(fid)
            if flow is not None:
                result.append(flow.to_dict())
        return result
