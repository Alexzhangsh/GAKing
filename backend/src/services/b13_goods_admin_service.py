# @ai-generated
"""
B13-补全 商品管理后台 Service
业务逻辑层：商品上下架、编辑、批量操作、CPS 渠道同步
所有写操作自动记录审计日志（通过 B14 审计中间件 + AuditLogger）
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.common.b14_audit_util import AuditLogger
from src.config.b13_b14_constants import (
    B13B14AuditAction,
    GoodsShelfStatus,
)
from src.dao.goods_management_dao import GoodsManagementDAO
from src.db.base import DatabaseManager
from src.models.business.goods_management_model import GoodsManagement
from src.schemas.b13_goods_admin import GoodsUpsertRequest

logger = logging.getLogger("services.b13_goods_admin")


class B13GoodsAdminService:
    """商品管理后台 Service"""

    @classmethod
    async def list_goods(
        cls,
        keyword: Optional[str] = None,
        source_channel: Optional[str] = None,
        shelf_status: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """商品列表筛选查询"""
        async with DatabaseManager.get_session() as session:
            dao = GoodsManagementDAO(session)
            items, total = await dao.list_with_filters(
                keyword=keyword,
                source_channel=source_channel,
                shelf_status=shelf_status,
                category=category,
                page=page,
                page_size=page_size,
            )
            return [cls._serialize(g) for g in items], total

    @classmethod
    async def get_shelf_stats(
        cls,
        keyword: Optional[str] = None,
        source_channel: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, int]:
        """统计总的上架/下架商品数（与列表共用非 shelf_status 过滤条件）"""
        async with DatabaseManager.get_session() as session:
            dao = GoodsManagementDAO(session)
            return await dao.count_by_shelf_status(
                keyword=keyword,
                source_channel=source_channel,
                category=category,
            )

    @classmethod
    async def get_goods_detail(
        cls, goods_id: str, source_channel: str
    ) -> Optional[Dict[str, Any]]:
        """商品详情"""
        async with DatabaseManager.get_session() as session:
            dao = GoodsManagementDAO(session)
            goods = await dao.get_by_goods_id_channel(goods_id, source_channel)
            if not goods:
                return None
            return cls._serialize(goods)

    @classmethod
    async def upsert_goods(
        cls, request: GoodsUpsertRequest, admin_user_id: int = 0
    ) -> Dict[str, Any]:
        """创建/更新商品（upsert by goods_id + channel）"""
        data = {
            "goods_title": request.goods_title,
            "goods_img": request.goods_img,
            "sale_price": request.sale_price,
            "original_price": request.original_price,
            "commission_rate": request.commission_rate,
            "bonus_price_normal": request.bonus_price_normal,
            "bonus_rate_normal": request.bonus_rate_normal,
            "bonus_price_vip": request.bonus_price_vip,
            "bonus_rate_vip": request.bonus_rate_vip,
            "category": request.category,
            "shop_name": request.shop_name,
            "sort_order": request.sort_order,
            "admin_remark": request.admin_remark,
            "last_admin_id": admin_user_id,
        }
        async with DatabaseManager.get_session() as session:
            dao = GoodsManagementDAO(session)
            goods = await dao.upsert_by_goods_channel(
                goods_id=request.goods_id,
                source_channel=request.source_channel,
                data=data,
            )
            return cls._serialize(goods)

    @classmethod
    async def update_shelf_status(
        cls,
        goods_id: str,
        source_channel: str,
        shelf_status: str,
        admin_user_id: int = 0,
    ) -> Dict[str, Any]:
        """单个商品上下架"""
        if shelf_status not in (GoodsShelfStatus.ON_SHELF.value, GoodsShelfStatus.OFF_SHELF.value):
            raise ValueError(f"非法上下架状态: {shelf_status}")

        async with DatabaseManager.get_session() as session:
            dao = GoodsManagementDAO(session)
            goods = await dao.get_by_goods_id_channel(goods_id, source_channel)
            if not goods:
                raise ValueError(f"商品不存在: goods_id={goods_id}, channel={source_channel}")

            updated = await dao.update_by_id(
                goods.id,
                {"shelf_status": shelf_status, "last_admin_id": admin_user_id},
            )

            # 审计日志
            action = (
                B13B14AuditAction.GOODS_SHELF_ON.value
                if shelf_status == GoodsShelfStatus.ON_SHELF.value
                else B13B14AuditAction.GOODS_SHELF_OFF.value
            )
            await AuditLogger.log(
                action=action,
                target_type="goods",
                target_id=goods.id,
                details={
                    "goods_id": goods_id,
                    "source_channel": source_channel,
                    "shelf_status": shelf_status,
                },
                user_id=admin_user_id,
            )
            return cls._serialize(updated)

    @classmethod
    async def batch_update_shelf_status(
        cls,
        goods_ids: List[str],
        source_channel: str,
        shelf_status: str,
        admin_user_id: int = 0,
    ) -> Dict[str, Any]:
        """批量上下架"""
        if shelf_status not in (GoodsShelfStatus.ON_SHELF.value, GoodsShelfStatus.OFF_SHELF.value):
            raise ValueError(f"非法上下架状态: {shelf_status}")

        async with DatabaseManager.get_session() as session:
            dao = GoodsManagementDAO(session)
            count = await dao.batch_update_shelf_status(
                goods_ids=goods_ids,
                source_channel=source_channel,
                shelf_status=shelf_status,
            )

            # 审计日志
            await AuditLogger.log(
                action=B13B14AuditAction.GOODS_BATCH_OP.value,
                target_type="goods",
                target_id=0,
                details={
                    "goods_ids": goods_ids[:50],  # 限制日志长度
                    "source_channel": source_channel,
                    "shelf_status": shelf_status,
                    "affected_count": count,
                },
                user_id=admin_user_id,
            )
            return {
                "affected_count": count,
                "total_requested": len(goods_ids),
                "shelf_status": shelf_status,
            }

    @classmethod
    async def batch_delete_goods(
        cls,
        goods_ids: List[str],
        source_channel: str,
        admin_user_id: int = 0,
    ) -> Dict[str, Any]:
        """批量软删除商品管理记录"""
        async with DatabaseManager.get_session() as session:
            dao = GoodsManagementDAO(session)
            # 查出所有匹配的记录 ID
            count = 0
            for goods_id in goods_ids:
                goods = await dao.get_by_goods_id_channel(goods_id, source_channel)
                if goods:
                    await dao.logic_delete_by_id(goods.id)
                    count += 1

            # 审计日志
            await AuditLogger.log(
                action=B13B14AuditAction.GOODS_BATCH_OP.value,
                target_type="goods",
                target_id=0,
                details={
                    "goods_ids": goods_ids[:50],
                    "source_channel": source_channel,
                    "operation": "batch_delete",
                    "affected_count": count,
                },
                user_id=admin_user_id,
            )
            return {
                "affected_count": count,
                "total_requested": len(goods_ids),
            }

    @classmethod
    async def sync_from_cps(
        cls,
        source_channel: str,
        keyword: str = "",
        page: int = 1,
        page_size: int = 20,
        admin_user_id: int = 0,
    ) -> Dict[str, Any]:
        """从 CPS 渠道同步商品到本地管理表

        委托 CPS 适配器搜索商品，upsert 到 goods_management 表
        """
        # 动态导入避免循环依赖
        from src.cps.adapter.base_adapter import BaseCpsAdapter
        from src.cps.adapter.miaoyouquan_adapter import MiaoyouquanAdapter
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter

        # 选择适配器
        adapter_map = {
            "myq": MiaoyouquanAdapter,
            "orderx": DingdanxiaAdapter,
        }
        adapter_cls = adapter_map.get(source_channel)
        if not adapter_cls:
            raise ValueError(f"不支持的渠道码: {source_channel}")

        try:
            adapter = adapter_cls()
            result = await adapter.search_goods(
                keyword=keyword, page=page, size=page_size
            )

            # upsert 到本地管理表
            synced_count = 0
            async with DatabaseManager.get_session() as session:
                dao = GoodsManagementDAO(session)
                for goods_dto in result.items:
                    data = {
                        "goods_title": goods_dto.goods_title,
                        "goods_img": goods_dto.goods_img,
                        "sale_price": goods_dto.sale_price,
                        "commission_rate": goods_dto.commission_rate,
                        "category": goods_dto.category,
                        "shop_name": goods_dto.shop_name,
                        "last_admin_id": admin_user_id,
                    }
                    await dao.upsert_by_goods_channel(
                        goods_id=goods_dto.goods_id,
                        source_channel=source_channel,
                        data=data,
                    )
                    synced_count += 1

            # 审计日志
            await AuditLogger.log(
                action=B13B14AuditAction.GOODS_SYNC.value,
                target_type="goods",
                target_id=0,
                details={
                    "source_channel": source_channel,
                    "keyword": keyword,
                    "page": page,
                    "page_size": page_size,
                    "synced_count": synced_count,
                    "total_fetched": len(result.items),
                },
                user_id=admin_user_id,
            )
            return {
                "source_channel": source_channel,
                "keyword": keyword,
                "synced_count": synced_count,
                "total_fetched": len(result.items),
            }
        except Exception as e:
            logger.error("[sync_from_cps] 同步失败 channel=%s: %s", source_channel, e)
            raise ValueError(f"商品同步失败: {e}")

    @staticmethod
    def _serialize(goods: GoodsManagement) -> Dict[str, Any]:
        """序列化商品管理记录"""
        return {
            "id": goods.id,
            "goods_id": goods.goods_id,
            "source_channel": goods.source_channel,
            "goods_title": goods.goods_title,
            "goods_img": goods.goods_img,
            "sale_price": str(goods.sale_price) if goods.sale_price else "0.00",
            "original_price": str(goods.original_price) if goods.original_price else "0.00",
            "commission_rate": str(goods.commission_rate) if goods.commission_rate else "0.00",
            "bonus_price_normal": str(goods.bonus_price_normal) if goods.bonus_price_normal else "0.00",
            "bonus_rate_normal": str(goods.bonus_rate_normal) if goods.bonus_rate_normal else "0.00",
            "bonus_price_vip": str(goods.bonus_price_vip) if goods.bonus_price_vip else "0.00",
            "bonus_rate_vip": str(goods.bonus_rate_vip) if goods.bonus_rate_vip else "0.00",
            "category": goods.category,
            "shop_name": goods.shop_name,
            "shelf_status": goods.shelf_status,
            "sort_order": goods.sort_order,
            "admin_remark": goods.admin_remark,
            "last_admin_id": goods.last_admin_id,
            "create_time": goods.create_time.isoformat() if goods.create_time else None,
            "update_time": goods.update_time.isoformat() if goods.update_time else None,
        }
