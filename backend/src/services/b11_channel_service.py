# @ai-generated
"""
B11-1 渠道管理 Service 层

包含：
1. B11ChannelBlacklistService - 渠道黑名单业务逻辑
2. B11ChannelStatisticsService - 渠道统计业务逻辑
3. B11ChannelConfigLogService - 配置变更日志业务逻辑
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.config.b11_constants import (
    BLACKLIST_TYPE_LABELS,
    OPERATION_TYPE_LABELS,
)
from src.dao.b11_channel_dao import (
    ChannelBlacklistDAO,
    ChannelDailyStatDAO,
    ChannelConfigLogDAO,
)
from src.models.system.b11_channel_blacklist import ChannelBlacklist
from src.models.system.b11_channel_daily_stat import ChannelDailyStat
from src.models.system.b11_channel_config_log import ChannelConfigLog

logger = logging.getLogger("service.b11_channel")


# ════════════════════════════════════════════════════════════
# 序列化工具
# ════════════════════════════════════════════════════════════


def _serialize_blacklist(item: ChannelBlacklist) -> Dict[str, Any]:
    """序列化黑名单记录"""
    return {
        "id": item.id,
        "channel_code": item.channel_code,
        "blacklist_type": item.blacklist_type,
        "blacklist_type_label": BLACKLIST_TYPE_LABELS.get(item.blacklist_type, "未知"),
        "blacklist_value": item.blacklist_value,
        "reason": item.reason or "",
        "status": item.status,
        "status_label": "启用" if item.status == 1 else "禁用",
        "operator_id": item.operator_id or 0,
        "operator_name": item.operator_name or "",
        "create_time": item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else None,
        "update_time": item.update_time.strftime("%Y-%m-%d %H:%M:%S") if item.update_time else None,
    }


def _serialize_daily_stat(item: ChannelDailyStat) -> Dict[str, Any]:
    """序列化每日统计记录"""
    return {
        "id": item.id,
        "stat_date": item.stat_date.isoformat() if item.stat_date else None,
        "channel_code": item.channel_code,
        "order_count": item.order_count,
        "total_pay_amount": str(item.total_pay_amount or 0),
        "total_commission": str(item.total_commission or 0),
        "user_commission": str(item.user_commission or 0),
        "platform_commission": str(item.platform_commission or 0),
        "settled_count": item.settled_count,
        "refund_count": item.refund_count,
        "refund_amount": str(item.refund_amount or 0),
        "create_time": item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else None,
    }


def _serialize_config_log(item: ChannelConfigLog) -> Dict[str, Any]:
    """序列化配置变更日志"""
    return {
        "id": item.id,
        "channel_code": item.channel_code,
        "config_key": item.config_key or "",
        "old_value": item.old_value or "",
        "old_value_label": item.old_value_label or "",
        "new_value": item.new_value or "",
        "new_value_label": item.new_value_label or "",
        "operator_id": item.operator_id or 0,
        "operator_name": item.operator_name or "",
        "operation_type": item.operation_type or "",
        "operation_type_label": OPERATION_TYPE_LABELS.get(item.operation_type, item.operation_type or ""),
        "remark": item.remark or "",
        "create_time": item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else None,
    }


# ════════════════════════════════════════════════════════════
# 黑名单服务
# ════════════════════════════════════════════════════════════


class B11ChannelBlacklistService:
    """渠道黑名单业务服务"""

    def __init__(self, dao: ChannelBlacklistDAO):
        self.dao = dao

    async def list_blacklist(
        self,
        channel_code: Optional[str] = None,
        blacklist_type: Optional[str] = None,
        status: Optional[int] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页查询黑名单列表"""
        items, total = await self.dao.list_by_channel(
            channel_code=channel_code,
            blacklist_type=blacklist_type,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_serialize_blacklist(item) for item in items],
        }

    async def get_blacklist_detail(self, item_id: int) -> Optional[Dict[str, Any]]:
        """查询黑名单详情"""
        item = await self.dao.get_by_id(item_id)
        if item is None:
            return None
        return _serialize_blacklist(item)

    async def add_blacklist(
        self,
        channel_code: str,
        blacklist_type: str,
        blacklist_value: str,
        reason: str = "",
        operator_id: int = 0,
        operator_name: str = "",
    ) -> Dict[str, Any]:
        """新增黑名单

        Args:
            channel_code: 渠道标识
            blacklist_type: 黑名单类型
            blacklist_value: 黑名单值
            reason: 拉黑原因
            operator_id: 操作人ID
            operator_name: 操作人名称
        Returns:
            新增的黑名单记录
        Raises:
            ValueError: 黑名单记录已存在
        """
        # 检查是否已存在
        existing = await self.dao.get_by_value(channel_code, blacklist_type, blacklist_value)
        if existing:
            raise ValueError(
                f"黑名单记录已存在: {channel_code}/{blacklist_type}/{blacklist_value}"
            )

        data = {
            "channel_code": channel_code,
            "blacklist_type": blacklist_type,
            "blacklist_value": blacklist_value,
            "reason": reason,
            "status": 1,
            "operator_id": operator_id,
            "operator_name": operator_name,
        }
        item = await self.dao.add_blacklist(data)
        return _serialize_blacklist(item)

    async def remove_blacklist(self, item_id: int) -> bool:
        """移除黑名单"""
        return await self.dao.remove_blacklist(item_id)

    async def toggle_blacklist_status(self, item_id: int, status: int) -> Optional[Dict[str, Any]]:
        """启停黑名单"""
        item = await self.dao.toggle_status(item_id, status)
        if item is None:
            return None
        return _serialize_blacklist(item)

    async def check_blacklisted(self, channel_code: str, blacklist_type: str, blacklist_value: str) -> bool:
        """检查指定值是否在黑名单中"""
        return await self.dao.is_blacklisted(channel_code, blacklist_type, blacklist_value)


