# @ai-generated
"""
B08-1 用户佣金资产账户管理服务层

职责：
1. 手工入账 —— 向用户账户增加可用余额，记录资金流水
2. 手工扣款 —— 从用户账户扣减可用余额（FOR UPDATE 行锁防超扣），记录资金流水
3. 冻结/解冻 —— 变更可用余额与冻结余额，记录资金流水
4. 账户详情查询 —— 账户余额 + 最近流水
5. 平台资产统计 —— 全平台账户聚合数据

依赖：
- UserCommissionAccountDAO 账户余额操作（FOR UPDATE 行锁）
- FundFlowDAO 资金流水记录
- 所有余额变动事务包裹 + 流水完整追溯
"""
import logging
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config.b08_1_constants import (
    FUND_FLOW_TYPE_LABELS,
    FundFlowType,
)
from src.dao.b08_1_fund_flow_dao import FundFlowDAO
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.models.business.b08_1_fund_flow_model import FundFlow
from src.models.business.user_commission_account_model import UserCommissionAccount

logger = logging.getLogger("service.b08_1_account")


def _generate_biz_id(flow_type: str, user_id: int) -> str:
    """生成业务流水号（唯一幂等键）

    格式: {flow_type}_{user_id}_{timestamp}_{random_suffix}
    """
    import random

    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
    suffix = random.randint(1000, 9999)
    return f"{flow_type}_{user_id}_{ts}_{suffix}"


def _serialize_account(account: UserCommissionAccount) -> Dict[str, Any]:
    """序列化账户信息"""
    return {
        "id": account.id,
        "user_id": account.user_id,
        "total_balance": float(account.total_balance or 0),
        "available_balance": float(account.available_balance or 0),
        "frozen_balance": float(account.frozen_balance or 0),
        "cumulative_withdrawn": float(account.cumulative_withdrawn or 0),
        "cumulative_fee": float(account.cumulative_fee or 0),
        "last_settle_date": account.last_settle_date.isoformat() if account.last_settle_date else None,
        "version": account.version or 0,
        "create_time": account.create_time.strftime("%Y-%m-%d %H:%M:%S") if account.create_time else None,
        "update_time": account.update_time.strftime("%Y-%m-%d %H:%M:%S") if account.update_time else None,
    }


def _serialize_flow(flow: FundFlow) -> Dict[str, Any]:
    """序列化资金流水"""
    return {
        "id": flow.id,
        "user_id": flow.user_id,
        "flow_type": flow.flow_type,
        "flow_type_label": FUND_FLOW_TYPE_LABELS.get(flow.flow_type, flow.flow_type),
        "amount": float(flow.amount or 0),
        "before_balance": float(flow.before_balance or 0),
        "after_balance": float(flow.after_balance or 0),
        "before_frozen": float(flow.before_frozen or 0),
        "after_frozen": float(flow.after_frozen or 0),
        "order_id": flow.order_id,
        "withdraw_apply_id": flow.withdraw_apply_id,
        "biz_id": flow.biz_id or "",
        "remark": flow.remark or "",
        "operator_id": flow.operator_id,
        "operator_name": flow.operator_name or "",
        "create_time": flow.create_time.strftime("%Y-%m-%d %H:%M:%S") if flow.create_time else None,
    }


