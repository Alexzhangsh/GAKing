# @ai-generated
"""
用户提现后台审核接口层（后台 4 个核心审核接口 + 1 个打款失败补充接口）
路由前缀：/api/v1/admin/withdraw
职责：管理员身份识别 → 参数校验 → 调用 WithdrawService → 统一响应封装
不包含任何业务逻辑，业务规则（状态机/余额联动/手续费）全部在 Service 层

接口清单（4 核心审核接口）：
1. GET /api/v1/admin/withdraw/applies                       后台提现申请列表（审核工作台）
2. PUT /api/v1/admin/withdraw/applies/{apply_id}/approve    审核通过（流程3：PENDING → APPROVED）
3. PUT /api/v1/admin/withdraw/applies/{apply_id}/reject     驳回（流程2：PENDING → REJECTED，退回余额）
4. PUT /api/v1/admin/withdraw/applies/{apply_id}/complete   标记打款完成（流程4：APPROVED/PROCESSING → SUCCESS，释放冻结）

补充接口（V2.0 银行卡异常退回可用余额场景）：
5. PUT /api/v1/admin/withdraw/applies/{apply_id}/fail       打款失败退回（APPROVED/PROCESSING → REJECTED，退回可用余额）

身份识别：
- 强制 JWT（Authorization: Bearer <token>）+ RBAC withdraw:review 权限校验；
- require_any_permission 完成：HTTPBearer 解析 token → JWT 校验 → RbacUtil 权限校验
  （含 "*" 通配符的超管直接放行；无权限→403；缺 token→401）；
- review_user_id 从 payload.user_id 提取并落库到提现申请。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.dao.user_withdraw_apply_dao import UserWithdrawApplyDAO
from src.db.init_db import DatabaseManager
from src.schemas.withdraw import (
    WithdrawApproveRequest,
    WithdrawCompleteRequest,
    WithdrawFailRequest,
    WithdrawRejectRequest,
)
from src.services.withdraw_service import WithdrawService

logger = logging.getLogger("api.admin.withdraw_review")

router = APIRouter(prefix="/api/v1/admin/withdraw", tags=["后台-提现审核"])


# ── 依赖注入：管理员身份识别 + 数据库会话 + Service 实例 ──────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission(["withdraw:review"])),
) -> int:
    """获取后台管理员ID（强制 JWT + RBAC withdraw:review 权限校验）

    依赖 require_any_permission(["withdraw:review"]) 完成：
      1. HTTPBearer 解析 Authorization: Bearer <token>（缺失→401）
      2. JwtAuthGuard.verify_token 校验 JWT（无效/过期→401）
      3. RbacUtil.has_any_permission 校验角色权限
         （超管 permissions 含 "*" 通配符直接放行；无权限→403）
    review_user_id 从 payload.user_id 提取并落库到提现申请。
    """
    return int(payload["user_id"])


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def get_withdraw_service(db: AsyncSession = Depends(get_db)) -> WithdrawService:
    """构造 WithdrawService 实例（注入账户 DAO + 提现申请 DAO，共享同一 session）"""
    return WithdrawService(
        UserCommissionAccountDAO(db),
        UserWithdrawApplyDAO(db),
    )


# ══════════════════════════════════════════════════════
# 接口实现
# ══════════════════════════════════════════════════════


@router.get("/applies")
async def list_applies_for_admin(
    request: Request,
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数，最大100"),
    user_id: Optional[int] = Query(None, gt=0, description="平台用户ID筛选"),
    status: Optional[str] = Query(
        None,
        description="提现状态筛选：PENDING/APPROVED/PROCESSING/SUCCESS/REJECTED",
    ),
    admin_user_id: int = Depends(get_admin_user_id),
    svc: WithdrawService = Depends(get_withdraw_service),
):
    """1. 后台提现申请列表（审核工作台）

    - 支持按 user_id / status 多条件筛选，按创建时间倒序
    - 返回：{"list": [...], "total": int, "page": int, "page_size": int}
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 后台提现列表 admin=%s page=%s size=%s user_id=%s status=%s",
        request_id,
        admin_user_id,
        page,
        page_size,
        user_id,
        status,
    )
    try:
        result = await svc.list_applies_for_admin(
            user_id=user_id, status=status, page=page, page_size=page_size
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/applies/{apply_id}/approve")
async def approve_apply(
    apply_id: int,
    body: WithdrawApproveRequest,
    request: Request,
    review_user_id: int = Depends(get_admin_user_id),
    svc: WithdrawService = Depends(get_withdraw_service),
):
    """2. 审核通过（核心流程3：PENDING → APPROVED，余额仍冻结）

    - 仅 PENDING 状态可审核通过；状态机校验在 Service 层
    - 不动余额，资金仍冻结；后续由「标记打款完成」释放冻结
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 审核通过 apply_id=%s review_user_id=%s",
        request_id,
        apply_id,
        review_user_id,
    )
    try:
        result = await svc.approve_apply(
            apply_id=apply_id,
            review_user_id=review_user_id,
            review_remark=body.review_remark,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/applies/{apply_id}/reject")
async def reject_apply(
    apply_id: int,
    body: WithdrawRejectRequest,
    request: Request,
    review_user_id: int = Depends(get_admin_user_id),
    svc: WithdrawService = Depends(get_withdraw_service),
):
    """3. 驳回（核心流程2：PENDING → REJECTED，退回冻结余额 → 可用余额）

    - 仅 PENDING 状态可驳回；状态机校验在 Service 层
    - 余额联动：frozen -= apply_amount, available += apply_amount
    - reject_reason 必填，落库 reject_reason 字段（用户可见）
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 驳回提现 apply_id=%s review_user_id=%s reason=%s",
        request_id,
        apply_id,
        review_user_id,
        body.reject_reason,
    )
    try:
        result = await svc.reject_apply(
            apply_id=apply_id,
            review_user_id=review_user_id,
            reject_reason=body.reject_reason,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/applies/{apply_id}/complete")
async def complete_apply(
    apply_id: int,
    body: WithdrawCompleteRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: WithdrawService = Depends(get_withdraw_service),
):
    """4. 标记打款完成（核心流程4：APPROVED/PROCESSING → SUCCESS，释放冻结余额）

    - 仅 APPROVED/PROCESSING 状态可标记完成；状态机校验在 Service 层
    - 余额联动：frozen -= apply_amount, cumulative_withdrawn += actual_amount, cumulative_fee += fee
    - transfer_batch_id 必填（微信转账批次ID，落库留痕）
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 标记打款完成 apply_id=%s admin=%s batch=%s",
        request_id,
        apply_id,
        admin_user_id,
        body.transfer_batch_id,
    )
    try:
        result = await svc.complete_apply(
            apply_id=apply_id,
            transfer_batch_id=body.transfer_batch_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/applies/{apply_id}/fail")
async def fail_apply(
    apply_id: int,
    body: WithdrawFailRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: WithdrawService = Depends(get_withdraw_service),
):
    """5. 打款失败退回（补充：APPROVED/PROCESSING → REJECTED，退回可用余额）

    场景：微信转账失败 / 银行卡异常（V2.0：资金退回可用余额，后台留痕）。
    - 仅 APPROVED/PROCESSING 状态可标记失败；状态机校验在 Service 层
    - 余额联动：frozen -= apply_amount, available += apply_amount
    - reason 落库 reject_reason（含失败原因）
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 打款失败退回 apply_id=%s admin=%s reason=%s",
        request_id,
        apply_id,
        admin_user_id,
        body.reason,
    )
    try:
        result = await svc.fail_apply(apply_id=apply_id, reason=body.reason)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
