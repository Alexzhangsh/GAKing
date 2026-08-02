# @ai-generated
import logging
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import Column, DateTime, Boolean, BigInteger, text
from sqlalchemy.sql import Select
from sqlalchemy.orm import DeclarativeBase, Session

from src.db.init_db import DatabaseManager, get_db as _get_db

logger = logging.getLogger("db.base")


class Base(DeclarativeBase):
    __abstract__ = True

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    is_delete = Column(Boolean, default=False, nullable=False, comment="软删除：0-未删除 1-已删除")
    create_time = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")


async def get_db():
    async for session in _get_db():
        yield session


async def exec_query(
    session: Session,
    sql: str,
    params: Optional[dict] = None,
) -> list:
    try:
        result = await session.execute(text(sql), params or {})
        if result.returns_rows:
            return result.fetchall()
        return []
    except Exception as e:
        logger.error(f"exec_query failed: {e}", exc_info=True)
        raise


async def exec_scalar(
    session: Session,
    sql: str,
    params: Optional[dict] = None,
) -> Any:
    try:
        result = await session.execute(text(sql), params or {})
        row = result.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"exec_scalar failed: {e}", exc_info=True)
        raise


async def exec_fetch_all(
    session: Session,
    sql: str,
    params: Optional[dict] = None,
) -> list:
    return await exec_query(session, sql, params)


async def exec_fetch_one(
    session: Session,
    sql: str,
    params: Optional[dict] = None,
) -> Optional[Any]:
    try:
        result = await session.execute(text(sql), params or {})
        return result.fetchone()
    except Exception as e:
        logger.error(f"exec_fetch_one failed: {e}", exc_info=True)
        raise


__all__ = [
    "Base",
    "get_db",
    "exec_query",
    "exec_scalar",
    "exec_fetch_all",
    "exec_fetch_one",
    "DatabaseManager",
]
