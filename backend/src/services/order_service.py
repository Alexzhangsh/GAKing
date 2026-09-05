# @ai-generated
"""
订单业务服务层
职责：业务规则校验、状态流转控制、订单详情组装
DB 操作全部下沉至 OrderDAO / CommissionFlowDAO，禁止直接写 SQL
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config.constants import OrderStatus
from src.dao.order_dao import OrderDAO
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.user_commission_account_dao import UserCommissionAccountDAO

logger = logging.getLogger("service.order")

# 订单状态合法流转映射（前置状态 → 允许的目标状态集合）
# 基于金角大王订单状态机：PENDING → SETTLABLE → SETTLED，异常分支 FROZEN / INVALID / REFUNDED
VALID_STATUS_TRANSITIONS: Dict[int, set] = {
    OrderStatus.PENDING: {
        OrderStatus.SETTLABLE,
        OrderStatus.INVALID,
        OrderStatus.REFUNDED,
    },
    OrderStatus.FROZEN: {
        OrderStatus.SETTLABLE,
        OrderStatus.INVALID,
    },
    OrderStatus.SETTLABLE: {
        OrderStatus.SETTLED,
        OrderStatus.INVALID,
    },
    OrderStatus.SETTLED: {
        OrderStatus.REFUNDED,
    },
    OrderStatus.INVALID: set(),   # 终态
    OrderStatus.REFUNDED: set(),  # 终态
}

# 转账状态枚举（与 model 字段 transfer_status 对应）
TRANSFER_STATUS_PENDING = "PENDING"
TRANSFER_STATUS_PROCESSING = "PROCESSING"
TRANSFER_STATUS_SUCCESS = "SUCCESS"
TRANSFER_STATUS_FAILED = "FAILED"


class OrderService:
    """订单业务服务

    通过构造函数注入 OrderDAO / CommissionFlowDAO / UserCommissionAccountDAO，业务规则在此层校验
    金额统一使用 Decimal，入库保持 Numeric 定点小数
    """

    def __init__(self, order_dao: OrderDAO, flow_dao: CommissionFlowDAO, account_dao: UserCommissionAccountDAO):
        self.order_dao = order_dao
        self.flow_dao = flow_dao
        self.account_dao = account_dao

    # ── 1. 渠道订单入库（幂等防重复） ────────────────────

    async def create_order_from_channel(
        self,
        out_order_no: str,
        internal_order_no: str,
        user_id: int,
        goods_title: str,
        goods_img: str,
        pay_amount: Decimal,
        total_commission: Decimal,
        user_commission: Decimal,
        platform_commission: Decimal,
        channel_code: str,
        pay_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """渠道订单入库（幂等防重复，out_order_no 唯一校验）

        业务规则：
        1. out_order_no 渠道订单号唯一，重复入库返回已有订单
        2. 金额校验：pay_amount >= 0，佣金各分项 >= 0
        3. 佣金一致性：user_commission + platform_commission == total_commission

        Args:
            out_order_no: 渠道订单号
            internal_order_no: 平台内部订单号
            user_id: 用户 ID
            goods_title: 商品标题
            goods_img: 商品主图 URL
            pay_amount: 支付金额（元）
            total_commission: 总佣金（元）
            user_commission: 用户佣金（元）
            platform_commission: 平台佣金（元）
            channel_code: 渠道标识 (myq / orderx)
            pay_time: 支付时间
        Returns:
            订单字典（含 id、order_status 等）
        Raises:
            ValueError: 参数校验失败
        """
        # 参数校验
        if not out_order_no:
            raise ValueError("渠道订单号 out_order_no 不能为空")
        if not internal_order_no:
            raise ValueError("平台内部订单号 internal_order_no 不能为空")
        if user_id <= 0:
            raise ValueError("user_id 必须为正整数")
        if pay_amount < 0:
            raise ValueError("支付金额 pay_amount 不能为负数")
        if total_commission < 0 or user_commission < 0 or platform_commission < 0:
            raise ValueError("佣金各分项不能为负数")

        # 佣金一致性校验（允许 0.01 精度误差）
        commission_sum = (user_commission + platform_commission).quantize(Decimal("0.01"))
        if abs(commission_sum - total_commission) > Decimal("0.01"):
            raise ValueError(
                f"佣金拆分不一致: user({user_commission}) + platform({platform_commission})"
                f" != total({total_commission})"
            )

        # 幂等防重复：out_order_no 唯一校验
        existing = await self.order_dao.get_by_order_no(out_order_no)
        if existing is not None:
            logger.info(
                "订单已存在，幂等返回: out_order_no=%s, order_id=%s",
                out_order_no,
                existing.id,
            )
            return existing.to_dict()

        # 自动确保用户佣金账户存在（首次订单时自动创建）
        try:
            account = await self.account_dao.get_or_create_by_user_id(user_id)
            logger.info(
                "用户佣金账户已就绪: user_id=%s, account_id=%s",
                user_id,
                account.id,
            )
        except Exception as e:
            logger.warning(
                "创建用户佣金账户失败（不阻断订单创建）: user_id=%s, error=%s",
                user_id,
                str(e),
            )

        # 入库
        order_data = {
            "user_id": user_id,
            "out_order_no": out_order_no,
            "internal_order_no": internal_order_no,
            "goods_title": goods_title,
            "goods_img": goods_img,
            "pay_amount": pay_amount,
            "total_commission": total_commission,
            "user_commission": user_commission,
            "platform_commission": platform_commission,
            "channel_code": channel_code,
            "order_status": int(OrderStatus.PENDING),
            "transfer_status": TRANSFER_STATUS_PENDING,
            "pay_time": pay_time,
        }
        order = await self.order_dao.create(order_data)
        logger.info(
            "渠道订单入库成功: out_order_no=%s, order_id=%s, user_id=%s",
            out_order_no,
            order.id,
            user_id,
        )
        return order.to_dict()

    # ── 2. 订单状态变更流转（校验前置状态合法性） ──────────

    async def transition_order_status(
        self,
        order_id: int,
        target_status: int,
    ) -> Dict[str, Any]:
        """订单状态变更流转（校验前置状态合法性）

        业务规则：
        1. 订单必须存在
        2. 前置状态 → 目标状态必须在 VALID_STATUS_TRANSITIONS 映射中
        3. 终态（INVALID / REFUNDED）不可再变更

        Args:
            order_id: 订单 ID
            target_status: 目标状态值 (OrderStatus 枚举)
        Returns:
            更新后的订单字典
        Raises:
            ValueError: 订单不存在或状态流转非法
        """
        order = await self.order_dao.get_by_id(order_id)
        if order is None:
            raise ValueError(f"订单不存在: order_id={order_id}")

        current_status = int(order.order_status)
        target = int(target_status)

        # 校验目标状态合法性
        if target not in OrderStatus._value2member_map_:
            raise ValueError(f"非法目标状态: {target}")

        # 校验流转合法性
        allowed_targets = VALID_STATUS_TRANSITIONS.get(current_status, set())
        if target not in allowed_targets:
            raise ValueError(
                f"订单状态流转非法: {current_status} → {target}, "
                f"当前状态允许的目标: {allowed_targets or '终态，不可变更'}"
            )

        # 状态变更
        update_data: Dict[str, Any] = {
            "order_status": int(target_status),
        }
        # 结算状态自动记录结算时间
        if target == OrderStatus.SETTLED:
            update_data["settle_time"] = datetime.now()

        updated = await self.order_dao.update_by_id(order_id, update_data)
        logger.info(
            "订单状态流转成功: order_id=%s, %s → %s",
            order_id,
            current_status,
            target,
        )
        return updated.to_dict()

    # ── 3. 分页查询订单列表（多条件筛选） ──────────────────

    async def list_orders(
        self,
        page: int = 1,
        page_size: int = 20,
        channel_code: Optional[str] = None,
        order_status: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """分页查询订单列表（多条件筛选：渠道/状态/用户）

        Args:
            page: 页码，从 1 开始
            page_size: 每页条数
            channel_code: 渠道标识筛选（可选）
            order_status: 订单状态筛选（可选）
            user_id: 用户 ID 筛选（可选）
        Returns:
            {"list": [...], "total": N, "page": page, "page_size": page_size}
        """
        # 构建筛选条件（IntEnum 统一转 int，避免 SQL 比较异常）
        filters: Dict[str, Any] = {}
        if user_id is not None:
            filters["user_id"] = user_id
        if order_status is not None:
            filters["order_status"] = int(order_status)

        # 渠道筛选走专属方法（如有 channel_code 优先使用）
        if channel_code is not None:
            orders, total = await self.order_dao.list_by_channel_code(
                channel_code, page=page, page_size=page_size
            )
            # 若同时有 status 筛选，在内存中二次过滤（DAO 层渠道分页不支持 status）
            if order_status is not None:
                target = int(order_status)
                orders = [o for o in orders if int(o.order_status) == target]
                total = len(orders)
        else:
            orders, total = await self.order_dao.paginate_list(
                page=page,
                page_size=page_size,
                filters=filters if filters else None,
                order_by="-create_time",
            )

        return {
            "list": [o.to_dict() for o in orders],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ── 4. 订单详情连带佣金流水完整组装返回 ────────────────

    async def get_order_detail(self, order_id: int) -> Dict[str, Any]:
        """订单详情连带佣金流水完整组装返回（带 Redis 读穿缓存）

        缓存读穿/回填/失效逻辑下沉至 OrderDAO.get_order_detail_cached，
        本方法仅做不存在校验与日志埋点，序列化由 DAO 层完成。

        Args:
            order_id: 订单 ID
        Returns:
            订单详情 dict（含 commission_flows 列表）
        Raises:
            ValueError: 订单不存在
        """
        order_dict = await self.order_dao.get_order_detail_cached(order_id)
        if order_dict is None:
            raise ValueError(f"订单不存在: order_id={order_id}")

        logger.info(
            "订单详情组装完成: order_id=%s, flows_count=%s",
            order_id,
            len(order_dict.get("commission_flows", [])),
        )
        return order_dict
