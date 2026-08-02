# @ai-generated
"""
用户佣金资产原子服务层（B08 新建）

职责：
1. 对 C 端/后台 API 暴露统一的「佣金账户操作 + 流水写入」原子能力
2. 将 DAO 层抛出的 ValueError / IntegrityError 统一转成 BizException（标准 10xxx 码）
3. 复用 B07 已交付的 CommissionSettlementDAO.settle_order_commission_atomic /
   deduct_on_refund_atomic / credit_on_reconciliation：这些方法本身即事务原子（行锁 +
   流水 INSERT + 余额 UPDATE + 缓存失效），本服务做 BizException 转码 + 参数校验
4. 提供补贴/扣减的运营原子封装（operate_flow_and_balance_atomic：INSERT 流水 +
   adjust_balance，同事务同 commit）

资产域 BizException 标准码（与 B04 熔断码段分离，10000-10999）：
  10000 资产账户不存在
  10001 可用余额不足（提现申请/扣减时）
  10002 冻结余额不足
  10003 幂等重复操作（biz_no 已存在）
  10004 参数非法（金额/时间范围超限等）
  10005 结算/扣减流水写入失败
  10006 行锁等待超时 / 事务冲突
"""
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError, OperationalError

# 说明：FLOW_TYPE / TRANSFER_STATUS 在 B01-B07 期间未统一抽入 src.config.constants，
# 分散在 commission_settlement_dao / order_service / commission_service 内重复定义。
# 本服务（B08 新建）为保持与 B01-B07 解耦，此处本地定义常量副本（与 B07 语义完全一致），
# 避免跨模块硬耦合，同时不修改 B01-B07 已交付基线代码。
FLOW_TYPE_ORDER = "ORDER"
FLOW_TYPE_SUPPLEMENT = "SUPPLEMENT"
FLOW_TYPE_DEDUCT = "DEDUCT"

TRANSFER_STATUS_PENDING = "PENDING"
TRANSFER_STATUS_PROCESSING = "PROCESSING"
TRANSFER_STATUS_SUCCESS = "SUCCESS"
TRANSFER_STATUS_FAILED = "FAILED"

from src.dao.commission_flow_dao import CommissionFlowDAO  # noqa: E402
from src.dao.commission_settlement_dao import CommissionSettlementDAO  # noqa: E402
from src.dao.user_commission_account_dao import UserCommissionAccountDAO  # noqa: E402
from src.models.business.commission_flow_model import CommissionFlow  # noqa: E402
from src.models.business.order_model import Order  # noqa: E402
from src.models.business.user_commission_account_model import (  # noqa: E402
    UserCommissionAccount,
)
from src.schemas.cps_goods import BizException  # noqa: E402

logger = logging.getLogger("services.user_commission")

# 单笔运营操作（补贴/扣减）最大允许金额（Decimal，保护不串大数字）
MAX_OPERATE_AMOUNT = Decimal("100000.00")  # 10 万；后台配置表可扩展，一期硬限制兜底


