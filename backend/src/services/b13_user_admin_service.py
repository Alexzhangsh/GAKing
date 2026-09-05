# @ai-generated
"""
B13-补全 C端用户管理后台 Service
业务逻辑层：用户列表、佣金账户查询、账户备注、冻结解冻
所有写操作自动记录审计日志
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.common.b14_audit_util import AuditLogger
from src.config.b13_b14_constants import (
    B13B14AuditAction,
    UserAdminStatus,
)
from src.dao.user_admin_profile_dao import UserAdminProfileDAO
from src.db.base import DatabaseManager

logger = logging.getLogger("services.b13_user_admin")


class B13UserAdminService:
    """C端用户管理后台 Service"""

    @classmethod
    async def list_users(
        cls,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """用户列表（联表查询佣金账户 + 管理档案）"""
        async with DatabaseManager.get_session() as session:
            dao = UserAdminProfileDAO(session)
            items, total = await dao.list_users_with_account(
                status=status,
                keyword=keyword,
                page=page,
                page_size=page_size,
            )
            return items, total

    @classmethod
    async def get_user_detail(
        cls, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """用户详情（佣金账户 + 管理档案）"""
        async with DatabaseManager.get_session() as session:
            dao = UserAdminProfileDAO(session)
            # 用 list_users_with_account 的逻辑，但只查单个 user_id
            # 这里简化处理：直接用 profile + account 分别查
            profile = await dao.get_by_user_id(user_id)

            # 查佣金账户
            from src.dao.user_commission_account_dao import UserCommissionAccountDAO
            account_dao = UserCommissionAccountDAO(session)
            account = await account_dao.get_by_user_id(user_id)

            if not account:
                return None

            return {
                "user_id": user_id,
                "total_balance": str(account.total_balance) if account.total_balance else "0.00",
                "available_balance": str(account.available_balance) if account.available_balance else "0.00",
                "frozen_balance": str(account.frozen_balance) if account.frozen_balance else "0.00",
                "cumulative_withdrawn": str(account.cumulative_withdrawn) if account.cumulative_withdrawn else "0.00",
                "cumulative_fee": str(account.cumulative_fee) if account.cumulative_fee else "0.00",
                "account_create_time": account.create_time.isoformat() if account.create_time else None,
                "status": profile.status if profile else "normal",
                "frozen_reason": profile.frozen_reason if profile else "",
                "frozen_time": profile.frozen_time.isoformat() if profile and profile.frozen_time else None,
                "admin_remark": profile.admin_remark if profile else "",
                "last_admin_id": profile.last_admin_id if profile else 0,
            }

    @classmethod
    async def update_remark(
        cls, user_id: int, admin_remark: str, admin_user_id: int = 0
    ) -> Dict[str, Any]:
        """更新用户备注（upsert）"""
        data = {
            "admin_remark": admin_remark,
            "last_admin_id": admin_user_id,
        }
        async with DatabaseManager.get_session() as session:
            dao = UserAdminProfileDAO(session)
            profile = await dao.upsert_by_user_id(user_id, data)

            # 审计日志
            await AuditLogger.log(
                action=B13B14AuditAction.USER_REMARK.value,
                target_type="user",
                target_id=user_id,
                details={"admin_remark": admin_remark[:200]},
                user_id=admin_user_id,
            )
            return {
                "user_id": user_id,
                "admin_remark": profile.admin_remark,
                "update_time": profile.update_time.isoformat() if profile.update_time else None,
            }

    @classmethod
    async def freeze_user(
        cls, user_id: int, frozen_reason: str, admin_user_id: int = 0
    ) -> Dict[str, Any]:
        """冻结用户"""
        data = {
            "status": UserAdminStatus.FROZEN.value,
            "frozen_reason": frozen_reason,
            "frozen_by": admin_user_id,
            "frozen_time": datetime.now(),
            "last_admin_id": admin_user_id,
        }
        async with DatabaseManager.get_session() as session:
            dao = UserAdminProfileDAO(session)
            profile = await dao.upsert_by_user_id(user_id, data)

            # 审计日志
            await AuditLogger.log(
                action=B13B14AuditAction.USER_FREEZE.value,
                target_type="user",
                target_id=user_id,
                details={
                    "frozen_reason": frozen_reason[:200],
                    "frozen_by": admin_user_id,
                },
                user_id=admin_user_id,
            )
            return {
                "user_id": user_id,
                "status": profile.status,
                "frozen_reason": profile.frozen_reason,
                "frozen_time": profile.frozen_time.isoformat() if profile.frozen_time else None,
            }

    @classmethod
    async def unfreeze_user(
        cls, user_id: int, admin_user_id: int = 0
    ) -> Dict[str, Any]:
        """解冻用户"""
        data = {
            "status": UserAdminStatus.NORMAL.value,
            "frozen_reason": "",
            "unfrozen_by": admin_user_id,
            "unfrozen_time": datetime.now(),
            "last_admin_id": admin_user_id,
        }
        async with DatabaseManager.get_session() as session:
            dao = UserAdminProfileDAO(session)
            profile = await dao.upsert_by_user_id(user_id, data)

            # 审计日志
            await AuditLogger.log(
                action=B13B14AuditAction.USER_UNFREEZE.value,
                target_type="user",
                target_id=user_id,
                details={
                    "unfrozen_by": admin_user_id,
                },
                user_id=admin_user_id,
            )
            return {
                "user_id": user_id,
                "status": profile.status,
                "unfrozen_time": profile.unfrozen_time.isoformat() if profile.unfrozen_time else None,
            }
