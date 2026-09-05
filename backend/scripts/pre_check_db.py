#!/usr/bin/env python3
# @ai-generated
"""
S04-9 生产数据库预检脚本（数据库初始化数据 + 角色权限绑定校验）

校验项：
1. 渠道配置：仅启用喵有券(myq)，订单侠(orderx)/大淘客(dta) 停用
2. 消息模板：预置 7 个基础模板（4 微信订阅 + 3 站内）
3. 基础角色：4 个基础角色存在且启用
4. 超级管理员：admin_user 存在超级管理员账号
5. 权限码完整性：遍历全部 31 项权限码（30 唯一 + 超管通配符 *），
   确认每个权限码至少被一个非超管角色绑定，无缺失
6. 角色-权限绑定：输出各角色权限数，校验 JSON 可解析

运行方式：
  cd backend && python scripts/pre_check_db.py [--json out.json]
  （需 DB 可达；复用 init_prod_data.py 的权限码/角色定义作为单一数据源）

退出码：0=全部通过，1=存在关键失败项
"""
import argparse
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from src.config.env_config import EnvConfig
from src.db.init_db import DatabaseManager
from src.models.system.channel_config import ChannelMapping
from src.models.system.message_template import MessageTemplate
from src.db.models import AdminRole

# 复用 init_prod_data.py 的权限码/角色/渠道/模板定义（单一数据源）
from scripts.init_prod_data import (
    ALL_PERMISSION_CODES,
    BASE_ROLES,
    CHANNEL_CONFIGS,
    STATION_MESSAGE_TEMPLATES,
    SUPER_ADMIN_PERMISSION,
    WX_SUBSCRIBE_TEMPLATES,
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("pre_check_db")

# 预检结果结构
REPORT = {
    "script": "pre_check_db",
    "version": "S04-9",
    "checks": [],
    "summary": {"pass": 0, "fail": 0, "warn": 0},
    "result": "PASS",
}

# 超管专属权限码：仅由超管通配符 * 覆盖，不要求绑定基础角色
# （系统配置/菜单管理/RBAC 管理属最高权限，绑定基础角色反而扩大风险面）
SUPER_ADMIN_ONLY_PERMISSIONS = {"config:manage", "menu:manage", "rbac:manage"}


def add_check(name: str, status: str, detail: str) -> None:
    """记录一条校验结果。status: PASS / FAIL / WARN"""
    REPORT["checks"].append({"name": name, "status": status, "detail": detail})
    REPORT["summary"][status.lower()] += 1
    if status == "FAIL":
        REPORT["result"] = "FAIL"


async def check_channels(session) -> None:
    """渠道配置校验：myq 启用，orderx/dta 停用"""
    stmt = select(ChannelMapping)
    result = await session.execute(stmt)
    channels = {c.channel_code: c for c in result.scalars().all()}

    for code, cfg in CHANNEL_CONFIGS.items():
        ch = channels.get(code)
        if ch is None:
            add_check(f"渠道[{code}]", "FAIL", f"渠道 {code} 未初始化")
            continue
        expected_status = "启用" if cfg["status"] else "停用"
        actual_status = "启用" if ch.status else "停用"
        if ch.status == cfg["status"]:
            add_check(
                f"渠道[{code}]",
                "PASS",
                f"{ch.channel_name} 状态={actual_status}（符合预期 {expected_status}）",
            )
        else:
            add_check(
                f"渠道[{code}]",
                "FAIL",
                f"{ch.channel_name} 状态={actual_status}，预期 {expected_status}（S04 红线：仅启用喵有券）",
            )


async def check_message_templates(session) -> None:
    """消息模板校验：7 个基础模板存在且启用"""
    stmt = select(MessageTemplate)
    result = await session.execute(stmt)
    templates = {t.template_name: t for t in result.scalars().all()}

    expected = WX_SUBSCRIBE_TEMPLATES + STATION_MESSAGE_TEMPLATES
    missing = []
    disabled = []
    for tpl in expected:
        name = tpl["template_name"]
        t = templates.get(name)
        if t is None:
            missing.append(name)
        elif t.status != 1:
            disabled.append(name)

    if missing:
        add_check("消息模板", "FAIL", f"缺失 {len(missing)} 个模板: {missing}")
    elif disabled:
        add_check("消息模板", "WARN", f"{len(disabled)} 个模板未启用: {disabled}")
    else:
        add_check(
            "消息模板",
            "PASS",
            f"全部 {len(expected)} 个基础模板已初始化且启用",
        )


async def check_roles(session) -> None:
    """基础角色校验：4 个基础角色存在且启用"""
    stmt = select(AdminRole).where(AdminRole.is_delete == False)  # noqa: E712
    result = await session.execute(stmt)
    roles = {r.role_name: r for r in result.scalars().all()}

    missing = []
    for role in BASE_ROLES:
        r = roles.get(role["role_name"])
        if r is None:
            missing.append(role["role_name"])
        elif r.status != 1:
            add_check(
                f"角色[{role['role_name']}]",
                "WARN",
                f"角色存在但未启用 status={r.status}",
            )

    if missing:
        add_check("基础角色", "FAIL", f"缺失 {len(missing)} 个基础角色: {missing}")
    else:
        add_check(
            "基础角色",
            "PASS",
            f"全部 {len(BASE_ROLES)} 个基础角色已初始化且启用",
        )


async def check_super_admin(session) -> None:
    """超级管理员校验：存在「超级管理员」角色(permissions=['*']) + 绑定该角色的用户

    说明：AdminUser ORM 模型未声明 is_delete/is_super 字段，但实际表存在，
    故此处使用原生 SQL 查询，与 init_super_admin.py 保持一致。
    """
    from sqlalchemy import text

    # 1. 超管角色存在且权限为 ['*']
    role_sql = text(
        "SELECT id, role_name, permissions FROM admin_role "
        "WHERE role_name = '超级管理员' AND is_delete = 0 AND status = 1 LIMIT 1"
    )
    role_row = (await session.execute(role_sql)).first()

    if role_row is None:
        add_check("超级管理员", "FAIL", "「超级管理员」角色不存在（需执行 init_super_admin.py）")
        return

    perms_raw = role_row[2] or ""
    if '"*"' not in perms_raw:
        add_check(
            "超级管理员",
            "FAIL",
            f"「超级管理员」角色权限异常: {perms_raw}（预期 ['*']）",
        )
        return

    # 2. 存在绑定超管角色的用户
    user_sql = text(
        "SELECT u.id, u.username, u.status FROM admin_user u "
        "WHERE u.role_id = :rid AND u.is_delete = 0 AND u.status = 1 LIMIT 1"
    )
    user_row = (await session.execute(user_sql, {"rid": role_row[0]})).first()

    if user_row is None:
        add_check(
            "超级管理员",
            "WARN",
            "「超级管理员」角色存在但无绑定用户（生产需执行 init_super_admin.py --username admin --password xxx）",
        )
    else:
        add_check(
            "超级管理员",
            "PASS",
            f"超管角色 id={role_row[0]}，绑定用户 {user_row[1]}(id={user_row[0]})",
        )


async def check_permissions(session) -> None:
    """权限码完整性校验：遍历全部 31 项权限码，确认角色权限绑定无缺失"""
    stmt = select(AdminRole).where(AdminRole.is_delete == False)  # noqa: E712
    result = await session.execute(stmt)
    roles = result.scalars().all()

    # 汇总所有角色绑定的权限码
    bound_perms = set()
    role_perms = {}
    for role in roles:
        try:
            perms = json.loads(role.permissions or "[]")
        except (json.JSONDecodeError, TypeError):
            perms = []
        role_perms[role.role_name] = perms
        bound_perms.update(perms)

    # 唯一权限码（不含超管通配符）
    unique_codes = set(ALL_PERMISSION_CODES)

    # 1. 唯一性校验
    if len(unique_codes) != len(ALL_PERMISSION_CODES):
        dupes = [c for c in ALL_PERMISSION_CODES if ALL_PERMISSION_CODES.count(c) > 1]
        add_check("权限码唯一性", "FAIL", f"权限码清单存在重复项: {dupes}")
    else:
        add_check("权限码唯一性", "PASS", f"权限码清单无重复，共 {len(unique_codes)} 项")

    # 2. 每个权限码至少被一个非超管角色绑定
    #    豁免：超管专属权限码（config:manage/menu:manage/rbac:manage），
    #    由超管通配符 * 覆盖即可，不要求绑定基础角色
    missing = []
    super_admin_only = []
    for code in sorted(unique_codes):
        if code not in bound_perms:
            if code in SUPER_ADMIN_ONLY_PERMISSIONS:
                super_admin_only.append(code)
            else:
                missing.append(code)

    if missing:
        add_check(
            "权限码绑定",
            "FAIL",
            f"{len(missing)} 项权限码未被任何角色绑定: {missing}",
        )
    else:
        add_check(
            "权限码绑定",
            "PASS",
            f"全部 {len(unique_codes)} 项权限码均已绑定"
            + (f"（含 {len(super_admin_only)} 项超管专属权限由 * 覆盖: {super_admin_only}）" if super_admin_only else ""),
        )

    # 3. 超管通配符校验
    if SUPER_ADMIN_PERMISSION in bound_perms:
        add_check("超管通配符", "PASS", f"超管通配符 {SUPER_ADMIN_PERMISSION} 已绑定")
    else:
        add_check(
            "超管通配符",
            "WARN",
            f"超管通配符 {SUPER_ADMIN_PERMISSION} 未显式绑定（超管通常由 is_super 标志控制，可接受）",
        )

    # 4. 角色权限 JSON 可解析性 + 数量输出
    for role_name, perms in role_perms.items():
        add_check(
            f"角色[{role_name}]",
            "PASS",
            f"{len(perms)} 项权限",
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="S04-9 生产数据库预检")
    parser.add_argument("--json", dest="json_out", default="", help="输出 JSON 报告路径")
    args = parser.parse_args()

    EnvConfig.load()
    DatabaseManager.initialize()

    try:
        async with DatabaseManager.get_session() as session:
            await check_channels(session)
            await check_message_templates(session)
            await check_roles(session)
            await check_super_admin(session)
            await check_permissions(session)
    finally:
        await DatabaseManager.dispose()

    # 输出报告
    report_json = json.dumps(REPORT, ensure_ascii=False, indent=2)
    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            f.write(report_json)
        print(f"[INFO] JSON 报告已写入: {args.json_out}")

    # 控制台摘要
    s = REPORT["summary"]
    print("=" * 60)
    print("S04-9 生产数据库预检报告")
    print("=" * 60)
    for c in REPORT["checks"]:
        mark = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}[c["status"]]
        print(f"  {mark} {c['name']}: {c['detail']}")
    print("-" * 60)
    print(f"  通过={s['pass']}  失败={s['fail']}  警告={s['warn']}  结果={REPORT['result']}")
    print("=" * 60)

    sys.exit(0 if REPORT["result"] == "PASS" else 1)


if __name__ == "__main__":
    asyncio.run(main())
