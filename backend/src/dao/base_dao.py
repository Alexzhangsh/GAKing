# @ai-generated
"""
通用异步 DAO 基类
封装全部表通用的增删改查、分页、软删除、批量操作能力
所有子类只需指定 model_class 即可获得完整数据访问能力
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlalchemy import Select, func, select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("dao.base")

T = TypeVar("T")


class BaseDAO:
    """通用异步 DAO 基类

    子类继承后设置 model_class 即可使用全部方法
    软删除过滤自动追加 is_delete=False，所有查询默认排除已删除记录
    """

    model_class: Type = None

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── 内部工具方法 ──────────────────────────────────────

    def _active_filter(self, stmt: Select) -> Select:
        """追加软删除过滤：is_delete = False"""
        return stmt.where(
            self.model_class.is_delete == False  # noqa: E712
        )

    def _active_query(self) -> Select:
        """构建已过滤软删除的基础查询"""
        return self._active_filter(select(self.model_class))

    # ── 1. 主键单条查询 ──────────────────────────────────

    async def get_by_id(self, item_id: int) -> Optional[T]:
        """按主键 ID 查询单条记录（自动过滤软删除）

        Args:
            item_id: 主键 ID
        Returns:
            模型实例 或 None
        """
        stmt = self._active_query().where(self.model_class.id == item_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── 2. 条件列表查询 ──────────────────────────────────

    async def list_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
    ) -> List[T]:
        """按条件查询列表（自动过滤软删除）

        Args:
            filters: 等值过滤条件，如 {"user_id": 10001, "status": 10}
            order_by: 排序字段，如 "-create_time" 降序，"create_time" 升序
        Returns:
            模型实例列表
        """
        stmt = self._active_query()
        if filters:
            conditions = [
                getattr(self.model_class, k) == v for k, v in filters.items()
            ]
            stmt = stmt.where(and_(*conditions))
        if order_by:
            col_name = order_by.lstrip("-")
            col = getattr(self.model_class, col_name)
            stmt = stmt.order_by(col.desc() if order_by.startswith("-") else col.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ── 3. 分页查询 ──────────────────────────────────────

    async def paginate_list(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
    ) -> tuple[List[T], int]:
        """分页查询（自动过滤软删除）

        Args:
            page: 页码，从 1 开始
            page_size: 每页条数
            filters: 等值过滤条件
            order_by: 排序字段
        Returns:
            (当前页记录列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query()
        if filters:
            conditions = [
                getattr(self.model_class, k) == v for k, v in filters.items()
            ]
            stmt = stmt.where(and_(*conditions))

        # 统计总数
        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        if order_by:
            col_name = order_by.lstrip("-")
            col = getattr(self.model_class, col_name)
            stmt = stmt.order_by(col.desc() if order_by.startswith("-") else col.asc())
        page_query = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    # ── 4. 单条新增 ──────────────────────────────────────

    async def create(self, data: Dict[str, Any]) -> T:
        """新增单条记录

        Args:
            data: 字段数据字典
        Returns:
            创建的模型实例（含自增 ID）
        """
        obj = self.model_class(**data)
        self.session.add(obj)
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "create 提交失败已回滚: %s", self.model_class.__name__, exc_info=True
            )
            raise
        return obj

    # ── 5. 批量插入 ──────────────────────────────────────

    async def batch_create(self, data_list: List[Dict[str, Any]]) -> List[T]:
        """批量插入多条记录

        Args:
            data_list: 字段数据字典列表
        Returns:
            创建的模型实例列表
        """
        objects = [self.model_class(**data) for data in data_list]
        self.session.add_all(objects)
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "batch_create 提交失败已回滚: %s",
                self.model_class.__name__,
                exc_info=True,
            )
            raise
        return objects

    # ── 6. 主键局部更新 ──────────────────────────────────

    async def update_by_id(
        self,
        item_id: int,
        data: Dict[str, Any],
    ) -> Optional[T]:
        """按主键 ID 局部更新字段

        Args:
            item_id: 主键 ID
            data: 需要更新的字段字典
        Returns:
            更新后的模型实例 或 None（记录不存在）
        """
        obj = await self.get_by_id(item_id)
        if obj is None:
            return None
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "update_by_id 提交失败已回滚: %s id=%s",
                self.model_class.__name__,
                item_id,
                exc_info=True,
            )
            raise
        return obj

    # ── 7. 软删除（单条） ────────────────────────────────

    async def logic_delete_by_id(self, item_id: int) -> bool:
        """按主键 ID 软删除（更新 is_delete=True、update_time）

        Args:
            item_id: 主键 ID
        Returns:
            是否删除成功
        """
        obj = await self.get_by_id(item_id)
        if obj is None:
            return False
        obj.is_delete = True
        obj.update_time = datetime.now()
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "logic_delete_by_id 提交失败已回滚: %s id=%s",
                self.model_class.__name__,
                item_id,
                exc_info=True,
            )
            raise
        return True

    # ── 8. 批量软删除 ────────────────────────────────────

    async def batch_logic_delete(self, item_ids: List[int]) -> int:
        """批量软删除（仅更新 is_delete=True、update_time）

        Args:
            item_ids: 主键 ID 列表
        Returns:
            实际删除的记录数
        """
        now = datetime.now()
        stmt = (
            update(self.model_class)
            .where(
                and_(
                    self.model_class.id.in_(item_ids),
                    self.model_class.is_delete == False,  # noqa: E712
                )
            )
            .values(is_delete=True, update_time=now)
        )
        result = await self.session.execute(stmt)
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "batch_logic_delete 提交失败已回滚: %s",
                self.model_class.__name__,
                exc_info=True,
            )
            raise
        return result.rowcount or 0
