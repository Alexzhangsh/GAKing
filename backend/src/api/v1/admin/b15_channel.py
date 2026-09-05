# @ai-generated
"""
F04 渠道配置管理 API（CRUD + 密钥测试）
路由前缀：/api/v1/admin/channel
权限码：config:manage（CRUD）/ channel:test（密钥测试）
审计中间件自动记录所有写操作

接口清单：
1. GET    /api/v1/admin/channel/list               渠道配置列表
2. GET    /api/v1/admin/channel/{channel_code}      渠道配置详情
3. POST   /api/v1/admin/channel                     新增渠道配置
4. PUT    /api/v1/admin/channel/{channel_code}      更新渠道配置
5. DELETE /api/v1/admin/channel/{channel_code}      删除渠道配置（软删除）
6. POST   /api/v1/admin/channel/test-key            渠道密钥测试（生产环境拦截）
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.config.b14_constants import PERM_CONFIG_MANAGE
from src.config.b15_constants import PERM_CHANNEL_TEST
from src.config.env_config import EnvConfig
from src.cps.adapter_factory import AdapterFactory
from src.dao.base_dao import BaseDAO
from src.db.base import DatabaseManager
from src.models.system.channel_config import ChannelMapping

logger = logging.getLogger("api.admin.b15_channel")

router = APIRouter(prefix="/api/v1/admin/channel", tags=["后台-渠道配置(F04)"])


# ── 依赖注入 ──────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission([PERM_CONFIG_MANAGE])),
) -> int:
    return int(payload["user_id"])


async def get_admin_user_id_channel_test(
    payload: dict = Depends(require_any_permission([PERM_CHANNEL_TEST])),
) -> int:
    return int(payload["user_id"])


# ── Schema ──────────────


class ChannelConfigCreate(BaseModel):
    channel_code: str = Field(..., max_length=32, description="渠道标识：myq / orderx")
    channel_name: str = Field("", max_length=64, description="渠道中文名称")
    api_token: str = Field("", max_length=256, description="渠道API Token")
    api_secret: str = Field("", max_length=256, description="渠道API密钥")
    pid: str = Field("", max_length=64, description="渠道推广位PID")
    settle_rate: float = Field(0.0, ge=0, le=1, description="结算比例(0~1)")
    status: bool = Field(True, description="状态：True-启用 False-禁用")
    remark: str = Field("", max_length=512, description="备注")


class ChannelConfigUpdate(BaseModel):
    channel_name: Optional[str] = Field(None, max_length=64)
    api_token: Optional[str] = Field(None, max_length=256)
    api_secret: Optional[str] = Field(None, max_length=256)
    pid: Optional[str] = Field(None, max_length=64)
    settle_rate: Optional[float] = Field(None, ge=0, le=1)
    status: Optional[bool] = None
    remark: Optional[str] = Field(None, max_length=512)


class ChannelKeyTestRequest(BaseModel):
    channel_code: str = Field(..., max_length=32, description="渠道标识：myq / orderx")
    api_token: str = Field(..., max_length=256, description="渠道API Token")
    api_secret: str = Field("", max_length=256, description="渠道API密钥")


# ── 序列化 ──────────────


def _serialize_channel(c: ChannelMapping) -> Dict[str, Any]:
    return {
        "id": c.id,
        "channel_code": c.channel_code,
        "channel_name": c.channel_name,
        "api_token": c.api_token,
        "api_secret": "***" if c.api_secret else "",  # 密钥脱敏
        "pid": c.pid,
        "settle_rate": float(c.settle_rate) if c.settle_rate else 0.0,
        "status": c.status,
        "remark": c.remark,
        "create_time": c.create_time.strftime("%Y-%m-%d %H:%M:%S") if c.create_time else None,
        "update_time": c.update_time.strftime("%Y-%m-%d %H:%M:%S") if c.update_time else None,
    }


# ════════════════════════════════════════════════════════════
# 渠道配置 CRUD
# ════════════════════════════════════════════════════════════


@router.get("/list")
async def list_channels(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin_user_id: int = Depends(get_admin_user_id),
):
    """渠道配置列表"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            items, total = await dao.paginate_list(
                page=page, page_size=page_size, order_by="-create_time"
            )
            data = {
                "total": total, "page": page, "page_size": page_size,
                "items": [_serialize_channel(c) for c in items],
            }
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/{channel_code}")
async def get_channel(
    request: Request,
    channel_code: str,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """渠道配置详情"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            stmt = dao._active_query().where(ChannelMapping.channel_code == channel_code)
            result = await session.execute(stmt)
            c = result.scalar_one_or_none()
            if c is None:
                raise ValueError(f"渠道配置不存在: {channel_code}")
            return success_response(data=_serialize_channel(c), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("")
async def create_channel(
    request: Request,
    body: ChannelConfigCreate,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """新增渠道配置"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            data = body.model_dump()
            c = await dao.create(data)
            return success_response(data=_serialize_channel(c), msg="渠道配置创建成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/{channel_code}")
async def update_channel(
    request: Request,
    channel_code: str,
    body: ChannelConfigUpdate,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """更新渠道配置"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            stmt = dao._active_query().where(ChannelMapping.channel_code == channel_code)
            result = await session.execute(stmt)
            c = result.scalar_one_or_none()
            if c is None:
                raise ValueError(f"渠道配置不存在: {channel_code}")
            data = body.model_dump(exclude_unset=True)
            for key, value in data.items():
                if hasattr(c, key):
                    setattr(c, key, value)
            await session.flush()
            await session.commit()
            return success_response(data=_serialize_channel(c), msg="渠道配置更新成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.delete("/{channel_code}")
async def delete_channel(
    request: Request,
    channel_code: str,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """删除渠道配置（软删除）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            stmt = dao._active_query().where(ChannelMapping.channel_code == channel_code)
            result = await session.execute(stmt)
            c = result.scalar_one_or_none()
            if c is None:
                raise ValueError(f"渠道配置不存在: {channel_code}")
            c.is_delete = True
            from datetime import datetime
            c.update_time = datetime.now()
            await session.flush()
            await session.commit()
            return success_response(data={"channel_code": channel_code}, msg="渠道配置删除成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 渠道密钥测试（对接真实适配器 health_check，S04 P2-4）
# ════════════════════════════════════════════════════════════


@router.post("/test-key")
async def test_channel_key(
    request: Request,
    body: ChannelKeyTestRequest,
    admin_user_id: int = Depends(get_admin_user_id_channel_test),
):
    """测试渠道密钥有效性（对接真实适配器）

    S04 P2-4 优化：由「模拟格式校验」升级为「调用真实渠道适配器 health_check」，
    用提交的密钥实际请求渠道接口，验证密钥是否真实有效。

    生产环境仍禁止测试密钥（is_production → 403），避免生产流量异常。
    """
    request_id = get_request_id(request)

    # 生产环境拦截
    if EnvConfig.is_production():
        return handle_service_exception(
            ValueError("生产环境禁止测试密钥，请在开发/测试环境操作"),
            request_id,
        )

    try:
        # 校验渠道标识
        if body.channel_code not in AdapterFactory.get_supported_channels():
            raise ValueError(
                f"不支持的渠道标识: {body.channel_code}，支持的渠道: "
                f"{AdapterFactory.get_supported_channels()}"
            )
        channel_name = _get_channel_name(body.channel_code)

        # 校验密钥非空
        if not body.api_token or len(body.api_token.strip()) < 10:
            raise ValueError("API Token 不能为空且长度需大于10")

        # ── S04 P2-4：对接真实适配器，用提交的密钥实例化并调用 health_check ──
        try:
            adapter = _build_test_adapter(body)
        except Exception as exc:
            raise ValueError(f"创建 {channel_name} 适配器失败: {exc}")

        alive = await adapter.health_check()

        if alive:
            test_result = {
                "success": True,
                "message": f"{channel_name} 密钥验证通过，渠道接口连通正常",
                "channel_code": body.channel_code,
                "token_length": len(body.api_token),
                "secret_length": len(body.api_secret) if body.api_secret else 0,
                "tested_by": "real_adapter_health_check",
            }
            return success_response(data=test_result, msg="密钥测试通过", request_id=request_id)

        raise ValueError(
            f"{channel_name} 密钥验证失败：渠道接口调用异常（密钥无效或服务不可达）"
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


def _get_channel_name(channel_code: str) -> str:
    """获取渠道中文名（供日志/提示使用）"""
    names = {"myq": "喵有券", "orderx": "订单侠", "dta": "大淘客"}
    return names.get(channel_code, channel_code)


def _build_test_adapter(body: ChannelKeyTestRequest):
    """用提交的密钥构造渠道适配器实例（不污染环境变量单例）

    S04 P2-4：直接实例化 B01 真实适配器，将测试密钥注入构造参数，
    避免使用 AdapterFactory 的环境变量单例（那会测试线上已配置密钥）。
    返回原始适配器实例（不含熔断器，测试场景不需要熔断）。
    """
    from src.cps.adapter.dataoke_adapter import DataokeAdapter
    from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter
    from src.cps.adapter.miaoyouquan_adapter import MiaoyouquanAdapter

    if body.channel_code == "myq":
        adapter = MiaoyouquanAdapter(
            apkey=body.api_token,
            tbname=EnvConfig.MIAO_QUAN_TBNAME,
            pid=EnvConfig.MIAO_QUAN_PID,
        )
    elif body.channel_code == "orderx":
        # 订单侠适配器构造参数：apikey（唯一鉴权参数）
        adapter = DingdanxiaAdapter(
            apikey=body.api_token,
        )
    elif body.channel_code == "dta":
        # 大淘客适配器构造参数：appid + appkey
        adapter = DataokeAdapter(
            appid=body.api_token,
            appkey=body.api_secret or "",
        )
    else:
        raise ValueError(f"不支持的渠道标识: {body.channel_code}")
    return adapter
