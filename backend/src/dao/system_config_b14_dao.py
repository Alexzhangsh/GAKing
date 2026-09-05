# @ai-generated
"""
系统配置 DAO（B14 新建，不修改 B01-B13 基线，不复用已损坏的 system_config_util.py）
继承 BaseDAO；操作 src/models/system/system_config.py 中的 SystemConfig 模型
提供按 key 查询、全量查询、upsert（存在则更新/不存在则创建）
仅做数据存取，不含业务逻辑
"""
import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.models.system.system_config import SystemConfig

logger = logging.getLogger("dao.system_config_b14")


class SystemConfigB14DAO(BaseDAO):
    """系统配置 DAO（B14 新建，使用迁移后的 SystemConfig 模型）"""

    model_class = SystemConfig

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_key(self, config_key: str) -> Optional[SystemConfig]:
        """按配置 key 查询（自动过滤软删除）

        Args:
            config_key: 配置唯一键名
        Returns:
            配置实例 或 None
        """
        stmt = self._active_query().where(SystemConfig.config_key == config_key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all_configs(self) -> List[SystemConfig]:
        """查询全部启用配置（加载缓存用）

        Returns:
            配置列表
        """
        stmt = self._active_query()
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_by_key(
        self,
        config_key: str,
        config_value: str,
        config_name: str = "",
        remark: str = "",
    ) -> SystemConfig:
        """按 key upsert 配置（存在则更新，不存在则创建）

        Args:
            config_key: 配置键
            config_value: 配置值
            config_name: 配置名称（新建时使用）
            remark: 备注（新建时使用）
        Returns:
            配置实例
        """
        existing = await self.get_by_key(config_key)
        if existing is not None:
            existing.config_value = config_value
            if config_name:
                existing.config_name = config_name
            if remark:
                existing.remark = remark
            try:
                await self.session.flush()
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                logger.warning(
                    "upsert_by_key 更新提交失败: key=%s", config_key, exc_info=True
                )
                raise
            return existing

        # 新建
        data = {
            "config_key": config_key,
            "config_value": config_value,
            "config_name": config_name or config_key,
            "remark": remark,
        }
        return await self.create(data)

    async def list_with_pagination(
        self,
        config_key: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple:
        """分页查询配置列表

        Args:
            config_key: 配置键模糊筛选
            page: 页码
            page_size: 每页条数
        Returns:
            (配置列表, 总数)
        """
        from sqlalchemy import func

        stmt = self._active_query()
        if config_key:
            stmt = stmt.where(SystemConfig.config_key.like(f"%{config_key}%"))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(SystemConfig.id.asc()).offset(offset).limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())
        return items, total