# ════════════════════════════════════════════════════════════
# 统计服务
# ════════════════════════════════════════════════════════════


class B11ChannelStatisticsService:
    """渠道统计业务服务"""

    def __init__(self, dao: ChannelDailyStatDAO):
        self.dao = dao

    async def list_daily_stat(
        self,
        start_date: date,
        end_date: date,
        channel_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页查询每日统计"""
        items, total = await self.dao.list_by_date_range(
            start_date=start_date,
            end_date=end_date,
            channel_code=channel_code,
            page=page,
            page_size=page_size,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_serialize_daily_stat(item) for item in items],
        }

    async def get_summary(
        self,
        start_date: date,
        end_date: date,
        channel_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取渠道汇总统计"""
        return await self.dao.get_summary_by_date_range(
            start_date=start_date,
            end_date=end_date,
            channel_code=channel_code,
        )


# ════════════════════════════════════════════════════════════
# 配置日志服务
# ════════════════════════════════════════════════════════════


class B11ChannelConfigLogService:
    """渠道配置变更日志服务"""

    def __init__(self, dao: ChannelConfigLogDAO):
        self.dao = dao

    async def create_log(
        self,
        channel_code: str,
        config_key: str,
        old_value: str,
        old_value_label: str,
        new_value: str,
        new_value_label: str,
        operator_id: int,
        operator_name: str,
        operation_type: str,
        remark: str = "",
    ) -> Dict[str, Any]:
        """创建变更日志"""
        data = {
            "channel_code": channel_code,
            "config_key": config_key,
            "old_value": old_value,
            "old_value_label": old_value_label,
            "new_value": new_value,
            "new_value_label": new_value_label,
            "operator_id": operator_id,
            "operator_name": operator_name,
            "operation_type": operation_type,
            "remark": remark,
        }
        item = await self.dao.create_log(data)
        return _serialize_config_log(item)

    async def list_logs(
        self,
        channel_code: Optional[str] = None,
        operation_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页查询变更日志"""
        items, total = await self.dao.list_by_channel(
            channel_code=channel_code,
            operation_type=operation_type,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_serialize_config_log(item) for item in items],
        }