#!/usr/bin/env python3
# @ai-generated
# ============================================================
# 金角大王CPS - 超级管理员账号 + 默认角色初始化脚本
#
# 功能：
#   1. 幂等创建「超级管理员」角色（permissions=["*"]，拥有全部权限）
#   2. 幂等创建超级管理员用户（bcrypt cost=12 哈希，与 B14PasswordUtil 一致）
#   3. 已存在则重置密码并绑定超管角色
#
# 运行环境：后端 Docker 容器内（已装 bcrypt + aiomysql）
# 运行方式：
#   docker compose exec backend python /app/scripts/init_super_admin.py \
#       --username admin --password 'YOUR_STRONG_PASSWORD'
#   或通过环境变量：
#   docker compose exec -e SUPER_ADMIN_PASSWORD='xxx' backend \
#       python /app/scripts/init_super_admin.py --username admin
#
# 安全：密码仅作为命令行参数/环境变量临时传入，不落盘、不入库明文
# ============================================================
import argparse
import asyncio
import json
import os
import sys

import aiomysql
import bcrypt

SUPER_ROLE_NAME = "超级管理员"
SUPER_ROLE_DESC = '拥有全部权限（permissions=["*"]）'
SUPER_PERMISSIONS = json.dumps(["*"], ensure_ascii=False)


def hash_password(plain: str) -> str:
    """bcrypt cost=12 哈希，与 src/common/b14_password_util.py B14PasswordUtil 一致"""
    if not plain:
        raise ValueError("密码不能为空")
    plain_bytes = plain.encode("utf-8")[:72]  # bcrypt 72 字节限制
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_bytes, salt).decode("utf-8")


async def init_super_admin(username: str, password: str, real_name: str) -> None:
    db_host = os.environ.get("DB_HOST", "")
    db_port = int(os.environ.get("DB_PORT", "3306"))
    db_user = os.environ.get("DB_USERNAME", "")
    db_pwd = os.environ.get("DB_PASSWORD", "")
    db_name = os.environ.get("DB_DATABASE", "")

    if not all([db_host, db_user, db_pwd, db_name]):
        print("[FAIL] 数据库环境变量缺失（DB_HOST/DB_USERNAME/DB_PASSWORD/DB_DATABASE）", file=sys.stderr)
        sys.exit(2)

    print(f"[INFO] 连接 MySQL {db_host}:{db_port}/{db_name} ...")
    conn = await aiomysql.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_pwd,
        db=db_name,
        charset="utf8mb4",
        autocommit=True,
    )

    try:
        cur = await conn.cursor()

        # 1. 幂等创建超管角色（role_name 唯一约束）
        await cur.execute(
            """INSERT INTO admin_role (role_name, role_desc, permissions, status, is_delete, create_time, update_time)
               VALUES (%s, %s, %s, 1, 0, NOW(), NOW())
               ON DUPLICATE KEY UPDATE
                 role_desc = VALUES(role_desc),
                 permissions = VALUES(permissions),
                 status = 1,
                 is_delete = 0,
                 update_time = NOW()""",
            (SUPER_ROLE_NAME, SUPER_ROLE_DESC, SUPER_PERMISSIONS),
        )
        await cur.execute(
            "SELECT id FROM admin_role WHERE role_name=%s AND is_delete=0",
            (SUPER_ROLE_NAME,),
        )
        row = await cur.fetchone()
        if not row:
            print("[FAIL] 超管角色创建/查询失败", file=sys.stderr)
            sys.exit(3)
        role_id = row[0]
        print(f"[OK] 超管角色就绪: id={role_id}, name={SUPER_ROLE_NAME}, permissions=['*']")

        # 2. 幂等创建超管用户
        await cur.execute(
            "SELECT id FROM admin_user WHERE username=%s AND is_delete=0",
            (username,),
        )
        row = await cur.fetchone()
        pwd_hash = hash_password(password)

        if row:
            user_id = row[0]
            await cur.execute(
                """UPDATE admin_user
                   SET password=%s, role_id=%s, real_name=%s, status=1, is_delete=0, update_time=NOW()
                   WHERE id=%s""",
                (pwd_hash, role_id, real_name, user_id),
            )
            print(f"[OK] 超管用户已存在，密码已重置: id={user_id}, username={username}")
        else:
            await cur.execute(
                """INSERT INTO admin_user
                     (username, password, real_name, phone, email, role_id, status, is_delete, create_time, update_time)
                   VALUES (%s, %s, %s, '', '', %s, 1, 0, NOW(), NOW())""",
                (username, pwd_hash, real_name, role_id),
            )
            user_id = cur.lastrowid
            print(f"[OK] 超管用户创建成功: id={user_id}, username={username}")

        # 3. 输出校验信息
        await cur.execute(
            """SELECT u.id, u.username, u.real_name, u.status, r.role_name, r.permissions
               FROM admin_user u
               LEFT JOIN admin_role r ON r.id = u.role_id
               WHERE u.username=%s AND u.is_delete=0""",
            (username,),
        )
        row = await cur.fetchone()
        if row:
            print(
                f"[VERIFY] id={row[0]} username={row[1]} real_name={row[2]} "
                f"status={row[3]} role={row[4]} permissions={row[5]}"
            )
        print("[DONE] 超管初始化完成。请使用该账号登录管理后台。")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化金角大王超级管理员账号")
    parser.add_argument("--username", default=os.environ.get("SUPER_ADMIN_USERNAME", "admin"),
                        help="超管用户名（默认 admin，或读 SUPER_ADMIN_USERNAME 环境变量）")
    parser.add_argument("--password", default=os.environ.get("SUPER_ADMIN_PASSWORD", ""),
                        help="超管密码（或读 SUPER_ADMIN_PASSWORD 环境变量；禁止使用弱密码）")
    parser.add_argument("--real-name", default="超级管理员", help="真实姓名")
    args = parser.parse_args()

    if not args.password:
        print("[FAIL] 必须通过 --password 或 SUPER_ADMIN_PASSWORD 环境变量提供密码", file=sys.stderr)
        sys.exit(1)
    if len(args.password) < 8:
        print("[FAIL] 密码长度不足 8 位（建议≥12位，含大小写数字符号）", file=sys.stderr)
        sys.exit(1)

    asyncio.run(init_super_admin(args.username, args.password, args.real_name))


if __name__ == "__main__":
    main()
