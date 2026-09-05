# @ai-generated
"""
B14 系统配置管理 API（CRUD + 批量更新 + 缓存刷新 + 注册表元信息）
路由前缀：/api/v1/admin/config
新建独立文件，不修改 B01-B13 任何基线 API

接口清单：
1. GET    /api/v1/admin/config/                  分页查询配置列表
2. GET    /api/v1/admin/config/registry          获取全量注册表 + 当前值
3. GET    /api/v1/admin/config/{config_key}      获取配置详情（含元信息）
4. POST   /api/v1/admin/config/                  新增配置（仅白名单 key）
5. PUT    /api/v1/admin/config/batch             批量更新开关类配置
6. PUT    /api/v1/admin/config/{config_key}      更新配置
7. DELETE /api/v1/admin/config/{config_key}      删除配置（软删除）
8. POST   /api/v1/admin/config/cache/refresh     刷新配置缓存
9. POST   /api/v1/admin/config/validate          校验配置值合法性

权限设计：
- 全部接口需要 config:manage 权限（超管 * 通配符自动放行）
- 限流中间件已包裹（gaking:prod:rate:admin:{ip}）
- 审计中间件自动记录所有写操作

路由顺序注意：静态路径（/registry /batch /cache/refresh /validate）
必须定义在动态路径 /{config_key} 之前，否则会被通配捕获
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.config.b14_constants import PERM_CONFIG_MANAGE
from src.schemas.b14_config import (
    ConfigValidateRequest,
    SystemConfigBatchUpdateRequest,
    SystemConfigCreateRequest,
    SystemConfigUpdateRequest,
)
from src.services.b14_config_service import B14ConfigService

logger = logging.getLogger("api.admin.b14_config")

router = APIRouter(prefix="/api/v1/admin/config", tags=["后台-系统配置(B14)"])


# ── 依赖注入：管理员身份识别 ──────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission([PERM_CONFIG_MANAGE])),
) -> int:
    """获取管理员ID（强制 JWT + RBAC config:manage 权限）"""
    return int(payload["user_id"])


def _serialize_config(config) -> dict:
    """序列化 SystemConfig 实例为字典"""
    def _fmt(dt):
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return dt
    return {
        "id": config.id,
        "config_key": config.config_key,
        "config_value": config.config_value,
        "config_name": config.config_name,
        "remark": config.remark,
        "create_time": _fmt(config.create_time),
        "update_time": _fmt(config.update_time),
    }


# ════════════════════════════════════════════════════════════
# 静态路径（必须在 /{config_key} 之前定义）
# ════════════════════════════════════════════════════════════


@router.get("/registry")
async def list_registry(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """获取全量配置注册表 + 当前生效值（前端配置中心渲染用）"""
    request_id = get_request_id(request)
    try:
        items = await B14ConfigService.list_registry()
        return success_response(data=items, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/batch")
async def batch_update_configs(
    request: Request,
    body: SystemConfigBatchUpdateRequest,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """批量更新开关类配置（仅 task_*_enable 前缀）"""
    request_id = get_request_id(request)
    try:
        result = await B14ConfigService.batch_update_configs(body.items)
        data = {
            "updated": result.updated,
            "skipped": result.skipped,
            "failed": result.failed,
        }
        return success_response(data=data, msg="批量更新完成", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/cache/refresh")
async def refresh_cache(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """手动刷新配置缓存（运维兜底，全量重新加载 DB → 内存 → Redis）"""
    request_id = get_request_id(request)
    try:
        result = await B14ConfigService.refresh_cache()
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/validate")
async def validate_config(
    request: Request,
    body: ConfigValidateRequest,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """校验配置值合法性（不写 DB，更新前预校验）"""
    request_id = get_request_id(request)
    try:
        result = B14ConfigService.validate_config_value(
            body.config_key, body.config_value
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 列表 & 动态路径
# ════════════════════════════════════════════════════════════


@router.get("/")
async def list_configs(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    config_key: Optional[str] = Query(None, description="配置键模糊筛选"),
    admin_user_id: int = Depends(get_admin_user_id),
):
    """分页查询系统配置列表"""
    request_id = get_request_id(request)
    try:
        items, total = await B14ConfigService.list_configs(
            page=page, page_size=page_size, config_key=config_key
        )
        data = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_serialize_config(c) for c in items],
        }
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/{config_key}")
async def get_config_detail(
    request: Request,
    config_key: str,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """获取配置详情（含注册表元信息 + 当前生效值）"""
    request_id = get_request_id(request)
    try:
        data = await B14ConfigService.get_config_detail(config_key)
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/")
async def create_config(
    request: Request,
    body: SystemConfigCreateRequest,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """新增系统配置（仅注册表白名单内 key 允许创建）"""
    request_id = get_request_id(request)
    try:
        config = await B14ConfigService.create_config(body)
        return success_response(
            data=_serialize_config(config), msg="配置创建成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/{config_key}")
async def update_config(
    request: Request,
    config_key: str,
    body: SystemConfigUpdateRequest,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """更新系统配置（仅允许更新 value/name/remark）"""
    request_id = get_request_id(request)
    try:
        config = await B14ConfigService.update_config(config_key, body)
        return success_response(
            data=_serialize_config(config), msg="配置更新成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.delete("/{config_key}")
async def delete_config(
    request: Request,
    config_key: str,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """删除系统配置（软删除，后续读取降级到注册表默认值）"""
    request_id = get_request_id(request)
    try:
        await B14ConfigService.delete_config(config_key)
        return success_response(
            data={"config_key": config_key}, msg="配置删除成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)
