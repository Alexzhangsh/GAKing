# @ai-generated
"""
用户提现业务服务层
职责：提现 4 核心流程（发起扣余额 / 驳回退回余额 / 审核通过 / 标记打款完成）+ 账户/记录查询

设计约定：
1. 金额统一 Decimal 精确计算，禁止 float；手续费 max(amount×0.1%, 1元)。
2. 余额变动全部数据库事务包裹（DAO 内 FOR UPDATE + commit）；commit 后失效 Redis 缓存。
3. 幂等防重复提交：用户级分布式锁 + SETNX 5s 间隔键（吸收双击）。
4. 状态机校验在 Service 层；DAO 仅数据存取。
5. 余额变动与申请状态变更分两次 DAO commit（与现有 BaseDAO 单方法 commit 模式一致）；
   审核流程采用「状态优先」策略（先更新状态再调余额），失败记 CRITICAL 日志便于人工对账，
   避免重试导致重复扣/退余额（重试时状态已推进，状态校验拦截）。
6. 不改动 BaseDAO 事务代码、不改动现有定时任务与 Redis 缓存逻辑。

远期需求埋点备注（本期不实现，仅注释不编码）：
- TODO(远期-V2.1): 20% 佣金保证金冻结 + 订单结算 30 天冷静期自动释放。
  本 Service（提现主流程）仅消费 available_balance 作为可提现资金来源，保证金冻结/释放
  不在提现流程内实现，而在「佣金结算入账」与「保证金释放定时任务」中完成：
    a. 对账入账（UserCommissionAccountDAO.credit_on_reconciliation）按 20% 冻结至
       margin_balance，仅 80% 计入 available_balance；
    b. 独立定时任务扫描结算满 30 天的保证金，释放 margin_balance → available_balance；
    c. 上线后提现可用余额校验保持「仅看 available_balance」不变，保证金冻结期间自然不可提现。
  详见 user_commission_account_model.py 的远期字段埋点注释。
"""
import logging
import random
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.common.lock_util import LockUtil
from src.common.pay_config_util import PayConfigUtil, WithdrawFeeConfig
from src.common.redis_client import RedisClient
from src.common.withdraw_rule_validator import WithdrawRuleValidator
from src.config.constants import (
    IDEMPOTENT_KEY_WITHDRAW_SUBMIT,
    LOCK_KEY_WITHDRAW_APPLY,
    LOCK_KEY_WITHDRAW_USER,
    LockTimeout,
    WITHDRAW_FEE_QUANTIZE,
    WITHDRAW_MIN_AMOUNT,
    WITHDRAW_SUBMIT_INTERVAL,
    WithdrawStatus,
)
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.dao.user_withdraw_apply_dao import UserWithdrawApplyDAO

logger = logging.getLogger("service.withdraw")

# 金额为零的 Decimal 常量
_ZERO = Decimal("0.00")


