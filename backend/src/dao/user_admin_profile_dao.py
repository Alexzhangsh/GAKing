# @ai-generated
"""
用户管理扩展表 DAO
继承 BaseDAO 通用能力，扩展用户管理业务专属查询方法
仅做数据存取，不包含任何业务计算逻辑
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select, func, or_

from src.dao.base_dao import BaseDAO
from src.models.business.user_admin_profile_model import UserAdminProfile
from src.models.business.user_commission_account_model import UserCommissionAccount

logger = logging.getLogger("dao.user_admin_profile")


class UserAdminProfileDAO(BaseDAO):
    """用户管理扩展表 DAO"""

    model_class = UserAdminProfile

    def __init__(self, session):
        super().__init__(session)

    # ── 专属扩展方法 ────────────────────────────────────

    async def get_by_user_id(self, user_id: int) -> Optional[UserAdminProfile]:
        """按 user_id 查询用户管理档案（一对一）"""
        stmt = self._active_query().where(UserAdminProfile.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_by_user_id(
        self, user_id: int, data: Dict[str, Any]
    ) -> UserAdminProfile:
        """按 user_id upsert（存在则更新，不存在则创建）"""
        existing = await self.get_by_user_id(user_id)
        if existing:
            return await self.update_by_id(existing.id, data)
        else:
            data["user_id"] = user_id
            return await self.create(data)

    async def list_users_with_account(
        self,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """联表查询用户管理档案 + 佣金账户（LEFT JOIN，user_admin_profile 可能不存在）

        返回字典列表，含 profile + account 字段
        """
        # 构建 LEFT JOIN 查询：user_commission_account LEFT JOIN user_admin_profile
        stmt = (
            select(
                UserCommissionAccount.user_id,
                UserCommissionAccount.total_balance,
                UserCommissionAccount.available_balance,
                UserCommissionAccount.frozen_balance,
                UserCommissionAccount.cumulative_withdrawn,
                UserCommissionAccount.cumulative_fee,
                UserCommissionAccount.create_time.label("account_create_time"),
                UserAdminProfile.status,
                UserAdminProfile.frozen_reason,
                UserAdminProfile.frozen_time,
                UserAdminProfile.admin_remark,
                UserAdminProfile.last_admin_id,
            )
            .outerjoin(
                UserAdminProfile,
                UserCommissionAccount.user_id == UserAdminProfile.user_id,
            )
            .where(UserCommissionAccount.is_delete == False)  # noqa: E712
        )

        # 筛选条件
        if status:
            if status == "normal":
                # normal 状态包含：profile.status='normal' 或 profile 不存在
                stmt = stmt.where(
                    or_(
                        UserAdminProfile.status == "normal",
                        UserAdminProfile.status.is_(None),
                    )
                )
            else:
                stmt = stmt.where(UserAdminProfile.status == status)

        # 统计总数
        count_stmt = (
            select(func.count())
            .select_from(UserCommissionAccount)
            .outerjoin(
                UserAdminProfile,
                UserCommissionAccount.user_id == UserAdminProfile.user_id,
            )
            .where(UserCommissionAccount.is_delete == False)  # noqa: E712
        )
        if status:
            if status == "normal":
                count_stmt = count_stmt.where(
                    or_(
                        UserAdminProfile.status == "normal",
                        UserAdminProfile.status.is_(None),
                    )
                )
            else:
                count_stmt = count_stmt.where(UserAdminProfile.status == status)

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # 分页
        offset = (page - 1) * page_size
        page_stmt = stmt.order_by(
            UserCommissionAccount.create_time.desc()
        ).offset(offset).limit(page_size)
        result = await self.session.execute(page_stmt)
        rows = result.all()

        # 转为字典列表
        items = []
        for row in rows:
            items.append(
                {
                    "user_id": row.user_id,
                    "total_balance": str(row.total_balance) if row.total_balance else "0.00",
                    "available_balance": str(row.available_balance) if row.available_balance else "0.00",
                    "frozen_balance": str(row.frozen_balance) if row.frozen_balance else "0.00",
                    "cumulative_withdrawn": str(row.cumulative_withdrawn) if row.cumulative_withdrawn else "0.00",
                    "cumulative_fee": str(row.cumulative_fee) if row.cumulative_fee else "0.00",
                    "account_create_time": row.account_create_time.isoformat() if row.account_create_time else None,
                    "status": row.status or "normal",
                    "frozen_reason": row.frozen_reason or "",
                    "frozen_time": row.frozen_time.isoformat() if row.frozen_time else None,
                    "admin_remark": row.admin_remark or "",
                    "last_admin_id": row.last_admin_id or 0,
                }
            )

        return items, total