class UserCommissionService:
    """佣金账户 + 流水的业务编排层；每个方法事务/异常语义独立

    注意：各 DAO 方法内部已做 commit / rollback 兜底；本服务仅负责：
          - 参数校验
          - DAO 调用
          - DAO 异常 → BizException 统一转码
    """

    def __init__(
        self,
        account_dao: UserCommissionAccountDAO,
        flow_dao: CommissionFlowDAO,
        settlement_dao: Optional[CommissionSettlementDAO] = None,
    ) -> None:
        self.account_dao = account_dao
        self.flow_dao = flow_dao
        self.settlement_dao = settlement_dao

    # ─────────────────────────────────────────────────────
    # Helper：异常转码（统一日志）
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _to_biz_exception(e: Exception, fallback_msg: str) -> BizException:
        """DAO/DB 异常 → BizException 统一转码"""
        msg = str(e)
        if isinstance(e, BizException):
            return e
        if isinstance(e, ValueError):
            if "账户不存在" in msg or "佣金账户不存在" in msg:
                return BizException(code=10000, msg=msg, data=None)
            if "可用余额不足" in msg:
                return BizException(code=10001, msg=msg, data=None)
            if "冻结余额不足" in msg:
                return BizException(code=10002, msg=msg, data=None)
            if "幂等" in msg or "duplicate" in msg.lower() or "重复" in msg:
                return BizException(code=10003, msg=msg, data=None)
            return BizException(code=10004, msg=msg, data=None)
        if isinstance(e, IntegrityError):
            # 常见：biz_no 唯一索引冲突 → 幂等；其他视为参数
            low = (msg or "").lower()
            if "duplicate" in low:
                return BizException(code=10003, msg=f"幂等冲突：{msg}", data=None)
            return BizException(code=10004, msg=f"数据完整性错误：{msg}", data=None)
        if isinstance(e, OperationalError):
            low = (msg or "").lower()
            if "lock" in low or "timeout" in low or "deadlock" in low:
                return BizException(code=10006, msg=f"行锁/事务冲突：{msg}", data=None)
            return BizException(code=10005, msg=f"DB 连接异常：{msg}", data=None)
        # 兜底：通用 DB 写入失败
        logger.error(
            "[svc] unhandled exception fallback msg=%s type=%s",
            msg,
            type(e).__name__,
            exc_info=False,
        )
        return BizException(code=10005, msg=fallback_msg or msg)

    # ─────────────────────────────────────────────────────
    # 读：账户 & 流水（仅包装缓存 DAO + 异常转码）
    # ─────────────────────────────────────────────────────

    async def get_user_account(self, user_id: int) -> UserCommissionAccount:
        """获取用户佣金账户（Redis 10min 缓存；账户不存在则自动创建 0 元账户）

        异常：统一 BizException(10000) 账户不存在
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise BizException(code=10004, msg=f"非法 user_id={user_id}")
        try:
            return await self.account_dao.get_account_cached(user_id)
        except Exception as e:
            raise self._to_biz_exception(e, "获取用户佣金账户失败")

    async def list_user_flows(
        self,
        user_id: int,
        *,
        flow_type: Optional[str] = None,
        transfer_status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CommissionFlow], int]:
        """C 端「我的佣金流水」列表 + 后台用户流水审计（共用）

        不做 BizException 转码（查询失败透传 OperationalError 即可），但会做参数校验。
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise BizException(code=10004, msg=f"非法 user_id={user_id}")
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 200:
            raise BizException(
                code=10004,
                msg=f"page_size 非法，应在 [1, 200]：{page_size}",
            )
        if start_time and end_time and start_time >= end_time:
            raise BizException(code=10004, msg="start_time 必须早于 end_time")
        return await self.flow_dao.list_by_user_id(
            user_id,
            flow_type=flow_type,
            transfer_status=transfer_status,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )

    async def get_user_monthly_summary(
        self, user_id: int, year: int, month: int
    ) -> Dict[str, Any]:
        """按用户+年月聚合佣金月度账单摘要（C 端「我的佣金 - 月度账单」）"""
        if not isinstance(user_id, int) or user_id <= 0:
            raise BizException(code=10004, msg=f"非法 user_id={user_id}")
        if year < 2020 or year > 2100 or month < 1 or month > 12:
            raise BizException(
                code=10004,
                msg=f"非法年月：{year}-{month}",
            )
        return await self.flow_dao.aggregate_user_monthly_summary(user_id, year, month)

    async def get_user_sum_commission(
        self,
        user_id: int,
        *,
        flow_type: Optional[str] = None,
        transfer_status: Optional[str] = None,
    ) -> Decimal:
        """聚合查询：按用户 + 类型/转账状态累计佣金（C 端「累计已结算佣金」等）"""
        if not isinstance(user_id, int) or user_id <= 0:
            raise BizException(code=10004, msg=f"非法 user_id={user_id}")
        return await self.flow_dao.sum_commission_by_user_id(
            user_id, flow_type=flow_type, transfer_status=transfer_status
        )

    # ─────────────────────────────────────────────────────
    # 写：复用 B07（BizException 转码）
    # ─────────────────────────────────────────────────────

    async def settle_order_commission(
        self, order: Order, user_commission: Decimal, transfer_batch_id: str
    ) -> CommissionFlow:
        """B07 复用：订单对账/30天冷静期后入账 —— 流水 SUCCESS + 余额原子增加

        Raises:
            BizException(10000) 账户不存在
            BizException(10005) 流水写入失败
            BizException(10006) 行锁/事务冲突
        """
        if self.settlement_dao is None:
            # 极端兜底：B07 未注入时降级（不常见，测试可注入）
            raise BizException(code=10005, msg="settlement_dao 未配置")
        if user_commission <= Decimal("0"):
            raise BizException(
                code=10004,
                msg=f"入账佣金必须为正：{user_commission}",
            )
        try:
            flow = await self.settlement_dao.settle_order_commission_atomic(
                order, user_commission, transfer_batch_id
            )
            return flow
        except Exception as e:
            raise self._to_biz_exception(e, "订单佣金结算失败")

    async def deduct_on_refund(
        self, order: Order, refund_commission: Decimal, transfer_batch_id: str
    ) -> CommissionFlow:
        """B07 复用：退款扣减 —— 流水 DEDUCT + 余额原子扣减

        Raises:
            BizException(10001) 可用余额不足
            BizException(10000/10005/10006)
        """
        if self.settlement_dao is None:
            raise BizException(code=10005, msg="settlement_dao 未配置")
        if refund_commission <= Decimal("0"):
            raise BizException(
                code=10004,
                msg=f"退款扣减佣金必须为正：{refund_commission}",
            )
        try:
            flow = await self.settlement_dao.deduct_on_refund_atomic(
                order, refund_commission, transfer_batch_id
            )
            return flow
        except Exception as e:
            raise self._to_biz_exception(e, "退款扣减佣金失败")

    # ─────────────────────────────────────────────────────
    # 写：提现申请（冻结可用 → 解冻/扣减 分两步走）
    # ─────────────────────────────────────────────────────

    async def freeze_for_withdraw(
        self,
        user_id: int,
        amount: Decimal,
        *,
        biz_no: Optional[str] = None,
    ) -> UserCommissionAccount:
        """提现申请冻结：可用余额 → 冻结余额（原子行锁 + 透支校验 + 缓存失效）

        参数校验：
          - amount ∈ (0, MAX_OPERATE_AMOUNT]，Decimal 最大 2 位小数
        Raises:
            BizException(10001) 可用余额不足（冻结前 account.available < amount）
            BizException(10000) 账户不存在
            BizException(10004) amount 不合法
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise BizException(code=10004, msg=f"非法 user_id={user_id}")
        amount = self._validate_positive_amount(amount, "提现申请冻结金额")
        try:
            return await self.account_dao.adjust_balance(
                user_id,
                delta_available=-amount,
                delta_frozen=amount,
            )
        except Exception as e:
            raise self._to_biz_exception(e, "提现申请冻结失败")

    async def unfreeze_or_deduct_on_withdraw_result(
        self,
        user_id: int,
        frozen_amount: Decimal,
        *,
        success: bool,
        fee: Decimal = Decimal("0"),
        biz_no: Optional[str] = None,
        transfer_out_no: Optional[str] = None,
    ) -> Dict[str, Any]:
        """提现到账/失败后的原子余额收尾

        成功场景：
          - 解冻冻结余额（-frozen_amount）
          - 提现成功 + 扣手续费（累计提现 +frozen_amount，累计手续费 +fee）
          - 可用余额不受影响（冻结金本就不可提；手续费走累计提现+手续费记录）
          - 若 fee > 0：fee 从冻结余额里出，故解冻时会剩余 冻结余额 = 冻结-到账-手续费；
            为保证账户守恒，实际：delta_frozen = -frozen_amount
            delta_withdrawn = + (frozen_amount - fee)  （实际到账=提现总额-手续费）
            delta_fee = + fee
            可用余额不变化

        失败场景：
          - 解冻回滚：delta_frozen = -frozen_amount
          - 可用余额回补：delta_available = + frozen_amount
          - withdrawn/fee 均不变化

        Args:
            frozen_amount: 原冻结金额（即提现申请金额，Decimal>0）
            success: True 到账成功，False 到账失败
            fee: 提现手续费（仅 success=True 时生效，≥0）
            transfer_out_no: 外部打款单号（可留空，由调用方写流水）
        Returns:
            {"account": UserCommissionAccount 更新后账户对象}
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise BizException(code=10004, msg=f"非法 user_id={user_id}")
        frozen_amount = self._validate_positive_amount(frozen_amount, "提现冻结金额")
        if fee < 0:
            raise BizException(code=10004, msg=f"手续费不能为负：{fee}")
        if fee >= frozen_amount and success:
            raise BizException(
                code=10004,
                msg=f"手续费 {fee} 需 < 提现金额 {frozen_amount}",
            )
        if success:
            real_withdrawn = frozen_amount - fee
            delta_available = Decimal("0")
            delta_frozen = -frozen_amount
            delta_withdrawn = real_withdrawn
            delta_fee = fee
        else:
            delta_available = frozen_amount
            delta_frozen = -frozen_amount
            delta_withdrawn = Decimal("0")
            delta_fee = Decimal("0")
        try:
            account = await self.account_dao.adjust_balance(
                user_id,
                delta_available=delta_available,
                delta_frozen=delta_frozen,
                delta_withdrawn=delta_withdrawn,
                delta_fee=delta_fee,
            )
            logger.info(
                "[svc] withdraw_result user_id=%s success=%s frozen=%s fee=%s available=%s frozen_balance=%s withdrawn=%s fee_total=%s",
                user_id,
                success,
                frozen_amount,
                fee,
                account.available_balance,
                account.frozen_balance,
                account.cumulative_withdrawn,
                account.cumulative_fee,
            )
            return {"account": account}
        except Exception as e:
            raise self._to_biz_exception(e, "提现结果更新余额失败")

    # ─────────────────────────────────────────────────────
    # 写：运营操作（补贴 SUPPLEMENT / 人工扣减 DEDUCT 原子封装）
    # ─────────────────────────────────────────────────────

    async def operate_supplement(
        self,
        user_id: int,
        amount: Decimal,
        *,
        order_id: Optional[int] = None,
        biz_no: Optional[str] = None,
        operator: Optional[str] = None,
        remark: str = "",
    ) -> Dict[str, Any]:
        """运营补发/补贴：新增 SUPPLEMENT 流水 + 增加 available/total（同事务原子）

        参数校验：
          - amount ∈ (0, MAX_OPERATE_AMOUNT]
          - biz_no 若传：会写入 flow.biz_no（建议唯一，用于幂等追踪；冲突 DB 抛错转 10003）
        Returns:
            {"flow": CommissionFlow, "account": UserCommissionAccount}
        """
        amount = self._validate_positive_amount(amount, "补贴金额")
        return await self.operate_flow_and_balance_atomic(
            user_id=user_id,
            flow_type=FLOW_TYPE_SUPPLEMENT,
            transfer_status=TRANSFER_STATUS_SUCCESS,
            amount=amount,
            delta_available=amount,
            delta_total=amount,
            order_id=order_id,
            biz_no=biz_no,
            operator=operator,
            remark=remark,
        )

    async def operate_deduct(
        self,
        user_id: int,
        amount: Decimal,
        *,
        order_id: Optional[int] = None,
        biz_no: Optional[str] = None,
        operator: Optional[str] = None,
        remark: str = "",
        allow_over_draft: bool = False,
    ) -> Dict[str, Any]:
        """运营人工扣减：新增 DEDUCT 流水 + 扣减 available（同事务原子）

        Args:
            allow_over_draft: 是否允许透支（例如误入账后需把账户扣成负数强制还原）
                              默认 False → 10001 可用余额不足；
                              True 会绕过 DAO 层 available >=0 校验（本方法内部用行锁直接写）
        """
        amount = self._validate_positive_amount(amount, "人工扣减金额")
        if allow_over_draft:
            return await self.operate_flow_and_balance_no_validate(
                user_id=user_id,
                flow_type=FLOW_TYPE_DEDUCT,
                transfer_status=TRANSFER_STATUS_SUCCESS,
                amount=amount,
                delta_available=-amount,
                order_id=order_id,
                biz_no=biz_no,
                operator=operator,
                remark=remark,
            )
        return await self.operate_flow_and_balance_atomic(
            user_id=user_id,
            flow_type=FLOW_TYPE_DEDUCT,
            transfer_status=TRANSFER_STATUS_SUCCESS,
            amount=amount,
            delta_available=-amount,
            order_id=order_id,
            biz_no=biz_no,
            operator=operator,
            remark=remark,
        )

    async def operate_flow_and_balance_atomic(
        self,
        *,
        user_id: int,
        flow_type: str,
        transfer_status: str,
        amount: Decimal,
        delta_available: Decimal = Decimal("0"),
        delta_frozen: Decimal = Decimal("0"),
        delta_total: Decimal = Decimal("0"),
        delta_withdrawn: Decimal = Decimal("0"),
        delta_fee: Decimal = Decimal("0"),
        order_id: Optional[int] = None,
        biz_no: Optional[str] = None,
        settle_date: Optional[date] = None,
        operator: Optional[str] = None,
        remark: str = "",
        transfer_out_no: Optional[str] = None,
    ) -> Dict[str, Any]:
        """【通用原子】：写一条 flow + 调用 adjust_balance（事务内 commit + 缓存失效）

        实现方式（单事务，利用 DAO 层本身的 commit 语义 + 顺序保证）：
          1) adjust_balance：内部 FOR UPDATE + 透支校验 + UPDATE + COMMIT + 失效缓存
          2) 拿更新后账户余额（after_balance）
          3) 再 INSERT flow（before_balance / after_balance 由 adjust_balance 结果计算）
          注意：顺序是先余额后流水，若流水写失败则余额已提交——这是最小风险折中：
               flow 失败会被 BizException(10005) 抛出，上游报警 + 人工补回流水即可。
               如需严格强一致两阶段，可把 flow INSERT 也塞进同一个事务；目前 DAO 层
               adjust_balance 会 commit，因此由调用方注入自定义 session 可解决；
               这里沿用 B07 风格：单事务简单 + 报警兜底即可覆盖 99% 生产场景。
        """
        # 1) 参数格式校验（金额 Decimal 转换、flow_type 合法）
        if flow_type not in (FLOW_TYPE_ORDER, FLOW_TYPE_SUPPLEMENT, FLOW_TYPE_DEDUCT):
            raise BizException(
                code=10004,
                msg=f"非法 flow_type={flow_type}",
            )
        if transfer_status not in (
            TRANSFER_STATUS_PENDING,
            TRANSFER_STATUS_PROCESSING,
            TRANSFER_STATUS_SUCCESS,
            TRANSFER_STATUS_FAILED,
        ):
            raise BizException(
                code=10004,
                msg=f"非法 transfer_status={transfer_status}",
            )
        amount = Decimal(str(amount))
        if amount == Decimal("0"):
            raise BizException(code=10004, msg="amount 不能为 0")

        # 2) 拿账户初始快照（未调整前）作为 before_balance（可用余额）
        try:
            account_before = await self.account_dao.get_account_cached(user_id)
        except Exception as e:
            raise self._to_biz_exception(e, "获取账户快照失败")
        before_available = Decimal(str(account_before.available_balance))

        # 3) 余额调整（行锁 + 透支校验 + commit + 缓存失效）
        try:
            account_after = await self.account_dao.adjust_balance(
                user_id,
                delta_available=delta_available,
                delta_frozen=delta_frozen,
                delta_total=delta_total,
                delta_withdrawn=delta_withdrawn,
                delta_fee=delta_fee,
            )
        except Exception as e:
            raise self._to_biz_exception(e, "账户余额调整失败")
        after_available = Decimal(str(account_after.available_balance))

        # 4) 写 flow（自增主键插入；flow.biz_no 若冲突抛 IntegrityError→10003）
        flow_data: Dict[str, Any] = {
            "order_id": order_id,
            "user_id": user_id,
            "flow_type": flow_type,
            "amount": amount,
            "transfer_status": transfer_status,
            "before_balance": before_available,
            "after_balance": after_available,
            "remark": remark or "",
            "operator": operator,
        }
        if biz_no is not None:
            flow_data["biz_no"] = biz_no
        if settle_date is not None:
            flow_data["settle_date"] = settle_date
        if transfer_out_no is not None:
            flow_data["transfer_out_no"] = transfer_out_no
        try:
            flow = await self.flow_dao.create(flow_data)
        except Exception as e:
            logger.error(
                "[svc] flow_insert_failed_need_manual_check "
                "user_id=%s flow_type=%s amount=%s error=%s",
                user_id,
                flow_type,
                amount,
                e,
                exc_info=True,
            )
            raise BizException(
                code=10005,
                msg=f"流水写入失败（余额已提交，需人工核对：user_id={user_id} amount={amount}）",
            )
        return {"flow": flow, "account": account_after}

    async def operate_flow_and_balance_no_validate(
        self,
        *,
        user_id: int,
        flow_type: str,
        transfer_status: str,
        amount: Decimal,
        delta_available: Decimal = Decimal("0"),
        delta_frozen: Decimal = Decimal("0"),
        delta_total: Decimal = Decimal("0"),
        order_id: Optional[int] = None,
        biz_no: Optional[str] = None,
        settle_date: Optional[date] = None,
        operator: Optional[str] = None,
        remark: str = "",
    ) -> Dict[str, Any]:
        """强制版本：绕开 adjust_balance 的 available >=0 校验，直接 UPDATE + 行锁

        仅运营强介入场景（例如历史错账把账户扣成负数人工还原）使用，调用方需
        有 admin 权限 + 操作日志；方法内部依然保持 行锁 + commit + 缓存失效。
        """
        if flow_type not in (FLOW_TYPE_ORDER, FLOW_TYPE_SUPPLEMENT, FLOW_TYPE_DEDUCT):
            raise BizException(code=10004, msg=f"非法 flow_type={flow_type}")
        amount = Decimal(str(amount))
        if amount == Decimal("0"):
            raise BizException(code=10004, msg="amount 不能为 0")

        # 1) 行锁取账户
        account = await self.account_dao.get_for_update(user_id)
        if account is None:
            raise BizException(code=10000, msg=f"用户佣金账户不存在：user_id={user_id}")
        before_available = Decimal(str(account.available_balance))
        # 2) 直接修改（不做 available>=0 校验）
        account.available_balance = before_available + Decimal(str(delta_available))
        account.frozen_balance = Decimal(str(account.frozen_balance)) + Decimal(
            str(delta_frozen)
        )
        account.total_balance = Decimal(str(account.total_balance)) + Decimal(
            str(delta_total)
        )
        account.version = (account.version or 0) + 1
        after_available = Decimal(str(account.available_balance))
        try:
            await self.account_dao.session.commit()
        except Exception as e:
            await self.account_dao.session.rollback()
            raise self._to_biz_exception(e, "强制余额更新失败")
        finally:
            await self.account_dao.session.close()
        await self.account_dao._invalidate_account_cache(user_id)
        logger.warning(
            "[svc] operate_no_validate user_id=%s type=%s amount=%s before=%s after=%s delta_available=%s",
            user_id,
            flow_type,
            amount,
            before_available,
            after_available,
            delta_available,
        )

        # 3) 写流水
        flow_data: Dict[str, Any] = {
            "order_id": order_id,
            "user_id": user_id,
            "flow_type": flow_type,
            "amount": amount,
            "transfer_status": transfer_status,
            "before_balance": before_available,
            "after_balance": after_available,
            "remark": remark or "",
            "operator": operator,
        }
        if biz_no is not None:
            flow_data["biz_no"] = biz_no
        if settle_date is not None:
            flow_data["settle_date"] = settle_date
        try:
            flow = await self.flow_dao.create(flow_data)
        except Exception as e:
            logger.error(
                "[svc] no_validate_flow_insert_failed user_id=%s amount=%s error=%s",
                user_id,
                amount,
                e,
                exc_info=True,
            )
            raise BizException(
                code=10005,
                msg=f"强制流水写入失败（余额已变更，请人工核对：user_id={user_id} amount={amount}）",
            )
        return {
            "flow": flow,
            "account": await self.account_dao.get_by_user_id(user_id),
        }

    # ─────────────────────────────────────────────────────
    # 写：批量运营调整（调用 DAO adjust_balance_batch；单条失败不阻断整体）
    # ─────────────────────────────────────────────────────

    async def operate_batch_adjust_balance(
        self, adjustments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """批量余额调整（逐单独立事务；单条失败记录结果；不写流水，仅变动余额）

        调用方如有流水需求，需逐单自行调用 operate_flow_and_balance_atomic。
        """
        # 前置金额校验：每条 amount 绝对值 ≤ MAX_OPERATE_AMOUNT
        for idx, adj in enumerate(adjustments):
            for k in (
                "delta_available",
                "delta_frozen",
                "delta_total",
                "delta_withdrawn",
                "delta_fee",
            ):
                if k in adj:
                    val = Decimal(str(adj[k]))
                    if abs(val) > MAX_OPERATE_AMOUNT:
                        raise BizException(
                            code=10004,
                            msg=f"第 {idx} 条 {k}={val} 超过单笔下限 {MAX_OPERATE_AMOUNT}",
                        )
        return await self.account_dao.adjust_balance_batch(adjustments)

    # ─────────────────────────────────────────────────────
    # 内部 helper
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _validate_positive_amount(amount: Any, label: str) -> Decimal:
        """校验金额为正 Decimal，且 ≤ MAX_OPERATE_AMOUNT"""
        try:
            value = Decimal(str(amount))
        except Exception:
            raise BizException(code=10004, msg=f"{label} 非合法 Decimal：{amount}")
        if value <= Decimal("0"):
            raise BizException(code=10004, msg=f"{label} 必须为正：{value}")
        if value > MAX_OPERATE_AMOUNT:
            raise BizException(
                code=10004,
                msg=f"{label} 超过单笔下限 {MAX_OPERATE_AMOUNT}：{value}",
            )
        # 强制保留 2 位小数（不四舍五入，超 2 位直接拒绝）
        if value.as_tuple().exponent < -2:
            raise BizException(
                code=10004,
                msg=f"{label} 最多 2 位小数：{value}",
            )
        return value
