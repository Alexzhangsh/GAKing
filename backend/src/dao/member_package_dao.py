# @ai-generated
"""
X02-1 会员套餐 DAO（新建文件）
继承 BaseDAO；提供套餐分页查询、按编码查询、上架套餐列表能力
仅做数据存取，不含业务逻辑
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select

from src.dao.base_dao import BaseDAO
from src.models.business.member_package_model import MemberPackage

logger = logging.getLogger("dao.member_package")


class MemberPackageDAO(BaseDAO):
    """会员套餐 DAO"""

    model_class = MemberPackage

    # ── 按编码查询 ────────────────────────────────────────

    async def get_by_code(self, package_code: str) -> Optional[MemberPackage]:
        """按套餐编码查询（自动过滤软删除）"""
        stmt = self._active_query().where(
            MemberPackage.package_code == package_code
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── 分页查询 ──────────────────────────────────────────

    async def paginate_packages(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[List[MemberPackage], int]:
        """分页查询套餐（支持上下架状态 / 名称编码关键字筛选）"""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query()
        conditions = []
        if status is not None:
            conditions.append(MemberPackage.status == status)
        if keyword:
            like = f"%{keyword}%"
            conditions.append(
                or_(
                    MemberPackage.package_name.like(like),
                    MemberPackage.package_code.like(like),
                )
            )
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(
                MemberPackage.sort_order.asc(),
                MemberPackage.create_time.desc(),
            )
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    # ── 上架套餐列表 ──────────────────────────────────────

    async def list_on_shelf(self) -> List[MemberPackage]:
        """查询全部上架套餐（按排序号升序）"""
        stmt = (
            self._active_query()
            .where(MemberPackage.status == 1)
            .order_by(MemberPackage.sort_order.asc(), MemberPackage.create_time.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
