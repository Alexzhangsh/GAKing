# @ai-generated
"""
X02-1 会员套餐管理 API
路由前缀：/api/v1/admin/member-package
权限码：member:manage（套餐管理全部接口）
审计：写操作（新增/编辑/上下架/删除）自动记录审计日志

接口清单：
1. GET    /api/v1/admin/member-package/packages           套餐列表（分页+状态/关键字筛选）
2. GET    /api/v1/admin/member-package/packages/on-shelf  上架套餐列表（供 C 端/结算使用）
3. GET    /api/v1/admin/member-package/packages/{id}      套餐详情
4. POST   /api/v1/admin/member-package/packages           新增套餐
5. PUT    /api/v1/admin/member-package/packages/{id}      编辑套餐
6. PUT    /api/v1/admin/member-package/packages/{id}/status  上下架
7. DELETE /api/v1/admin/member-package/packages/{id}      删除套餐（软删除）
"""
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.common.b14_audit_util import AuditLogger
from src.config.x02_1_constants import (
    PERM_MEMBER_MANAGE,
    PACKAGE_STATUS_LABELS,
    PACKAGE_STATUS_OFF,
    PACKAGE_STATUS_ON,
)
from src.dao.member_package_dao import MemberPackageDAO
from src.db.init_db import DatabaseManager
from src.models.business.member_package_model import MemberPackage

logger = logging.getLogger("api.admin.member_package")

router = APIRouter(prefix="/api/v1/admin/member-package", tags=["后台-会员套餐管理(X02-1)"])

# 审计动作码
ACTION_PACKAGE_CREATE = "MEMBER_PACKAGE_CREATE"
ACTION_PACKAGE_UPDATE = "MEMBER_PACKAGE_UPDATE"
ACTION_PACKAGE_STATUS = "MEMBER_PACKAGE_STATUS"
ACTION_PACKAGE_DELETE = "MEMBER_PACKAGE_DELETE"
TARGET_TYPE_PACKAGE = "member_package"


# ── 依赖注入 ──────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission([PERM_MEMBER_MANAGE])),
) -> int:
    return int(payload["user_id"])


# ── Schema ──────────────


class PackageCreateRequest(BaseModel):
    """新增会员套餐请求"""
    package_code: str = Field(..., max_length=32, description="套餐编码（唯一）")
    package_name: str = Field(..., max_length=64, description="套餐名称")
    price: float = Field(0.0, ge=0, description="套餐价格（元）")
    duration_days: int = Field(30, ge=1, le=3650, description="有效期（天）")
    member_commission_rate: float = Field(..., ge=0, le=1, description="会员分佣比例(0~1)")
    status: int = Field(PACKAGE_STATUS_ON, ge=0, le=1, description="上下架状态：1-上架 0-下架")
    sort_order: int = Field(0, ge=0, description="排序号")
    description: str = Field("", max_length=512, description="套餐描述")

    @model_validator(mode="after")
    def validate_rate(self):
        if self.member_commission_rate < 0 or self.member_commission_rate > 1:
            raise ValueError("会员分佣比例必须在 0~1 区间")
        return self


class PackageUpdateRequest(BaseModel):
    """编辑会员套餐请求（全部字段可选，仅更新传入字段）"""
    package_name: Optional[str] = Field(None, max_length=64, description="套餐名称")
    price: Optional[float] = Field(None, ge=0, description="套餐价格（元）")
    duration_days: Optional[int] = Field(None, ge=1, le=3650, description="有效期（天）")
    member_commission_rate: Optional[float] = Field(None, ge=0, le=1, description="会员分佣比例(0~1)")
    status: Optional[int] = Field(None, ge=0, le=1, description="上下架状态：1-上架 0-下架")
    sort_order: Optional[int] = Field(None, ge=0, description="排序号")
    description: Optional[str] = Field(None, max_length=512, description="套餐描述")


class PackageStatusRequest(BaseModel):
    """上下架请求"""
    status: int = Field(..., ge=0, le=1, description="目标状态：1-上架 0-下架")


# ── 序列化 ──────────────


def _serialize_package(p: MemberPackage) -> Dict[str, Any]:
    return {
        "id": p.id,
        "package_code": p.package_code,
        "package_name": p.package_name,
        "price": float(p.price) if p.price is not None else 0.0,
        "duration_days": p.duration_days or 0,
        "member_commission_rate": float(p.member_commission_rate) if p.member_commission_rate is not None else 0.0,
        "status": p.status,
        "status_label": PACKAGE_STATUS_LABELS.get(p.status, "未知"),
        "sort_order": p.sort_order or 0,
        "description": p.description or "",
        "create_time": p.create_time.strftime("%Y-%m-%d %H:%M:%S") if p.create_time else None,
        "update_time": p.update_time.strftime("%Y-%m-%d %H:%M:%S") if p.update_time else None,
    }


# ════════════════════════════════════════════════════════════
# 1. 套餐列表
# ════════════════════════════════════════════════════════════


@router.get("/packages")
async def list_packages(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status: Optional[int] = Query(None, ge=0, le=1, description="上下架状态筛选"),
    keyword: Optional[str] = Query(None, max_length=64, description="名称/编码关键字"),
    admin_user_id: int = Depends(get_admin_user_id),
):
    """会员套餐列表（分页 + 状态/关键字筛选）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = MemberPackageDAO(session)
            items, total = await dao.paginate_packages(
                page=page, page_size=page_size, status=status, keyword=keyword,
            )
            data = {
                "total": total, "page": page, "page_size": page_size,
                "items": [_serialize_package(p) for p in items],
            }
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 2. 上架套餐列表
# ════════════════════════════════════════════════════════════


@router.get("/packages/on-shelf")
async def list_on_shelf_packages(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """上架套餐列表（供 C 端展示 / 结算识别使用）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = MemberPackageDAO(session)
            items = await dao.list_on_shelf()
            data = {"items": [_serialize_package(p) for p in items]}
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 3. 套餐详情
# ════════════════════════════════════════════════════════════


