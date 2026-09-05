# @ai-generated
"""
B13-补全 商品管理后台 API 路由
权限码：goods:manage（全部接口需此权限）
路由前缀：/api/v1/admin/goods
所有写操作自动被 B14 审计中间件记录
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
    error_response,
)
from src.common.auth_util import require_any_permission
from src.config.b13_b14_constants import PERM_GOODS_MANAGE
from src.schemas.b13_goods_admin import (
    GoodsBatchDeleteRequest,
    GoodsBatchShelfRequest,
    GoodsShelfRequest,
    GoodsSyncRequest,
    GoodsUpsertRequest,
)
from src.services.b13_goods_admin_service import B13GoodsAdminService

logger = logging.getLogger("api.b13_goods")

router = APIRouter(
    prefix="/api/v1/admin/goods",
    tags=["后台-商品管理(B13-补全)"],
)


@router.get("")
async def list_goods(
    request: Request,
    keyword: Optional[str] = Query(None, description="商品标题模糊搜索"),
    source_channel: Optional[str] = Query(None, description="来源渠道筛选"),
    shelf_status: Optional[str] = Query(None, description="上下架状态筛选"),
    category: Optional[str] = Query(None, description="类目筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    payload: dict = Depends(require_any_permission([PERM_GOODS_MANAGE])),
):
    """商品列表筛选查询"""
    request_id = get_request_id(request)
    try:
        items, total = await B13GoodsAdminService.list_goods(
            keyword=keyword,
            source_channel=source_channel,
            shelf_status=shelf_status,
            category=category,
            page=page,
            page_size=page_size,
        )
        shelf_stats = await B13GoodsAdminService.get_shelf_stats(
            keyword=keyword,
            source_channel=source_channel,
            category=category,
        )
        data = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
            "total_on_shelf": shelf_stats.get("on_shelf", 0),
            "total_off_shelf": shelf_stats.get("off_shelf", 0),
        }
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/{goods_id}")
async def get_goods_detail(
    request: Request,
    goods_id: str,
    source_channel: str = Query(..., description="来源渠道码"),
    payload: dict = Depends(require_any_permission([PERM_GOODS_MANAGE])),
):
    """商品详情"""
    request_id = get_request_id(request)
    try:
        data = await B13GoodsAdminService.get_goods_detail(goods_id, source_channel)
        if data is None:
            return error_response(
                code=404, msg="商品不存在", request_id=request_id
            )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("")
async def upsert_goods(
    request: Request,
    body: GoodsUpsertRequest,
    payload: dict = Depends(require_any_permission([PERM_GOODS_MANAGE])),
):
    """创建/更新商品（upsert by goods_id + channel）"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B13GoodsAdminService.upsert_goods(body, admin_user_id)
        return success_response(data=data, msg="商品保存成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/{goods_id}/shelf")
async def update_shelf_status(
    request: Request,
    goods_id: str,
    body: GoodsShelfRequest,
    source_channel: str = Query(..., description="来源渠道码"),
    payload: dict = Depends(require_any_permission([PERM_GOODS_MANAGE])),
):
    """单个商品上下架"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B13GoodsAdminService.update_shelf_status(
            goods_id=goods_id,
            source_channel=source_channel,
            shelf_status=body.shelf_status,
            admin_user_id=admin_user_id,
        )
        return success_response(data=data, msg="上下架状态更新成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/batch/shelf")
async def batch_update_shelf_status(
    request: Request,
    body: GoodsBatchShelfRequest,
    payload: dict = Depends(require_any_permission([PERM_GOODS_MANAGE])),
):
    """批量上下架"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B13GoodsAdminService.batch_update_shelf_status(
            goods_ids=body.goods_ids,
            source_channel=body.source_channel,
            shelf_status=body.shelf_status,
            admin_user_id=admin_user_id,
        )
        return success_response(data=data, msg="批量上下架成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.delete("/batch")
async def batch_delete_goods(
    request: Request,
    body: GoodsBatchDeleteRequest,
    payload: dict = Depends(require_any_permission([PERM_GOODS_MANAGE])),
):
    """批量删除商品管理记录"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B13GoodsAdminService.batch_delete_goods(
            goods_ids=body.goods_ids,
            source_channel=body.source_channel,
            admin_user_id=admin_user_id,
        )
        return success_response(data=data, msg="批量删除成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/sync")
async def sync_from_cps(
    request: Request,
    body: GoodsSyncRequest,
    payload: dict = Depends(require_any_permission([PERM_GOODS_MANAGE])),
):
    """从 CPS 渠道同步商品到本地管理表"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B13GoodsAdminService.sync_from_cps(
            source_channel=body.source_channel,
            keyword=body.keyword,
            page=body.page,
            page_size=body.page_size,
            admin_user_id=admin_user_id,
        )
        return success_response(data=data, msg="商品同步成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
