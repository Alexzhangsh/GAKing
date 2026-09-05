# @ai-generated
"""
提现后置审批编排 Service（B11 新建）

职责：
1. 包装 B09 WithdrawService 的审批方法，增加审批幂等防重复操作
2. 审核通过后可选触发 B10 微信批量打款（自动转账模式）
3. 每次状态变更记录状态流转日志（WithdrawReviewLog）
4. 后台分页查询 + 导出条件过滤 + 审批历史查询
5. 状态机严格约束：PENDING→APPROVED→PROCESSING→SUCCESS/REJECTED，驳回终态不可二次操作

设计要点：
1. 不修改 B01-B10 基线代码，通过依赖注入包装 WithdrawService
2. 审批幂等：Redis SETNX gaking:prod:lock:review:{apply_id}:{action}，TTL=30s
3. B10 打款可选：传入 wechat_pay_service 时自动转账，否则仅标记 APPROVED（手动打款模式）
4. 状态流转日志在每次操作后异步记录（失败不阻断主流程，仅记 warning）
5. 异常统一抛 ValueError（与 B09 风格一致），由 API 层转 BizException

状态机流转图：
  PENDING ──approve──→ APPROVED ──transfer──→ PROCESSING ──success──→ SUCCESS
     │                    │                      │
     └──reject──→ REJECTED ←──transfer_fail──────┘
                   (终态)

约束：严禁修改 B01-B10 任何基线代码，全部新建独立文件
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.common.lock_util import LockUtil
from src.common.mock_user_util import (
    gen_mock_transfer_batch_id,
    is_mock_openid,
    should_simulate_transfer,
)
from src.common.redis_client import RedisClient
from src.config.constants import LockTimeout, WithdrawStatus
from src.dao.withdraw_review_log_dao import WithdrawReviewLogDAO
from src.models.business.withdraw_review_log_model import WithdrawReviewLog
from src.services.withdraw_service import WithdrawService

logger = logging.getLogger("service.withdraw_review")

# 审批操作类型常量
ACTION_APPROVE = "APPROVE"
ACTION_REJECT = "REJECT"
ACTION_TRANSFER = "TRANSFER"
ACTION_TRANSFER_SUCCESS = "TRANSFER_SUCCESS"
ACTION_TRANSFER_FAIL = "TRANSFER_FAIL"

# 审批幂等锁前缀（裸 key，LockUtil 内部补 LOCK_PREFIX）
LOCK_KEY_REVIEW = "review:"

# 审批幂等锁 TTL（秒）：30s 防止管理员重复点击
REVIEW_LOCK_TIMEOUT = 30


class WithdrawReviewService:
    """提现后置审批编排 Service

    通过构造函数注入 B09 WithdrawService + 日志 DAO + 可选 B10 微信支付服务
    所有审批操作先加幂等锁，再调用 B09 方法，最后记录状态流转日志
    """

    def __init__(
        self,
        withdraw_service: WithdrawService,
        review_log_dao: WithdrawReviewLogDAO,
        wechat_pay_service: Optional[Any] = None,
    ) -> None:
        """初始化审批编排服务

        Args:
            withdraw_service: B09 提现服务（含 approve/reject/complete/fail 方法）
            review_log_dao: 审批日志 DAO
            wechat_pay_service: B10 微信支付转账服务（None 则手动打款模式）
        """
        self.withdraw_service = withdraw_service
        self.review_log_dao = review_log_dao
        self.wechat_pay_service = wechat_pay_service

    # ══════════════════════════════════════════════════════
    # 1. 审核通过 + 可选触发微信打款
    # ══════════════════════════════════════════════════════

    async def approve_and_transfer(
        self,
        apply_id: int,
        review_user_id: int,
        review_remark: str,
        *,
        openid: Optional[str] = None,
        auto_transfer: bool = False,
    ) -> Dict[str, Any]:
        """审核通过 + 可选触发微信打款

        流程：
        1. 审批幂等锁（SETNX，防重复点击）
        2. 调用 B09 approve_apply（PENDING → APPROVED）
        3. 记录状态流转日志（APPROVE）
        4. 若 auto_transfer=True 且 openid 不为空 → 触发 B10 微信转账
           4a. 转账成功 → 更新状态为 PROCESSING，记录 TRANSFER 日志
           4b. 转账失败 → 不回滚审核状态（已 APPROVED），记 CRITICAL 日志，人工处理

        Args:
            apply_id: 提现申请ID
            review_user_id: 审核管理员ID
            review_remark: 审核备注
            openid: 收款用户微信 openid（auto_transfer=True 时必填）
            auto_transfer: 是否自动触发微信打款（False 则仅审核通过，手动打款）
        Returns:
            {"apply": {...审核后申请详情...}, "transfer": {...转账结果...或 None}}
        Raises:
            ValueError: 幂等拦截 / 状态机校验失败 / B09 审核失败
        """
        # 1. 审批幂等锁
        await self._acquire_review_lock(apply_id, ACTION_APPROVE)

        try:
            # 2. 调用 B09 审核通过
            apply_result = await self.withdraw_service.approve_apply(
                apply_id=apply_id,
                review_user_id=review_user_id,
                review_remark=review_remark,
            )

            # 3. 记录状态流转日志
            await self._log_review(
                apply_id=apply_id,
                from_status=WithdrawStatus.PENDING.value,
                to_status=WithdrawStatus.APPROVED.value,
                action=ACTION_APPROVE,
                operator_id=review_user_id,
                remark=review_remark,
            )

            transfer_result: Optional[Dict[str, Any]] = None

            # 4. 可选触发微信打款
            if auto_transfer and openid:
                transfer_result = await self._trigger_wechat_transfer(
                    apply_id=apply_id,
                    apply_result=apply_result,
                    openid=openid,
                    operator_id=review_user_id,
                )

            logger.info(
                "[withdraw_review] 审核通过 apply_id=%s review_user_id=%s "
                "auto_transfer=%s transfer=%s",
                apply_id,
                review_user_id,
                auto_transfer,
                "success" if transfer_result else "skip",
            )
            return {"apply": apply_result, "transfer": transfer_result}

        finally:
            # 释放审批锁
            await self._release_review_lock(apply_id, ACTION_APPROVE)

    # ══════════════════════════════════════════════════════
    # 2. 审核驳回
    # ══════════════════════════════════════════════════════

    async def reject(
        self,
        apply_id: int,
        review_user_id: int,
        reject_reason: str,
    ) -> Dict[str, Any]:
        """审核驳回（PENDING → REJECTED，退回冻结余额 → 可用余额）

        流程：
        1. 审批幂等锁
        2. 调用 B09 reject_apply（PENDING → REJECTED + 退回余额）
        3. 记录状态流转日志（REJECT）

        Args:
            apply_id: 提现申请ID
            review_user_id: 审核管理员ID
            reject_reason: 驳回原因
        Returns:
            驳回后的申请详情 dict
        Raises:
            ValueError: 幂等拦截 / 状态机校验失败
        """
        await self._acquire_review_lock(apply_id, ACTION_REJECT)

        try:
            result = await self.withdraw_service.reject_apply(
                apply_id=apply_id,
                review_user_id=review_user_id,
                reject_reason=reject_reason,
            )

            await self._log_review(
                apply_id=apply_id,
                from_status=WithdrawStatus.PENDING.value,
                to_status=WithdrawStatus.REJECTED.value,
                action=ACTION_REJECT,
                operator_id=review_user_id,
                remark=reject_reason,
            )

            logger.info(
                "[withdraw_review] 驳回 apply_id=%s review_user_id=%s reason=%s",
                apply_id,
                review_user_id,
                reject_reason,
            )
            return result

        finally:
            await self._release_review_lock(apply_id, ACTION_REJECT)

    # ══════════════════════════════════════════════════════
    # 3. 微信打款成功回调
    # ══════════════════════════════════════════════════════

    async def on_transfer_success(
        self,
        apply_id: int,
        transfer_batch_id: str,
        *,
        operator_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """微信打款成功回调（APPROVED/PROCESSING → SUCCESS，释放冻结余额）

        流程：
        1. 审批幂等锁
        2. 调用 B09 complete_apply（APPROVED/PROCESSING → SUCCESS + 释放冻结）
        3. 记录状态流转日志（TRANSFER_SUCCESS）

        Args:
            apply_id: 提现申请ID
            transfer_batch_id: 微信转账批次ID
            operator_id: 操作人ID（回调场景可为空）
        Returns:
            更新后的申请详情 dict
        Raises:
            ValueError: 幂等拦截 / 状态机校验失败
        """
        await self._acquire_review_lock(apply_id, ACTION_TRANSFER_SUCCESS)

        try:
            result = await self.withdraw_service.complete_apply(
                apply_id=apply_id,
                transfer_batch_id=transfer_batch_id,
            )

            await self._log_review(
                apply_id=apply_id,
                from_status=WithdrawStatus.PROCESSING.value,
                to_status=WithdrawStatus.SUCCESS.value,
                action=ACTION_TRANSFER_SUCCESS,
                operator_id=operator_id,
                remark=f"打款成功 batch_id={transfer_batch_id}",
                transfer_batch_id=transfer_batch_id,
            )

            logger.info(
                "[withdraw_review] 打款成功 apply_id=%s batch_id=%s",
                apply_id,
                transfer_batch_id,
            )
            return result

        finally:
            await self._release_review_lock(apply_id, ACTION_TRANSFER_SUCCESS)

    # ══════════════════════════════════════════════════════
    # 4. 微信打款失败回调
    # ══════════════════════════════════════════════════════

    async def on_transfer_fail(
        self,
        apply_id: int,
        fail_reason: str,
        *,
        operator_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """微信打款失败回调（APPROVED/PROCESSING → REJECTED，退回可用余额）

        流程：
        1. 审批幂等锁
        2. 调用 B09 fail_apply（APPROVED/PROCESSING → REJECTED + 退回余额）
        3. 记录状态流转日志（TRANSFER_FAIL）

        Args:
            apply_id: 提现申请ID
            fail_reason: 失败原因
            operator_id: 操作人ID
        Returns:
            更新后的申请详情 dict
        Raises:
            ValueError: 幂等拦截 / 状态机校验失败
        """
        await self._acquire_review_lock(apply_id, ACTION_TRANSFER_FAIL)

        try:
            result = await self.withdraw_service.fail_apply(
                apply_id=apply_id,
                reason=fail_reason,
            )

            await self._log_review(
                apply_id=apply_id,
                from_status=WithdrawStatus.PROCESSING.value,
                to_status=WithdrawStatus.REJECTED.value,
                action=ACTION_TRANSFER_FAIL,
                operator_id=operator_id,
                remark=fail_reason,
            )

            logger.info(
                "[withdraw_review] 打款失败 apply_id=%s reason=%s",
                apply_id,
                fail_reason,
            )
            return result

        finally:
            await self._release_review_lock(apply_id, ACTION_TRANSFER_FAIL)

    # ══════════════════════════════════════════════════════
    # 5. 后台分页查询 + 导出条件过滤
    # ══════════════════════════════════════════════════════

    async def list_applies_with_filter(
        self,
        *,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """后台提现申请列表（增强版，支持金额/时间范围过滤）

        复用 B09 WithdrawService.list_applies_for_admin 的基础能力，
        在 Service 层对返回结果做金额/时间二次过滤（不修改 B09 DAO）

        Args:
            user_id: 平台用户ID筛选
            status: 提现状态筛选
            min_amount: 最低申请金额筛选
            max_amount: 最高申请金额筛选
            start_time: 创建时间起始
            end_time: 创建时间截止
            page: 页码
            page_size: 每页条数
        Returns:
            {"list": [...], "total": int, "page": int, "page_size": int}
        """
        # 复用 B09 基础查询（user_id + status 筛选已下沉到 DAO）
        result = await self.withdraw_service.list_applies_for_admin(
            user_id=user_id, status=status, page=page, page_size=page_size
        )

        # Service 层二次过滤（金额范围 + 时间范围）
        # 注意：这是内存过滤，仅对当前页数据生效；大数据量导出应走专用导出接口
        if (
            min_amount is not None
            or max_amount is not None
            or start_time is not None
            or end_time is not None
        ):
            filtered_list = []
            for item in result.get("list", []):
                # 金额过滤
                amount = Decimal(str(item.get("apply_amount", 0)))
                if min_amount is not None and amount < min_amount:
                    continue
                if max_amount is not None and amount > max_amount:
                    continue
                # 时间过滤
                create_time_str = item.get("create_time", "")
                if start_time is not None and create_time_str:
                    try:
                        item_time = datetime.strptime(
                            create_time_str, "%Y-%m-%d %H:%M:%S"
                        )
                        if item_time < start_time:
                            continue
                    except ValueError:
                        pass
                if end_time is not None and create_time_str:
                    try:
                        item_time = datetime.strptime(
                            create_time_str, "%Y-%m-%d %H:%M:%S"
                        )
                        if item_time >= end_time:
                            continue
                    except ValueError:
                        pass
                filtered_list.append(item)
            result["list"] = filtered_list
            result["total"] = len(filtered_list)

        return result

    async def get_review_logs(
        self,
        apply_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """查询提现申请的审批操作历史

        Args:
            apply_id: 提现申请ID
            page: 页码
            page_size: 每页条数
        Returns:
            {"list": [...], "total": int, "page": int, "page_size": int}
        """
        items, total = await self.review_log_dao.list_by_apply_id(
            apply_id, page=page, page_size=page_size
        )
        return {
            "list": [it.to_dict() for it in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def list_review_logs_with_filters(
        self,
        *,
        apply_id: Optional[int] = None,
        action: Optional[str] = None,
        operator_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """多条件分页查询审批日志（后台审计/导出用）

        Args:
            apply_id: 提现申请ID筛选
            action: 操作类型筛选
            operator_id: 操作人ID筛选
            start_time: 创建时间起始
            end_time: 创建时间截止
            page: 页码
            page_size: 每页条数
        Returns:
            {"list": [...], "total": int, "page": int, "page_size": int}
        """
        items, total = await self.review_log_dao.list_with_filters(
            apply_id=apply_id,
            action=action,
            operator_id=operator_id,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )
        return {
            "list": [it.to_dict() for it in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ══════════════════════════════════════════════════════
    # 内部方法
    # ══════════════════════════════════════════════════════

    async def _acquire_review_lock(self, apply_id: int, action: str) -> None:
        """获取审批幂等锁（Redis SETNX，防重复操作）

        锁 key：gaking:prod:lock:review:{apply_id}:{action}
        TTL：30s（覆盖管理员双击/网络重试场景）

        Args:
            apply_id: 提现申请ID
            action: 操作类型
        Raises:
            ValueError: 锁已被占用（操作正在处理中）
        """
        lock_key = f"{LOCK_KEY_REVIEW}{apply_id}:{action}"
        lock_owner = await LockUtil.acquire_lock(lock_key, timeout=REVIEW_LOCK_TIMEOUT)
        if lock_owner is None:
            raise ValueError(
                f"该提现申请正在{action}处理中，请勿重复操作: apply_id={apply_id}"
            )
        # 将 lock_owner 存到实例属性，供 release 使用
        # 注意：同一实例同一时刻只处理一个请求（FastAPI Depends 每请求新建实例）
        self._current_lock_owner = lock_owner
        self._current_lock_key = lock_key

    async def _release_review_lock(self, apply_id: int, action: str) -> None:
        """释放审批幂等锁"""
        lock_key = f"{LOCK_KEY_REVIEW}{apply_id}:{action}"
        lock_owner = getattr(self, "_current_lock_owner", None)
        if lock_owner:
            await LockUtil.release_lock(lock_key, lock_owner)
            self._current_lock_owner = None
            self._current_lock_key = None

    async def _trigger_wechat_transfer(
        self,
        apply_id: int,
        apply_result: Dict[str, Any],
        openid: str,
        operator_id: int,
    ) -> Optional[Dict[str, Any]]:
        """触发 B10 微信转账

        从审核通过的申请详情中提取金额/单号，调用 B10 transfer_single
        转账成功 → 更新状态为 PROCESSING + 记录 TRANSFER 日志
        转账失败 → 不回滚审核状态（已 APPROVED），记 CRITICAL 日志，人工处理

        Args:
            apply_id: 提现申请ID
            apply_result: B09 approve_apply 返回的申请详情
            openid: 收款用户微信 openid
            operator_id: 操作人ID
        Returns:
            转账结果 dict 或 None（转账服务不可用时）
        """
        if self.wechat_pay_service is None:
            logger.info(
                "[withdraw_review] 未注入微信支付服务，跳过自动打款 apply_id=%s",
                apply_id,
            )
            return None

        # 从申请详情提取转账参数
        out_batch_no = apply_result.get("apply_no", str(apply_id))
        out_detail_no = f"{out_batch_no}D1"
        amount = Decimal(str(apply_result.get("apply_amount", 0)))

        # X01-1 边界：mock 用户（dev_ 前缀 openid）一律不得调用真实微信转账接口。
        # - 非生产环境：模拟打款成功，打通全流程自测（避免用假 openid 调真实接口）
        # - 生产环境：mock openid 属异常数据，不模拟也不调真实接口，转人工打款处理
        if is_mock_openid(openid):
            if not should_simulate_transfer(openid):
                logger.critical(
                    "[withdraw_review] 生产环境 mock 用户提现，禁止自动打款，转人工处理"
                    " apply_id=%s openid=%s",
                    apply_id,
                    openid[:12] + "***",
                )
                return None
            batch_id = gen_mock_transfer_batch_id(out_batch_no)
            transfer_result = {
                "batch_id": batch_id,
                "out_batch_no": out_batch_no,
                "mock": True,
                "create_time": datetime.now().isoformat(),
            }
            await self._log_review(
                apply_id=apply_id,
                from_status=WithdrawStatus.APPROVED.value,
                to_status=WithdrawStatus.PROCESSING.value,
                action=ACTION_TRANSFER,
                operator_id=operator_id,
                remark=f"模拟微信转账成功（mock 用户）batch_id={batch_id}",
                transfer_batch_id=batch_id,
            )
            logger.info(
                "[withdraw_review] mock 用户模拟打款 apply_id=%s batch_id=%s",
                apply_id,
                batch_id,
            )
            return transfer_result

        try:
            # 调用 B10 微信转账
            transfer_result = await self.wechat_pay_service.transfer_single(
                out_batch_no=out_batch_no,
                out_detail_no=out_detail_no,
                transfer_amount=amount,
                openid=openid,
                transfer_remark="佣金提现",
            )

            batch_id = transfer_result.get("batch_id", "")

            # 记录 TRANSFER 日志
            await self._log_review(
                apply_id=apply_id,
                from_status=WithdrawStatus.APPROVED.value,
                to_status=WithdrawStatus.PROCESSING.value,
                action=ACTION_TRANSFER,
                operator_id=operator_id,
                remark=f"发起微信转账 batch_id={batch_id}",
                transfer_batch_id=batch_id,
            )

            logger.info(
                "[withdraw_review] 微信转账已发起 apply_id=%s batch_id=%s",
                apply_id,
                batch_id,
            )
            return transfer_result

        except Exception as e:
            # 转账失败不回滚审核状态（已 APPROVED），记 CRITICAL 日志
            logger.critical(
                "[withdraw_review] 微信转账失败（审核已通过，需人工打款）"
                " apply_id=%s openid=%s: %s",
                apply_id,
                openid[:6] + "***" if openid else "None",
                e,
                exc_info=True,
            )
            # 记录失败日志
            await self._log_review(
                apply_id=apply_id,
                from_status=WithdrawStatus.APPROVED.value,
                to_status=WithdrawStatus.APPROVED.value,
                action=ACTION_TRANSFER,
                operator_id=operator_id,
                remark=f"微信转账失败: {e}",
            )
            return None

    async def _log_review(
        self,
        apply_id: int,
        from_status: str,
        to_status: str,
        action: str,
        operator_id: Optional[int] = None,
        remark: str = "",
        transfer_batch_id: str = "",
    ) -> None:
        """记录状态流转日志（失败不阻断主流程）

        Args:
            apply_id: 提现申请ID
            from_status: 变更前状态
            to_status: 变更后状态
            action: 操作类型
            operator_id: 操作人ID
            remark: 操作备注
            transfer_batch_id: 微信转账批次ID
        """
        try:
            log_data = {
                "apply_id": apply_id,
                "from_status": from_status,
                "to_status": to_status,
                "action": action,
                "operator_id": operator_id,
                "remark": remark,
                "transfer_batch_id": transfer_batch_id,
            }
            await self.review_log_dao.create(log_data)
            logger.debug(
                "[withdraw_review] 状态流转日志 apply_id=%s %s→%s action=%s",
                apply_id,
                from_status,
                to_status,
                action,
            )
        except Exception as e:
            # 日志记录失败不阻断主流程，仅记 warning
            logger.warning(
                "[withdraw_review] 状态流转日志记录失败 apply_id=%s action=%s: %s",
                apply_id,
                action,
                e,
                exc_info=True,
            )
