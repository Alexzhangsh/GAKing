#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S07 权限隔离修复验证脚本（本地单元级，不依赖真实DB）
验证：C端用户 token（role_id=0）即使 user_id 与管理员 ID 碰撞，也无法获得后台权限
"""
import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "backend")

from src.common.auth_util import RbacUtil


async def main():
    passed = 0
    failed = 0

    def check(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [PASS] {name}  {detail}")
        else:
            failed += 1
            print(f"  [FAIL] {name}  {detail}")

    # ── 场景1: C端用户 role_id=0 且 user_id=1（与超管ID碰撞）→ 必须无权限 ──
    with patch("src.common.auth_util.DatabaseManager") as mock_db:
        # 即使 DB 中存在 AdminUser id=1（超管），role_id=0 也必须直接拒绝
        perms = await RbacUtil.get_user_permissions(1, role_id=0)
        check("C端用户(user_id=1,role_id=0)无后台权限", perms == [], f"perms={perms}")
        mock_db.get_session.assert_not_called()

    # ── 场景2: 管理员 role_id=1 正常查询权限 ──
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)

    admin_user = MagicMock()
    admin_user.id = 1
    admin_user.role_id = 1
    admin_role = MagicMock()
    admin_role.permissions = '["*"]'

    async def fake_execute(stmt):
        if "AdminUser" in str(stmt):
            r = MagicMock()
            r.scalar_one_or_none.return_value = admin_user
            return r
        r = MagicMock()
        r.scalar_one_or_none.return_value = admin_role
        return r

    session.execute = fake_execute

    with patch("src.common.auth_util.DatabaseManager") as mock_db:
        mock_db.get_session.return_value = cm
        perms = await RbacUtil.get_user_permissions(1, role_id=1)
        check("管理员(user_id=1,role_id=1)获得权限", perms == ["*"], f"perms={perms}")

    # ── 场景3: has_any_permission 对 C端用户返回 False ──
    with patch("src.common.auth_util.DatabaseManager") as mock_db:
        ok = await RbacUtil.has_any_permission(1, ["dashboard:view"], role_id=0)
        check("has_any_permission(C端)返回False", ok is False)

    # ── 场景4: 无 role_id 参数（默认0）→ 拒绝（安全默认） ──
    with patch("src.common.auth_util.DatabaseManager") as mock_db:
        perms = await RbacUtil.get_user_permissions(1)
        check("默认role_id=0安全拒绝", perms == [])

    print(f"\n结果: 通过={passed} 失败={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
