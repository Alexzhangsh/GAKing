# @ai-generated
"""
用户佣金提现接口层（用户端 3 接口）
路由前缀：/api/v1/withdraw
职责：身份识别 → 参数校验 → 调用 WithdrawService → 统一响应封装
不包含任何业务逻辑，业务规则（手续费/状态机/余额联动）全部在 Service 层

接口清单：
1. GET  /api/v1/withdraw/account   查询我的佣金账户余额
2. POST /api/v1/withdraw/apply     发起提现（流程1：扣可用→冻结，生成 PENDING 申请）
3. GET  /api/v1/withdraw/applies   我的提现记录（分页）

身份识别：
- 优先从 Authorization: Bearer <JWT> 提取 user_id（C 端登录落地后的正式方案）；
- JWT 缺失时回退 X-User-Id 请求头（仅开发/调试，记 warning）；
- TODO(C端登录落地后): 移除 X-User-Id 回退，强制 JWT。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import JwtAuthGuard
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.dao.user_withdraw_apply_dao import UserWithdrawApplyDAO
from src.db.init_db import DatabaseManager
from src.schemas.withdraw import WithdrawApplyRequest
from src.services.withdraw_service import WithdrawService

logger = logging.getLogger("api.withdraw")

router = APIRouter(prefix="/api/v1/withdraw", tags=["用户佣金提现"])


# ── 依赖注入：身份识别 + 数据库会话 + Service 实例 ──────────────────


async def get_current_user_id(
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> int:
    """获取当前平台用户ID

    优先 JWT（Authorization: Bearer <token>）；缺失时回退 X-User-Id 头（开发调试）。
    user_id 统一称谓：平台用户ID（不使用推广员/promoter_id）。
    """
    # 1. 尝试 JWT
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        payload = JwtAuthGuard.verify_token(token)
        if payload and "user_id" in payload:
            return int(payload["user_id"])
        raise HTTPException(status_code=401, detail="无效或过期的 token")

    # 2. 回退 X-User-Id（开发/调试，正式环境应移除）
    if x_user_id:
        try:
            uid = int(x_user_id)
            logger.warning("[auth] 开发模式回退：使用 X-User-Id=%s（未走 JWT）", uid)
            return uid
        except ValueError:
            raise HTTPException(status_code=400, detail="X-User-Id 必须为整数")

    raise HTTPException(
        status_code=401, detail="未提供身份凭证（Authorization 或 X-User-Id）"
    )


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


@router.get("/account")
async def get_my_account(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    svc: WithdrawService = Depends(get_withdraw_service),
):
    """1. 查询我的佣金账户余额

    - 走读穿缓存（gaking:prod:user_account:{user_id}，TTL 10min）
    - 账户不存在返回零余额占位结构，便于前端统一渲染
    - 返回：available(可用) / frozen(冻结) / total(累计) / cumulative_withdrawn / cumulative_fee
    """
    request_id = get_request_id(request)
    logger.info("[request_id=%s] 查询佣金账户 user_id=%s", request_id, user_id)
    try:
        result = await svc.get_account(user_id)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/apply")
async def apply_withdraw(
    body: WithdrawApplyRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    svc: WithdrawService = Depends(get_withdraw_service),
):
    """2. 发起提现申请（核心流程1：扣减可用余额 → 冻结余额）

    - 幂等防重复：5s 间隔键 + 用户级分布式锁
    - 门槛校验：apply_amount >= 10 元
    - 手续费：fee = max(apply_amount × 0.1%, 1元)；actual_amount = apply_amount - fee
    - 余额联动：available -= apply_amount, frozen += apply_amount（FOR UPDATE + 透支校验 + commit + 失效缓存）
    - 生成 PENDING 提现申请，返回申请详情
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 发起提现 user_id=%s apply_amount=%s",
        request_id,
        user_id,
        body.apply_amount,
    )
    try:
        result = await svc.apply_withdraw(
            user_id=user_id,
            apply_amount=body.apply_amount,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/applies")
async def list_my_applies(
    request: Request,
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数，最大100"),
    user_id: int = Depends(get_current_user_id),
    svc: WithdrawService = Depends(get_withdraw_service),
):
    """3. 我的提现记录（分页，按创建时间倒序）

    - 仅查询当前 user_id 的申请，user_id 来自身份识别（不可由前端传入）
    - 返回：{"list": [...], "total": int, "page": int, "page_size": int}
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 我的提现记录 user_id=%s page=%s size=%s",
        request_id,
        user_id,
        page,
        page_size,
    )
    try:
        result = await svc.list_my_applies(
            user_id=user_id, page=page, page_size=page_size
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
