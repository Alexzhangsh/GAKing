# @ai-generated
"""
异常订单表 DAO
继承 BaseDAO 通用能力，扩展异常订单专属查询方法
仅做数据存取，不包含任何业务计算逻辑
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_, func, or_

from src.dao.base_dao import BaseDAO
from src.models.business.abnormal_order_model import AbnormalOrder

logger = logging.getLogger("dao.abnormal_order")


class AbnormalOrderDAO(BaseDAO):
    """异常订单 DAO"""

    model_class = AbnormalOrder

    def __init__(self, session):
        super().__init__(session)

    async def get_by_out_order_no(self, out_order_no: str) -> Optional[AbnormalOrder]:
        """按渠道订单号唯一查询

        Args:
            out_order_no: 渠道订单号
        Returns:
            AbnormalOrder 实例 或 None
        """
        stmt = self._active_query().where(AbnormalOrder.out_order_no == out_order_no)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def paginate_list(
        self,
        page: int = 1,
        page_size: int = 20,
        review_status: Optional[str] = None,
        channel_code: Optional[str] = None,
        keyword: Optional[str] = None,
        order_by: str = "-create_time",
    ) -> Tuple[List[AbnormalOrder], int]:
        """分页查询异常订单（支持多条件筛选）

        Args:
            page: 页码
            page_size: 每页条数
            review_status: 复核状态筛选
            channel_code: 渠道筛选
            keyword: 搜索关键词（商品标题/订单号）
            order_by: 排序字段
        Returns:
            (记录列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query()

        conditions = []
        if review_status:
            conditions.append(AbnormalOrder.review_status == review_status)
        if channel_code:
            conditions.append(AbnormalOrder.channel_code == channel_code)
        if keyword:
            conditions.append(
                or_(
                    AbnormalOrder.goods_title.ilike(f"%{keyword}%"),
                    AbnormalOrder.out_order_no.ilike(f"%{keyword}%"),
                )
            )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # 统计总数
        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 排序
        col_name = order_by.lstrip("-")
        col = getattr(self.model_class, col_name, None)
        if col is not None:
            stmt = stmt.order_by(
                col.desc() if order_by.startswith("-") else col.asc()
            )

        # 分页
        offset = (page - 1) * page_size
        page_query = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    async def review(
        self,
        item_id: int,
        review_status: str,
        review_remark: str,
        reviewed_by: int,
        assigned_user_id: int = 0,
    ) -> Optional[AbnormalOrder]:
        """复核异常订单（支持手动指定归属用户）

        Args:
            item_id: 记录ID
            review_status: 复核状态
            review_remark: 复核备注
            reviewed_by: 复核人管理员ID
            assigned_user_id: 手动指定归属用户ID（>0 时更新）
        Returns:
            更新后的异常订单实例 或 None
        """
        update_data: Dict[str, Any] = {
            "review_status": review_status,
            "review_remark": review_remark,
            "reviewed_by": reviewed_by,
            "reviewed_at": datetime.now(),
        }
        if assigned_user_id > 0:
            update_data["assigned_user_id"] = assigned_user_id
        return await self.update_by_id(item_id, update_data)

    async def update_review(
        self,
        item_id: int,
        assigned_user_id: int = 0,
        review_remark: str = "",
    ) -> Optional[AbnormalOrder]:
        """复核后修改异常订单归属（编辑场景）

        Args:
            item_id: 记录ID
            assigned_user_id: 手动指定归属用户ID（>0 时更新）
            review_remark: 复核备注
        Returns:
            更新后的异常订单实例 或 None
        """
        update_data: Dict[str, Any] = {}
        if assigned_user_id > 0:
            update_data["assigned_user_id"] = assigned_user_id
        if review_remark:
            update_data["review_remark"] = review_remark
        if not update_data:
            return await self.get_by_id(item_id)
        # 更新 reviewed_at 标记最后编辑时间
        update_data["reviewed_at"] = datetime.now()
        return await self.update_by_id(item_id, update_data)

    async def count_by_review_status(self) -> Dict[str, int]:
        """统计各复核状态的异常订单数量"""
        stmt = self._active_query()
        # 此处使用简单分组查询
        count_query = (
            select(AbnormalOrder.review_status, func.count())
            .where(AbnormalOrder.is_delete == False)  # noqa: E712
            .group_by(AbnormalOrder.review_status)
        )
        result = await self.session.execute(count_query)
        counts: Dict[str, int] = {}
        for row in result.all():
            counts[str(row[0])] = int(row[1])
        return counts

    async def count_by_create_time(self, since: datetime) -> int:
        """统计指定时间之后新增的异常订单数量

        Args:
            since: 起始时间
        Returns:
            异常订单数量
        """
        stmt = (
            select(func.count())
            .where(
                and_(
                    AbnormalOrder.is_delete == False,  # noqa: E712
                    AbnormalOrder.create_time >= since,
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_by_review_status_simple(self, status: str) -> int:
        """按复核状态统计异常订单数量

        Args:
            status: 复核状态（PENDING/REVIEWED/IGNORED）
        Returns:
            该状态异常订单数量
        """
        stmt = (
            select(func.count())
            .where(
                and_(
                    AbnormalOrder.is_delete == False,  # noqa: E712
                    AbnormalOrder.review_status == status,
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0