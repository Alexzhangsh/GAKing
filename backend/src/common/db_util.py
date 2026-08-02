# @ai-generated
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from src.db.init_db import DatabaseManager


class DbUtil:
    @classmethod
    async def get_session(cls) -> AsyncSession:
        return DatabaseManager.get_session()

    @classmethod
    async def execute_scalar(cls, session: AsyncSession, stmt):
        result = await session.execute(stmt)
        return result.scalar()

    @classmethod
    async def execute_one(cls, session: AsyncSession, stmt):
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def execute_all(cls, session: AsyncSession, stmt):
        result = await session.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def execute_paginate(cls, session: AsyncSession, stmt: Select, page: int, page_size: int) -> Dict[str, Any]:
        offset = (page - 1) * page_size
        
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await cls.execute_scalar(session, count_stmt)
        
        stmt = stmt.offset(offset).limit(page_size)
        items = await cls.execute_all(session, stmt)
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": items,
        }

    @classmethod
    async def insert(cls, session: AsyncSession, model, **kwargs):
        instance = model(**kwargs)
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance

    @classmethod
    async def update_by_id(cls, session: AsyncSession, model, record_id: int, **kwargs):
        stmt = update(model).where(model.id == record_id, model.is_delete == False).values(**kwargs)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    @classmethod
    async def delete_by_id(cls, session: AsyncSession, model, record_id: int):
        stmt = update(model).where(model.id == record_id).values(is_delete=True)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    @classmethod
    async def hard_delete_by_id(cls, session: AsyncSession, model, record_id: int):
        stmt = delete(model).where(model.id == record_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    @classmethod
    async def get_by_id(cls, session: AsyncSession, model, record_id: int):
        stmt = select(model).where(model.id == record_id, model.is_delete == False)
        return await cls.execute_one(session, stmt)

    @classmethod
    async def get_by_field(cls, session: AsyncSession, model, field_name: str, value: Any):
        stmt = select(model).where(getattr(model, field_name) == value, model.is_delete == False)
        return await cls.execute_one(session, stmt)

    @classmethod
    async def exists(cls, session: AsyncSession, model, field_name: str, value: Any) -> bool:
        stmt = select(func.count()).where(getattr(model, field_name) == value, model.is_delete == False)
        count = await cls.execute_scalar(session, stmt)
        return count > 0

    @classmethod
    async def batch_insert(cls, session: AsyncSession, model, items: List[Dict[str, Any]]) -> List:
        instances = [model(**item) for item in items]
        session.add_all(instances)
        await session.commit()
        for instance in instances:
            await session.refresh(instance)
        return instances

    @classmethod
    async def transaction(cls, session: AsyncSession, func, *args, **kwargs):
        try:
            result = await func(session, *args, **kwargs)
            await session.commit()
            return result
        except Exception as e:
            await session.rollback()
            raise e

    @classmethod
    async def count(cls, session: AsyncSession, model, **filters) -> int:
        stmt = select(func.count()).select_from(model).where(model.is_delete == False)
        
        for key, value in filters.items():
            stmt = stmt.where(getattr(model, key) == value)
        
        return await cls.execute_scalar(session, stmt)

    @classmethod
    async def list_all(cls, session: AsyncSession, model, **filters) -> List:
        stmt = select(model).where(model.is_delete == False)
        
        for key, value in filters.items():
            stmt = stmt.where(getattr(model, key) == value)
        
        return await cls.execute_all(session, stmt)