class WithdrawService:
    """用户提现业务服务

    通过构造函数注入 UserCommissionAccountDAO / UserWithdrawApplyDAO
    （二者共享同一 AsyncSession，由 API 层 Depends 注入）
    """

    def __init__(
        self,
        account_dao: UserCommissionAccountDAO,
        apply_dao: UserWithdrawApplyDAO,
    ):
        self.account_dao = account_dao
        self.apply_dao = apply_dao

    # ── 内部工具方法 ────────────────────────────────────

    @staticmethod
    def _to_decimal(amount: Any) -> Decimal:
        """统一转 Decimal，避免 float 精度污染"""
        return Decimal(str(amount))

    def _calc_fee(self, amount: Decimal, cfg: WithdrawFeeConfig) -> Decimal:
        """计算手续费：max(amount × rate, min_fee)，quantize 2 位

        费率/最低手续费来自动态配置（PayConfigUtil 读取 gaking_pay_config，兜底 constants 常量）。
        公式来源：V2.0 分润规则定稿 + 用户确认（单笔最低 1 元）。
        """
        fee = (amount * cfg.rate).quantize(WITHDRAW_FEE_QUANTIZE)
        if fee < cfg.min_fee:
            fee = cfg.min_fee
        return fee

    @staticmethod
    def _gen_apply_no() -> str:
        """生成提现单号：GAKW + yyyyMMddHHmmss + 6 位随机数字，全局唯一"""
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        rand = "".join([str(random.randint(0, 9)) for _ in range(6)])
        return f"GAKW{ts}{rand}"

    @staticmethod
    def _apply_lock_key(apply_id: int) -> str:
        """提现申请级分布式锁 key（裸 key，LockUtil 内部补 LOCK_PREFIX）

        实际 Redis key：gaking:prod:lock:withdraw_apply:{apply_id}
        """
        return f"{LOCK_KEY_WITHDRAW_APPLY}{apply_id}"

    # ── 流程1：发起提现扣余额 ───────────────────────────

    async def apply_withdraw(
        self,
        user_id: int,
        apply_amount: Decimal,
    ) -> Dict[str, Any]:
        """发起提现申请（扣减可用余额 → 冻结余额，生成 PENDING 申请）

        业务规则：
        1. 幂等防重复：SETNX withdraw_submit:{user_id} TTL=5s，已存在→拒绝"操作过于频繁"
        2. 用户级分布式锁 lock:withdraw:{user_id}（防并发余额竞争）
        3. 校验 apply_amount >= WITHDRAW_MIN_AMOUNT(10 元，暂不动态化)
        4. 手续费 fee = max(apply_amount × rate, min_fee)（rate/min_fee 动态读取
           gaking_pay_config，PayConfigUtil 兜底 constants 常量）；actual_amount = apply_amount - fee
        5. account_dao.adjust_balance(available-=apply_amount, frozen+=apply_amount)
           （内部 FOR UPDATE + 透支校验 + commit + 失效缓存；余额不足抛 ValueError）
        6. apply_dao.create(status=PENDING)
        7. 返回申请详情

        Args:
            user_id: 平台用户ID
            apply_amount: 申请提现金额(元)
        Returns:
            提现申请详情 dict
        Raises:
            ValueError: 操作过于频繁 / 低于门槛 / 余额不足 / 账户不存在
        """
        amount = self._to_decimal(apply_amount)

        # 1. 幂等防重复提交（5s 间隔键吸收双击/快速重复提交）
        idem_key = f"{IDEMPOTENT_KEY_WITHDRAW_SUBMIT}{user_id}"
        acquired = await RedisClient.setnx(idem_key, "1")
        if not acquired:
            raise ValueError("操作过于频繁，请稍后再试")
        await RedisClient.expire(idem_key, WITHDRAW_SUBMIT_INTERVAL)

        # 2. 门槛校验（保留原有快速校验，规则校验器内也会校验但此处提前拦截减少后续开销）
        if amount < WITHDRAW_MIN_AMOUNT:
            raise ValueError(f"最低提现金额 {WITHDRAW_MIN_AMOUNT} 元")

        # 3. 用户级分布式锁
        lock_owner = await LockUtil.acquire_lock(
            f"{LOCK_KEY_WITHDRAW_USER}{user_id}", timeout=LockTimeout.NORMAL
        )
        if lock_owner is None:
            raise ValueError("当前有提现操作正在处理，请稍后再试")

        try:
            # B09 增强：注入规则校验器（最低金额+单日限额+冻结足额+阶梯手续费计算）
            # 替换原 _calc_fee 单一费率计算，校验失败抛 ValueError（与原风格一致）
            validator = WithdrawRuleValidator(self.account_dao, self.apply_dao)
            fee, tier_label = await validator.validate_all(user_id, amount)
            actual_amount = (amount - fee).quantize(WITHDRAW_FEE_QUANTIZE)
            apply_no = self._gen_apply_no()

            # 4. 扣减可用余额、增加冻结余额（FOR UPDATE + 透支校验 + commit + 失效缓存）
            await self.account_dao.adjust_balance(
                user_id,
                delta_available=-amount,
                delta_frozen=amount,
            )

            # 5. 创建提现申请（PENDING）
            apply_data = {
                "apply_no": apply_no,
                "user_id": user_id,
                "apply_amount": amount,
                "fee": fee,
                "actual_amount": actual_amount,
                "status": WithdrawStatus.PENDING.value,
                "remark": "",
            }
            try:
                apply_record = await self.apply_dao.create(apply_data)
            except Exception as create_err:
                # 余额已扣减但申请记录创建失败：记 CRITICAL 日志便于人工对账
                logger.critical(
                    "[withdraw] 提现申请创建失败但余额已扣减 user_id=%s apply_no=%s amount=%s fee=%s: %s",
                    user_id,
                    apply_no,
                    amount,
                    fee,
                    create_err,
                    exc_info=True,
                )
                raise

            # B09：提现申请成功后失效单日累计缓存（确保下次校验查最新值）
            await WithdrawRuleValidator.invalidate_daily_used_cache(user_id)

            logger.info(
                "[withdraw] 发起提现成功 user_id=%s apply_no=%s amount=%s fee=%s actual=%s tier=%s",
                user_id,
                apply_no,
                amount,
                fee,
                actual_amount,
                tier_label,
            )
            return apply_record.to_dict()
        finally:
            await LockUtil.release_lock(
                f"{LOCK_KEY_WITHDRAW_USER}{user_id}", lock_owner
            )

    # ── 流程2：驳回退回余额 ─────────────────────────────

    async def reject_apply(
        self,
        apply_id: int,
        review_user_id: int,
        reject_reason: str,
    ) -> Dict[str, Any]:
        """驳回提现申请（退回冻结余额 → 可用余额，状态 PENDING → REJECTED）

        采用「状态优先」策略：先更新状态为 REJECTED，再退回余额。
        若退回余额失败，状态已为 REJECTED，重试时状态校验拦截，避免重复退回；
        失败记 CRITICAL 日志便于人工对账（余额未退回，需人工补退）。

        Args:
            apply_id: 提现申请ID
            review_user_id: 审核人（后台管理员）ID
            reject_reason: 驳回原因
        Returns:
            更新后的申请详情 dict
        Raises:
            ValueError: 申请不存在 / 状态非 PENDING
        """
        lock_key = self._apply_lock_key(apply_id)
        lock_owner = await LockUtil.acquire_lock(lock_key, timeout=LockTimeout.NORMAL)
        if lock_owner is None:
            raise ValueError("该提现申请正在处理中，请稍后再试")

        try:
            apply_record = await self.apply_dao.get_by_id(apply_id)
            if apply_record is None:
                raise ValueError(f"提现申请不存在: apply_id={apply_id}")
            if apply_record.status != WithdrawStatus.PENDING.value:
                raise ValueError(
                    f"提现申请状态不允许驳回: apply_id={apply_id}, 当前状态={apply_record.status}"
                )

            amount = self._to_decimal(apply_record.apply_amount)

            # 状态优先：先置 REJECTED
            updated = await self.apply_dao.update_by_id(
                apply_id,
                {
                    "status": WithdrawStatus.REJECTED.value,
                    "review_user_id": review_user_id,
                    "review_time": datetime.now(),
                    "reject_reason": reject_reason,
                },
            )

            # 退回余额：frozen -= amount, available += amount
            try:
                await self.account_dao.adjust_balance(
                    apply_record.user_id,
                    delta_available=amount,
                    delta_frozen=-amount,
                )
            except Exception as bal_err:
                logger.critical(
                    "[withdraw] 驳回退回余额失败（状态已置 REJECTED，需人工补退）"
                    " apply_id=%s user_id=%s amount=%s: %s",
                    apply_id,
                    apply_record.user_id,
                    amount,
                    bal_err,
                    exc_info=True,
                )
                raise

            logger.info(
                "[withdraw] 驳回提现成功 apply_id=%s user_id=%s amount=%s reason=%s",
                apply_id,
                apply_record.user_id,
                amount,
                reject_reason,
            )
            return updated.to_dict() if updated is not None else apply_record.to_dict()
        finally:
            await LockUtil.release_lock(lock_key, lock_owner)

    # ── 流程3：审核通过 ─────────────────────────────────

    async def approve_apply(
        self,
        apply_id: int,
        review_user_id: int,
        review_remark: str,
    ) -> Dict[str, Any]:
        """审核通过（状态 PENDING → APPROVED，不动余额，资金仍冻结）

        Args:
            apply_id: 提现申请ID
            review_user_id: 审核人ID
            review_remark: 审核备注
        Returns:
            更新后的申请详情 dict
        Raises:
            ValueError: 申请不存在 / 状态非 PENDING
        """
        lock_key = self._apply_lock_key(apply_id)
        lock_owner = await LockUtil.acquire_lock(lock_key, timeout=LockTimeout.NORMAL)
        if lock_owner is None:
            raise ValueError("该提现申请正在处理中，请稍后再试")

        try:
            apply_record = await self.apply_dao.get_by_id(apply_id)
            if apply_record is None:
                raise ValueError(f"提现申请不存在: apply_id={apply_id}")
            if apply_record.status != WithdrawStatus.PENDING.value:
                raise ValueError(
                    f"提现申请状态不允许审核通过: apply_id={apply_id}, 当前状态={apply_record.status}"
                )

            updated = await self.apply_dao.update_by_id(
                apply_id,
                {
                    "status": WithdrawStatus.APPROVED.value,
                    "review_user_id": review_user_id,
                    "review_remark": review_remark,
                    "review_time": datetime.now(),
                },
            )

            logger.info(
                "[withdraw] 审核通过 apply_id=%s user_id=%s review_user_id=%s",
                apply_id,
                apply_record.user_id,
                review_user_id,
            )
            return updated.to_dict() if updated is not None else apply_record.to_dict()
        finally:
            await LockUtil.release_lock(lock_key, lock_owner)

    # ── 流程4：标记打款完成 ─────────────────────────────

    async def complete_apply(
        self,
        apply_id: int,
        transfer_batch_id: str,
    ) -> Dict[str, Any]:
        """标记打款完成（释放冻结余额，状态 APPROVED/PROCESSING → SUCCESS）

        余额联动：frozen -= apply_amount, cumulative_withdrawn += actual_amount,
                  cumulative_fee += fee（资金已通过微信商家转账转出）
        采用「状态优先」策略：先置 SUCCESS，再释放冻结；失败记 CRITICAL 日志。

        Args:
            apply_id: 提现申请ID
            transfer_batch_id: 微信转账批次ID
        Returns:
            更新后的申请详情 dict
        Raises:
            ValueError: 申请不存在 / 状态非 APPROVED/PROCESSING
        """
        lock_key = self._apply_lock_key(apply_id)
        lock_owner = await LockUtil.acquire_lock(lock_key, timeout=LockTimeout.NORMAL)
        if lock_owner is None:
            raise ValueError("该提现申请正在处理中，请稍后再试")

        try:
            apply_record = await self.apply_dao.get_by_id(apply_id)
            if apply_record is None:
                raise ValueError(f"提现申请不存在: apply_id={apply_id}")
            allowed = {WithdrawStatus.APPROVED.value, WithdrawStatus.PROCESSING.value}
            if apply_record.status not in allowed:
                raise ValueError(
                    f"提现申请状态不允许标记打款完成: apply_id={apply_id}, 当前状态={apply_record.status}"
                )

            amount = self._to_decimal(apply_record.apply_amount)
            actual = self._to_decimal(apply_record.actual_amount)
            fee = self._to_decimal(apply_record.fee)

            # 状态优先：先置 SUCCESS
            updated = await self.apply_dao.update_by_id(
                apply_id,
                {
                    "status": WithdrawStatus.SUCCESS.value,
                    "transfer_batch_id": transfer_batch_id,
                    "transfer_time": datetime.now(),
                },
            )

            # 释放冻结：frozen -= amount, cumulative_withdrawn += actual, cumulative_fee += fee
            try:
                await self.account_dao.adjust_balance(
                    apply_record.user_id,
                    delta_frozen=-amount,
                    delta_withdrawn=actual,
                    delta_fee=fee,
                )
            except Exception as bal_err:
                logger.critical(
                    "[withdraw] 打款完成释放冻结失败（状态已置 SUCCESS，需人工补释放）"
                    " apply_id=%s user_id=%s amount=%s: %s",
                    apply_id,
                    apply_record.user_id,
                    amount,
                    bal_err,
                    exc_info=True,
                )
                raise

            logger.info(
                "[withdraw] 打款完成 apply_id=%s user_id=%s amount=%s actual=%s fee=%s batch=%s",
                apply_id,
                apply_record.user_id,
                amount,
                actual,
                fee,
                transfer_batch_id,
            )
            return updated.to_dict() if updated is not None else apply_record.to_dict()
        finally:
            await LockUtil.release_lock(lock_key, lock_owner)

    async def fail_apply(
        self,
        apply_id: int,
        reason: str,
    ) -> Dict[str, Any]:
        """打款失败（退回可用余额，状态 APPROVED/PROCESSING → REJECTED）

        场景：微信转账失败 / 银行卡异常，资金退回可用余额（V2.0：银行卡异常时资金退回可用余额）。
        余额联动：frozen -= apply_amount, available += apply_amount。
        采用「状态优先」策略：先置 REJECTED，再退回余额；失败记 CRITICAL 日志。

        Args:
            apply_id: 提现申请ID
            reason: 失败原因
        Returns:
            更新后的申请详情 dict
        Raises:
            ValueError: 申请不存在 / 状态非 APPROVED/PROCESSING
        """
        lock_key = self._apply_lock_key(apply_id)
        lock_owner = await LockUtil.acquire_lock(lock_key, timeout=LockTimeout.NORMAL)
        if lock_owner is None:
            raise ValueError("该提现申请正在处理中，请稍后再试")

        try:
            apply_record = await self.apply_dao.get_by_id(apply_id)
            if apply_record is None:
                raise ValueError(f"提现申请不存在: apply_id={apply_id}")
            allowed = {WithdrawStatus.APPROVED.value, WithdrawStatus.PROCESSING.value}
            if apply_record.status not in allowed:
                raise ValueError(
                    f"提现申请状态不允许标记打款失败: apply_id={apply_id}, 当前状态={apply_record.status}"
                )

            amount = self._to_decimal(apply_record.apply_amount)

            updated = await self.apply_dao.update_by_id(
                apply_id,
                {
                    "status": WithdrawStatus.REJECTED.value,
                    "reject_reason": reason,
                    "transfer_time": datetime.now(),
                },
            )

            try:
                await self.account_dao.adjust_balance(
                    apply_record.user_id,
                    delta_available=amount,
                    delta_frozen=-amount,
                )
            except Exception as bal_err:
                logger.critical(
                    "[withdraw] 打款失败退回余额失败（状态已置 REJECTED，需人工补退）"
                    " apply_id=%s user_id=%s amount=%s: %s",
                    apply_id,
                    apply_record.user_id,
                    amount,
                    bal_err,
                    exc_info=True,
                )
                raise

            logger.info(
                "[withdraw] 打款失败退回 apply_id=%s user_id=%s amount=%s reason=%s",
                apply_id,
                apply_record.user_id,
                amount,
                reason,
            )
            return updated.to_dict() if updated is not None else apply_record.to_dict()
        finally:
            await LockUtil.release_lock(lock_key, lock_owner)

    # ── 查询接口 ────────────────────────────────────────

    async def get_account(self, user_id: int) -> Dict[str, Any]:
        """查询用户佣金账户余额（走读穿缓存）

        账户不存在时返回零余额占位结构，便于前端统一渲染。

        Args:
            user_id: 平台用户ID
        Returns:
            账户详情 dict（含 available/frozen/total/cumulative_withdrawn/cumulative_fee）
        """
        account = await self.account_dao.get_account_cached(user_id)
        if account is not None:
            return account
        # 账户不存在：返回零余额占位
        return {
            "user_id": user_id,
            "total_balance": 0.0,
            "available_balance": 0.0,
            "frozen_balance": 0.0,
            "cumulative_withdrawn": 0.0,
            "cumulative_fee": 0.0,
            "last_settle_date": None,
            "version": 0,
        }

    async def list_my_applies(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """查询我的提现记录（分页）

        Args:
            user_id: 平台用户ID
            page: 页码
            page_size: 每页条数
        Returns:
            {"list": [...], "total": int, "page": int, "page_size": int}
        """
        items, total = await self.apply_dao.list_by_user_id(user_id, page, page_size)
        return {
            "list": [it.to_dict() for it in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def list_applies_for_admin(
        self,
        *,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """后台提现申请列表（多条件筛选）

        Args:
            user_id: 平台用户ID筛选（可选）
            status: 提现状态筛选（可选）
            page: 页码
            page_size: 每页条数
        Returns:
            {"list": [...], "total": int, "page": int, "page_size": int}
        """
        items, total = await self.apply_dao.list_with_filters(
            user_id=user_id, status=status, page=page, page_size=page_size
        )
        return {
            "list": [it.to_dict() for it in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_apply_detail(self, apply_id: int) -> Dict[str, Any]:
        """查询单条提现申请详情

        Args:
            apply_id: 提现申请ID
        Returns:
            申请详情 dict
        Raises:
            ValueError: 申请不存在
        """
        apply_record = await self.apply_dao.get_by_id(apply_id)
        if apply_record is None:
            raise ValueError(f"提现申请不存在: apply_id={apply_id}")
        return apply_record.to_dict()
