# @ai-generated
"""
模型基类模块
复用 src/db/base.py 中的 Base 声明式基类及异步查询工具，
扩展 to_dict 序列化混入、软删除查询过滤、通用分页查询辅助方法
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Mapped

# 复用已有引擎逻辑，不可删除
from src.db.base import (
    Base as _DbBase,
    get_db,
    exec_query,
    exec_scalar,
    exec_fetch_all,
    exec_fetch_one,
    DatabaseManager,
)

logger = logging.getLogger("models.base")


class SerializableMixin:
    """通用序列化混入，为每个 Model 提供 to_dict() 方法"""

    def to_dict(self, exclude: Optional[set] = None) -> Dict[str, Any]:
        """将模型实例序列化为字典，自动处理 datetime / Decimal / bool

        Args:
            exclude: 需要排除的字段名集合
        Returns:
            可 JSON 序列化的字典
        """
        exclude = exclude or set()
        result: Dict[str, Any] = {}
        for column in self.__table__.columns:
            if column.name in exclude:
                continue
            value = getattr(self, column.name, None)
            if isinstance(value, datetime):
                result[column.name] = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, date):
                result[column.name] = value.isoformat()
            elif isinstance(value, Decimal):
                result[column.name] = float(value)
            elif isinstance(value, bool):
                result[column.name] = value
            else:
                result[column.name] = value
        return result


class SoftDeleteMixin:
    """软删除查询过滤混入，自动排除 is_delete=True 的记录"""

    @classmethod
    def filter_active(cls, stmt: Select) -> Select:
        """在查询语句上追加 is_delete=False 过滤条件"""
        return stmt.where(cls.is_delete == False)  # noqa: E712


async def paginate_query(
    session,
    query: Select,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Any], int]:
    """通用分页查询辅助

    Args:
        session: 异步数据库会话
        query: SQLAlchemy Select 查询语句（不含 limit/offset）
        page: 页码，从 1 开始
        page_size: 每页条数
    Returns:
        (当前页记录列表, 总记录数)
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20

    # 统计总数（提取查询主体做 count）
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    page_query = query.offset(offset).limit(page_size)
    result = await session.execute(page_query)
    items = result.scalars().all()

    return list(items), total


# 统一导出 Base —— 新模型统一继承此 Base
Base = _DbBase

__all__ = [
    "Base",
    "SerializableMixin",
    "SoftDeleteMixin",
    "paginate_query",
    "get_db",
    "exec_query",
    "exec_scalar",
    "exec_fetch_all",
    "exec_fetch_one",
    "DatabaseManager",
]
