# @ai-generated
"""
后台订单同步管理接口层（B05）
路由前缀：/api/v1/admin/order-sync
职责：管理员身份识别 → 参数校验 → 调用 OrderSyncService → 统一响应封装
不包含任何业务逻辑，业务规则（游标推进/重试/幂等入库）全部在 Service 层

接口清单：
1. POST /api/v1/admin/order-sync/trigger   手动触发单渠道订单同步（可指定时间范围）
2. POST /api/v1/admin/order-sync/retry     手动补发失败队列（取 N 条重试）
3. GET  /api/v1/admin/order-sync/status    查询三渠道同步状态（游标/失败队列/熔断/cron）

身份识别：
- 强制 JWT（Authorization: Bearer <token>）+ RBAC order:sync 权限校验；
- require_any_permission 完成：HTTPBearer 解析 token → JWT 校验 → RbacUtil 权限校验
  （含 "*" 通配符的超管直接放行；无权限→403；缺 token→401）。
"""
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.dao.order_sync_dao import OrderSyncDAO
from src.db.init_db import DatabaseManager
from src.schemas.order_sync import (
    OrderSyncRetryRequest,
    OrderSyncTriggerRequest,
)
from src.services.order_sync_service import OrderSyncService

logger = logging.getLogger("api.admin.order_sync")

router = APIRouter(prefix="/api/v1/admin/order-sync", tags=["后台-订单同步"])


# ── 依赖注入：管理员身份识别 + 数据库会话 + Service 实例 ──────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission(["order:sync"])),
) -> int:
    """获取后台管理员ID（强制 JWT + RBAC order:sync 权限校验）

    依赖 require_any_permission(["order:sync"]) 完成：
      1. HTTPBearer 解析 Authorization: Bearer <token>（缺失→401）
      2. JwtAuthGuard.verify_token 校验 JWT（无效/过期→401）
      3. RbacUtil.has_any_permission 校验角色权限
         （超管 permissions 含 "*" 通配符直接放行；无权限→403）
    """
    return int(payload["user_id"])


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def get_order_sync_service(
    db: AsyncSession = Depends(get_db),
) -> OrderSyncService:
    """构造 OrderSyncService 实例（注入 OrderSyncDAO）"""
    return OrderSyncService(OrderSyncDAO(db))


# ══════════════════════════════════════════════════════
# 接口实现
# ══════════════════════════════════════════════════════


@router.post("/trigger")
async def trigger_sync(
    body: OrderSyncTriggerRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: OrderSyncService = Depends(get_order_sync_service),
):
    """1. 手动触发单渠道订单同步

    - 可指定 start_time / end_time（缺省走 Redis 游标）
    - 走完整同步流程：游标推进 + 窗口切分 + 重试3次 + 熔断保护 + 幂等入库
    - 返回各窗口明细（pulled/inserted/updated/status）
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 手动触发订单同步 admin=%s channel=%s start=%s end=%s",
        request_id,
        admin_user_id,
        body.channel_code,
        body.start_time,
        body.end_time,
    )
    try:
        result = await svc.manual_sync_channel(
            channel_code=body.channel_code,
            start_time=body.start_time,
            end_time=body.end_time,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/retry")
async def retry_failed(
    body: OrderSyncRetryRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: OrderSyncService = Depends(get_order_sync_service),
):
    """2. 手动补发失败队列

    - 从 Redis 失败队列取 batch_size 条记录重试
    - 补发成功：从队列移除；补发失败：重新入队
    - 返回各条补发明细（success/failed + pulled/inserted）
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 手动补发失败队列 admin=%s channel=%s batch_size=%s",
        request_id,
        admin_user_id,
        body.channel_code,
        body.batch_size,
    )
    try:
        result = await svc.manual_retry_failed(
            channel_code=body.channel_code,
            batch_size=body.batch_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/status")
async def get_sync_status(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: OrderSyncService = Depends(get_order_sync_service),
):
    """3. 查询三渠道同步状态

    - 游标（最后成功同步时间）
    - 失败队列积压条数
    - 熔断器状态（CLOSED/OPEN/HALF_OPEN）
    - 定时任务 cron 表达式
    - 渠道任务开关
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询订单同步状态 admin=%s",
        request_id,
        admin_user_id,
    )
    try:
        result = await svc.get_sync_status()
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