@router.get("/packages/{package_id}")
async def get_package(
    request: Request,
    package_id: int,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """会员套餐详情"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = MemberPackageDAO(session)
            package = await dao.get_by_id(package_id)
            if package is None:
                raise ValueError(f"会员套餐不存在: {package_id}")
            return success_response(data=_serialize_package(package), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 4. 新增套餐
# ════════════════════════════════════════════════════════════


@router.post("/packages")
async def create_package(
    request: Request,
    body: PackageCreateRequest,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """新增会员套餐"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = MemberPackageDAO(session)
            existing = await dao.get_by_code(body.package_code)
            if existing is not None:
                raise ValueError(f"套餐编码已存在: {body.package_code}")

            package = await dao.create({
                "package_code": body.package_code,
                "package_name": body.package_name,
                "price": Decimal(str(body.price)),
                "duration_days": body.duration_days,
                "member_commission_rate": Decimal(str(body.member_commission_rate)),
                "status": body.status,
                "sort_order": body.sort_order,
                "description": body.description,
            })

            # 审计日志
            await AuditLogger.log(
                action=ACTION_PACKAGE_CREATE,
                target_type=TARGET_TYPE_PACKAGE,
                target_id=package.id,
                details={
                    "package_code": body.package_code,
                    "package_name": body.package_name,
                    "price": body.price,
                    "duration_days": body.duration_days,
                    "member_commission_rate": body.member_commission_rate,
                    "status": body.status,
                    "path": request.url.path,
                },
                user_id=admin_user_id,
                ip_address=AuditLogger.get_client_ip(request),
                user_agent=AuditLogger.get_user_agent(request),
            )

            return success_response(
                data=_serialize_package(package), msg="会员套餐创建成功", request_id=request_id
            )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 5. 编辑套餐
# ════════════════════════════════════════════════════════════


@router.put("/packages/{package_id}")
async def update_package(
    request: Request,
    package_id: int,
    body: PackageUpdateRequest,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """编辑会员套餐（仅更新传入字段）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = MemberPackageDAO(session)
            package = await dao.get_by_id(package_id)
            if package is None:
                raise ValueError(f"会员套餐不存在: {package_id}")

            data = body.model_dump(exclude_unset=True)
            for key, value in data.items():
                if key in ("price", "member_commission_rate") and value is not None:
                    value = Decimal(str(value))
                if hasattr(package, key):
                    setattr(package, key, value)
            await session.flush()
            await session.commit()

            # 审计日志
            await AuditLogger.log(
                action=ACTION_PACKAGE_UPDATE,
                target_type=TARGET_TYPE_PACKAGE,
                target_id=package.id,
                details={
                    "package_code": package.package_code,
                    "package_name": package.package_name,
                    "price": float(package.price or 0),
                    "duration_days": package.duration_days,
                    "member_commission_rate": float(package.member_commission_rate or 0),
                    "status": package.status,
                    "path": request.url.path,
                },
                user_id=admin_user_id,
                ip_address=AuditLogger.get_client_ip(request),
                user_agent=AuditLogger.get_user_agent(request),
            )

            return success_response(
                data=_serialize_package(package), msg="会员套餐更新成功", request_id=request_id
            )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 6. 上下架
# ════════════════════════════════════════════════════════════


@router.put("/packages/{package_id}/status")
async def update_package_status(
    request: Request,
    package_id: int,
    body: PackageStatusRequest,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """会员套餐上下架"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = MemberPackageDAO(session)
            package = await dao.get_by_id(package_id)
            if package is None:
                raise ValueError(f"会员套餐不存在: {package_id}")
            old_status = package.status
            package.status = body.status
            await session.flush()
            await session.commit()

            # 审计日志
            await AuditLogger.log(
                action=ACTION_PACKAGE_STATUS,
                target_type=TARGET_TYPE_PACKAGE,
                target_id=package.id,
                details={
                    "package_code": package.package_code,
                    "old_status": old_status,
                    "new_status": body.status,
                    "path": request.url.path,
                },
                user_id=admin_user_id,
                ip_address=AuditLogger.get_client_ip(request),
                user_agent=AuditLogger.get_user_agent(request),
            )

            return success_response(
                data={"id": package.id, "status": body.status},
                msg="套餐已上架" if body.status == PACKAGE_STATUS_ON else "套餐已下架",
                request_id=request_id,
            )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 7. 删除套餐
# ════════════════════════════════════════════════════════════


@router.delete("/packages/{package_id}")
async def delete_package(
    request: Request,
    package_id: int,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """删除会员套餐（软删除）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = MemberPackageDAO(session)
            package = await dao.get_by_id(package_id)
            if package is None:
                raise ValueError(f"会员套餐不存在: {package_id}")
            deleted = await dao.logic_delete_by_id(package_id)
            if not deleted:
                raise ValueError(f"会员套餐删除失败: {package_id}")

            # 审计日志
            await AuditLogger.log(
                action=ACTION_PACKAGE_DELETE,
                target_type=TARGET_TYPE_PACKAGE,
                target_id=package_id,
                details={
                    "package_code": package.package_code,
                    "package_name": package.package_name,
                    "path": request.url.path,
                },
                user_id=admin_user_id,
                ip_address=AuditLogger.get_client_ip(request),
                user_agent=AuditLogger.get_user_agent(request),
            )

            return success_response(
                data={"id": package_id}, msg="会员套餐已删除", request_id=request_id
            )
    except Exception as exc:
        return handle_service_exception(exc, request_id)