class AccountService:
    """用户佣金资产账户管理服务

    通过构造函数注入所需 DAO
    所有 DAO 共享同一 session（由 API 层注入）
    """

    def __init__(
        self,
        account_dao: UserCommissionAccountDAO,
        fund_flow_dao: FundFlowDAO,
    ):
        self.account_dao = account_dao
        self.fund_flow_dao = fund_flow_dao

    # ════════════════════════════════════════════════════════════
    # 1. 账户查询
    # ════════════════════════════════════════════════════════════

    async def get_account_by_user_id(
        self, user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """查询用户账户信息

        Args:
            user_id: 用户ID
        Returns:
            账户信息 dict 或 None
        """
        account = await self.account_dao.get_by_user_id(user_id)
        if account is None:
            return None
        return _serialize_account(account)

    async def list_accounts(
        self,
        user_id: Optional[int] = None,
        min_available: Optional[Decimal] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页查询账户列表

        Args:
            user_id: 按用户ID筛选
            min_available: 可用余额下限
            page: 页码
            page_size: 每页条数
        Returns:
            {"total": int, "page": int, "page_size": int, "items": List[dict]}
        """
        if user_id is not None:
            # 单用户查询
            account = await self.account_dao.get_by_user_id(user_id)
            items = [_serialize_account(account)] if account else []
            total = len(items)
        elif min_available is not None and min_available > 0:
            items_raw, total = await self.account_dao.list_accounts_by_balance_ge(
                min_available=min_available,
                page=page,
                page_size=page_size,
            )
            items = [_serialize_account(a) for a in items_raw]
        else:
            items_raw, total = await self.account_dao.paginate_list(
                page=page, page_size=page_size,
                order_by="-available_balance",
            )
            items = [_serialize_account(a) for a in items_raw]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    # ════════════════════════════════════════════════════════════
    # 2. 手工入账（增加可用余额 + 流水记录）
    # ════════════════════════════════════════════════════════════

    async def credit(
        self,
        user_id: int,
        amount: Decimal,
        remark: str = "",
        operator_id: int = 0,
        operator_name: str = "",
        order_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """手工入账

        流程：
        1. FOR UPDATE 行锁账户
        2. 校验余额有效性
        3. 更新余额
        4. 创建资金流水
        5. 事务提交 + 失效缓存

        Args:
            user_id: 用户ID
            amount: 入账金额（必须 > 0）
            remark: 备注
            operator_id: 操作人ID
            operator_name: 操作人姓名
            order_id: 关联订单ID
        Returns:
            入账结果
        """
        if amount <= 0:
            return {"status": "failed", "message": "入账金额必须大于0"}

        biz_id = _generate_biz_id(FundFlowType.DEPOSIT.value, user_id)

        try:
            # 获取或创建账户（FOR UPDATE 行锁）
            account = await self.account_dao.get_for_update(user_id)
            if account is None:
                # 账户不存在，创建后再锁
                account = await self.account_dao.get_or_create_by_user_id(user_id)
                account = await self.account_dao.get_for_update(user_id)
                if account is None:
                    return {"status": "failed", "message": f"无法创建用户账户: user_id={user_id}"}

            before_balance = Decimal(str(account.available_balance))
            before_frozen = Decimal(str(account.frozen_balance))
            after_balance = before_balance + amount

            # 更新余额
            account.available_balance = after_balance
            account.total_balance = Decimal(str(account.total_balance)) + amount
            account.version = (account.version or 0) + 1

            # 创建资金流水
            flow = await self.fund_flow_dao.create_flow(
                user_id=user_id,
                flow_type=FundFlowType.DEPOSIT.value,
                amount=amount,
                before_balance=before_balance,
                after_balance=after_balance,
                before_frozen=before_frozen,
                after_frozen=after_frozen,
                biz_id=biz_id,
                order_id=order_id,
                remark=remark or f"手工入账 {amount} 元",
                operator_id=operator_id,
                operator_name=operator_name,
            )

            await self.account_dao.session.flush()
            await self.account_dao.session.commit()
            await self.account_dao._invalidate_account_cache(user_id)

            logger.info(
                "[b08_account] 手工入账成功 user_id=%s amount=%s operator=%s",
                user_id, amount, operator_name,
            )

            return {
                "status": "success",
                "user_id": user_id,
                "amount": float(amount),
                "before_balance": float(before_balance),
                "after_balance": float(after_balance),
                "flow_id": flow.id,
                "biz_id": biz_id,
                "message": f"入账成功，金额 {float(amount):.2f} 元",
            }

        except Exception as e:
            await self.account_dao.session.rollback()
            logger.error(
                "[b08_account] 手工入账失败 user_id=%s amount=%s: %s\n%s",
                user_id, amount, e, traceback.format_exc(),
            )
            return {"status": "failed", "message": str(e)}

    # ════════════════════════════════════════════════════════════
    # 3. 手工扣款（减少可用余额 + FOR UPDATE 防超扣 + 流水记录）
    # ════════════════════════════════════════════════════════════

    async def debit(
        self,
        user_id: int,
        amount: Decimal,
        remark: str = "",
        operator_id: int = 0,
        operator_name: str = "",
        order_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """手工扣款

        流程：
        1. FOR UPDATE 行锁账户
        2. 校验可用余额 >= 扣款金额
        3. 更新余额
        4. 创建资金流水
        5. 事务提交 + 失效缓存

        Args:
            user_id: 用户ID
            amount: 扣款金额（必须 > 0）
            remark: 备注
            operator_id: 操作人ID
            operator_name: 操作人姓名
            order_id: 关联订单ID
        Returns:
            扣款结果
        """
        if amount <= 0:
            return {"status": "failed", "message": "扣款金额必须大于0"}

        biz_id = _generate_biz_id(FundFlowType.DEDUCT.value, user_id)
        deduct_amount = -amount  # 扣款金额为负

        try:
            # FOR UPDATE 行锁
            account = await self.account_dao.get_for_update(user_id)
            if account is None:
                return {"status": "failed", "message": f"用户账户不存在: user_id={user_id}"}

            before_balance = Decimal(str(account.available_balance))
            before_frozen = Decimal(str(account.frozen_balance))
            after_balance = before_balance - amount

            # 透支校验
            if after_balance < 0:
                return {
                    "status": "failed",
                    "message": f"可用余额不足: 当前 {float(before_balance):.2f} 元, 需扣 {float(amount):.2f} 元",
                }

            # 更新余额
            account.available_balance = after_balance
            account.version = (account.version or 0) + 1

            # 创建资金流水
            flow = await self.fund_flow_dao.create_flow(
                user_id=user_id,
                flow_type=FundFlowType.DEDUCT.value,
                amount=deduct_amount,
                before_balance=before_balance,
                after_balance=after_balance,
                before_frozen=before_frozen,
                after_frozen=after_frozen,
                biz_id=biz_id,
                order_id=order_id,
                remark=remark or f"手工扣款 {amount} 元",
                operator_id=operator_id,
                operator_name=operator_name,
            )

            await self.account_dao.session.flush()
            await self.account_dao.session.commit()
            await self.account_dao._invalidate_account_cache(user_id)

            logger.info(
                "[b08_account] 手工扣款成功 user_id=%s amount=%s operator=%s",
                user_id, amount, operator_name,
            )

            return {
                "status": "success",
                "user_id": user_id,
                "amount": float(-amount),
                "before_balance": float(before_balance),
                "after_balance": float(after_balance),
                "flow_id": flow.id,
                "biz_id": biz_id,
                "message": f"扣款成功，金额 {float(amount):.2f} 元",
            }

        except Exception as e:
            await self.account_dao.session.rollback()
            logger.error(
                "[b08_account] 手工扣款失败 user_id=%s amount=%s: %s\n%s",
                user_id, amount, e, traceback.format_exc(),
            )
            return {"status": "failed", "message": str(e)}

    # ════════════════════════════════════════════════════════════
    # 4. 冻结余额（可用→冻结 + 流水记录）
    # ════════════════════════════════════════════════════════════

    async def freeze_balance(
        self,
        user_id: int,
        amount: Decimal,
        remark: str = "",
        operator_id: int = 0,
        operator_name: str = "",
    ) -> Dict[str, Any]:
        """冻结余额：available_balance -= amount, frozen_balance += amount

        Args:
            user_id: 用户ID
            amount: 冻结金额（必须 > 0）
            remark: 备注
            operator_id: 操作人ID
            operator_name: 操作人姓名
        Returns:
            冻结结果
        """
        if amount <= 0:
            return {"status": "failed", "message": "冻结金额必须大于0"}

        biz_id = _generate_biz_id(FundFlowType.FREEZE.value, user_id)

        try:
            account = await self.account_dao.get_for_update(user_id)
            if account is None:
                return {"status": "failed", "message": f"用户账户不存在: user_id={user_id}"}

            before_balance = Decimal(str(account.available_balance))
            before_frozen = Decimal(str(account.frozen_balance))

            if before_balance < amount:
                return {
                    "status": "failed",
                    "message": f"可用余额不足: 当前 {float(before_balance):.2f} 元, 需冻结 {float(amount):.2f} 元",
                }

            after_balance = before_balance - amount
            after_frozen = before_frozen + amount

            account.available_balance = after_balance
            account.frozen_balance = after_frozen
            account.version = (account.version or 0) + 1

            flow = await self.fund_flow_dao.create_flow(
                user_id=user_id,
                flow_type=FundFlowType.FREEZE.value,
                amount=-amount,
                before_balance=before_balance,
                after_balance=after_balance,
                before_frozen=before_frozen,
                after_frozen=after_frozen,
                biz_id=biz_id,
                remark=remark or f"冻结余额 {amount} 元",
                operator_id=operator_id,
                operator_name=operator_name,
            )

            await self.account_dao.session.flush()
            await self.account_dao.session.commit()
            await self.account_dao._invalidate_account_cache(user_id)

            logger.info(
                "[b08_account] 冻结余额成功 user_id=%s amount=%s operator=%s",
                user_id, amount, operator_name,
            )

            return {
                "status": "success",
                "user_id": user_id,
                "amount": float(amount),
                "before_available": float(before_balance),
                "after_available": float(after_balance),
                "before_frozen": float(before_frozen),
                "after_frozen": float(after_frozen),
                "flow_id": flow.id,
                "biz_id": biz_id,
                "message": f"冻结成功，冻结金额 {float(amount):.2f} 元",
            }

        except Exception as e:
            await self.account_dao.session.rollback()
            logger.error(
                "[b08_account] 冻结余额失败 user_id=%s amount=%s: %s\n%s",
                user_id, amount, e, traceback.format_exc(),
            )
            return {"status": "failed", "message": str(e)}

    # ════════════════════════════════════════════════════════════
    # 5. 解冻余额（冻结→可用 + 流水记录）
    # ════════════════════════════════════════════════════════════

    async def unfreeze_balance(
        self,
        user_id: int,
        amount: Decimal,
        remark: str = "",
        operator_id: int = 0,
        operator_name: str = "",
    ) -> Dict[str, Any]:
        """解冻余额：available_balance += amount, frozen_balance -= amount

        Args:
            user_id: 用户ID
            amount: 解冻金额（必须 > 0）
            remark: 备注
            operator_id: 操作人ID
            operator_name: 操作人姓名
        Returns:
            解冻结果
        """
        if amount <= 0:
            return {"status": "failed", "message": "解冻金额必须大于0"}

        biz_id = _generate_biz_id(FundFlowType.UNFREEZE.value, user_id)

        try:
            account = await self.account_dao.get_for_update(user_id)
            if account is None:
                return {"status": "failed", "message": f"用户账户不存在: user_id={user_id}"}

            before_balance = Decimal(str(account.available_balance))
            before_frozen = Decimal(str(account.frozen_balance))

            if before_frozen < amount:
                return {
                    "status": "failed",
                    "message": f"冻结余额不足: 当前 {float(before_frozen):.2f} 元, 需解冻 {float(amount):.2f} 元",
                }

            after_balance = before_balance + amount
            after_frozen = before_frozen - amount

            account.available_balance = after_balance
            account.frozen_balance = after_frozen
            account.version = (account.version or 0) + 1

            flow = await self.fund_flow_dao.create_flow(
                user_id=user_id,
                flow_type=FundFlowType.UNFREEZE.value,
                amount=amount,
                before_balance=before_balance,
                after_balance=after_balance,
                before_frozen=before_frozen,
                after_frozen=after_frozen,
                biz_id=biz_id,
                remark=remark or f"解冻余额 {amount} 元",
                operator_id=operator_id,
                operator_name=operator_name,
            )

            await self.account_dao.session.flush()
            await self.account_dao.session.commit()
            await self.account_dao._invalidate_account_cache(user_id)

            logger.info(
                "[b08_account] 解冻余额成功 user_id=%s amount=%s operator=%s",
                user_id, amount, operator_name,
            )

            return {
                "status": "success",
                "user_id": user_id,
                "amount": float(amount),
                "before_available": float(before_balance),
                "after_available": float(after_balance),
                "before_frozen": float(before_frozen),
                "after_frozen": float(after_frozen),
                "flow_id": flow.id,
                "biz_id": biz_id,
                "message": f"解冻成功，解冻金额 {float(amount):.2f} 元",
            }

        except Exception as e:
            await self.account_dao.session.rollback()
            logger.error(
                "[b08_account] 解冻余额失败 user_id=%s amount=%s: %s\n%s",
                user_id, amount, e, traceback.format_exc(),
            )
            return {"status": "failed", "message": str(e)}

    # ════════════════════════════════════════════════════════════
    # 6. 资金流水查询
    # ════════════════════════════════════════════════════════════

    async def list_fund_flows(
        self,
        user_id: Optional[int] = None,
        flow_type: Optional[str] = None,
        order_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页查询资金流水

        Returns:
            {"total": int, "page": int, "page_size": int, "items": List[dict]}
        """
        items_raw, total = await self.fund_flow_dao.list_with_filters(
            user_id=user_id,
            flow_type=flow_type,
            order_id=order_id,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )
        items = [_serialize_flow(f) for f in items_raw]
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    # ════════════════════════════════════════════════════════════
    # 7. 平台资产统计
    # ════════════════════════════════════════════════════════════

    async def get_platform_statistics(self) -> Dict[str, Any]:
        """获取全平台资产统计概览

        Returns:
            {"total_balance": float, "available_balance": float,
             "frozen_balance": float, "withdrawn": float, "fee": float,
             "account_count": int}
        """
        try:
            stats = await self.account_dao.aggregate_platform_balance()
            return {
                "total_balance": float(stats["total"]),
                "available_balance": float(stats["available"]),
                "frozen_balance": float(stats["frozen"]),
                "cumulative_withdrawn": float(stats["withdrawn"]),
                "cumulative_fee": float(stats["fee"]),
                "account_count": stats["account_count"],
            }
        except Exception as e:
            logger.error(
                "[b08_account] 获取平台统计异常: %s\n%s",
                e, traceback.format_exc(),
            )
            return {
                "total_balance": 0.0,
                "available_balance": 0.0,
                "frozen_balance": 0.0,
                "cumulative_withdrawn": 0.0,
                "cumulative_fee": 0.0,
                "account_count": 0,
            }