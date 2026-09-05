# @ai-generated
"""add admin_menu table and seed superadmin (B14)

新增后台菜单元数据表（B14）：
- admin_menu   后台菜单树元数据（菜单-角色绑定通过 AdminRole.permissions JSON 实现）

同时 seed 默认超管角色（permissions=["*"]）+ 默认超管账号（admin）
确保 B14 RBAC 系统部署后立即可登录使用

执行方式：
  alembic upgrade head     # 建表 + seed
  alembic downgrade -1     # 回滚删除表（seed 数据保留，需手动清理）

Revision ID: 0006_add_admin_menu_b14
Revises: 0005_add_reconciliation_b13_tables
Create Date: 2026-08-03
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_add_admin_menu_b14"
down_revision: Union[str, None] = "0005_add_reconciliation_b13_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 默认超管配置（与 b14_constants.py 对齐）
_DEFAULT_ADMIN_USERNAME = "admin"
_DEFAULT_ADMIN_PASSWORD = "admin@12345"
_DEFAULT_ADMIN_ROLE_NAME = "超级管理员"
_DEFAULT_ADMIN_REAL_NAME = "系统超管"


def _hash_password(plain: str) -> str:
    """使用 bcrypt 库直接哈希密码（迁移 seed 用，规避 passlib 兼容问题）"""
    try:
        import bcrypt

        plain_bytes = plain.encode("utf-8")[:72]
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(plain_bytes, salt).decode("utf-8")
    except Exception:
        # bcrypt 不可用时降级到 sha256（仅 seed 兜底，生产环境必装 bcrypt）
        import hashlib

        return f"sha256${hashlib.sha256(plain.encode()).hexdigest()}"


def _ensure_admin_tables() -> None:
    """全新库兼容：admin_role / admin_user 表由应用启动 create_all 创建，
    迁移链中无对应建表迁移；全新库升级到本迁移时此处幂等预建（已存在则跳过）。
    生产库已应用本迁移（表由 create_all 或旧库提供），不受影响。
    （2026-09-05 发布测试发现：全新库从零 upgrade head 因缺表失败）"""
    from sqlalchemy import inspect as sa_inspect

    bind = op.get_bind()
    insp = sa_inspect(bind)
    if not insp.has_table("admin_role"):
        op.create_table(
            "admin_role",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("role_name", sa.String(64), nullable=False, comment="角色名称"),
            sa.Column("role_desc", sa.String(512), default="", comment="角色描述"),
            sa.Column("permissions", sa.Text(), default="", comment="权限列表JSON"),
            sa.Column("status", sa.Boolean(), default=True, nullable=False, comment="状态：0-禁用 1-启用"),
            sa.Column("is_delete", sa.Boolean(), default=False, nullable=False, comment="软删除：0-未删除 1-已删除"),
            sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
            sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
            sa.UniqueConstraint("role_name", name="uk_role_name"),
            comment="后台角色表",
        )
    if not insp.has_table("admin_user"):
        op.create_table(
            "admin_user",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(64), nullable=False, comment="用户名"),
            sa.Column("password", sa.String(256), nullable=False, comment="密码（bcrypt加密）"),
            sa.Column("real_name", sa.String(64), default="", comment="真实姓名"),
            sa.Column("phone", sa.String(32), default="", comment="手机号"),
            sa.Column("email", sa.String(128), default="", comment="邮箱"),
            sa.Column("role_id", sa.BigInteger(), nullable=False, comment="角色ID"),
            sa.Column("status", sa.Boolean(), default=True, nullable=False, comment="状态：0-禁用 1-启用"),
            sa.Column("is_delete", sa.Boolean(), default=False, nullable=False, comment="软删除：0-未删除 1-已删除"),
            sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
            sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
            sa.UniqueConstraint("username", name="uk_username"),
            sa.Index("idx_role_id", "role_id"),
            sa.Index("idx_status", "status"),
            comment="后台管理员表",
        )


def upgrade() -> None:
    """创建 admin_menu 表 + 索引 + seed 默认超管角色/账号"""
    # 全新库兼容：预建 admin_role / admin_user（幂等）
    _ensure_admin_tables()

    # ============================================================
    # 1. admin_menu 后台菜单元数据表（幂等：部分执行后重跑不撞表）
    # ============================================================
    bind = op.get_bind()
    from sqlalchemy import inspect as sa_inspect

    if not sa_inspect(bind).has_table("admin_menu"):
        op.create_table(
            "admin_menu",
            sa.Column(
                "id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"
            ),
            sa.Column(
                "parent_id",
                sa.BigInteger(),
                nullable=False,
                comment="父菜单ID，0表示顶级",
            ),
            sa.Column(
                "menu_name", sa.String(length=128), nullable=False, comment="菜单名称"
            ),
            sa.Column(
                "menu_code",
                sa.String(length=64),
                nullable=False,
                comment="菜单唯一编码（权限码）",
            ),
            sa.Column(
                "menu_path",
                sa.String(length=256),
                nullable=False,
                comment="前端路由路径",
            ),
            sa.Column(
                "menu_icon", sa.String(length=64), nullable=False, comment="菜单图标"
            ),
            sa.Column(
                "menu_type",
                sa.String(length=16),
                nullable=False,
                comment="菜单类型：directory/menu/button",
            ),
            sa.Column(
                "sort_num", sa.Integer(), nullable=False, comment="排序权重"
            ),
            sa.Column(
                "status",
                sa.Boolean(),
                nullable=False,
                comment="状态：True-启用 False-禁用",
            ),
            sa.Column(
                "remark", sa.String(length=512), nullable=False, comment="备注说明"
            ),
            sa.Column(
                "is_delete",
                sa.Boolean(),
                nullable=False,
                comment="软删除：0-未删除 1-已删除",
            ),
            sa.Column(
                "create_time", sa.DateTime(), nullable=False, comment="创建时间"
            ),
            sa.Column(
                "update_time", sa.DateTime(), nullable=False, comment="更新时间"
            ),
            sa.PrimaryKeyConstraint("id"),
            comment="后台菜单元数据表（B14）",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        # admin_menu 索引
        op.create_index(
            "uk_menu_code", "admin_menu", ["menu_code"], unique=True
        )
        op.create_index("idx_parent_id", "admin_menu", ["parent_id"])
        op.create_index("idx_status", "admin_menu", ["status"])
        op.create_index("idx_menu_type", "admin_menu", ["menu_type"])

    # ============================================================
    # 2. seed 默认超管角色（admin_role 表，幂等：已存在则跳过）
    # ============================================================
    bind = op.get_bind()
    # 检查超管角色是否已存在
    existing_role = bind.execute(
        sa.text(
            "SELECT id FROM admin_role WHERE role_name = :name AND is_delete = 0"
        ),
        {"name": _DEFAULT_ADMIN_ROLE_NAME},
    ).first()

    super_role_id = None
    if existing_role is None:
        # 插入超管角色
        bind.execute(
            sa.text(
                "INSERT INTO admin_role (role_name, role_desc, permissions, status, "
                "is_delete, create_time, update_time) "
                "VALUES (:name, :desc, :perms, 1, 0, NOW(), NOW())"
            ),
            {
                "name": _DEFAULT_ADMIN_ROLE_NAME,
                "desc": "系统默认超级管理员，拥有全部权限",
                "perms": json.dumps(["*"], ensure_ascii=False),
            },
        )
        super_role_id = bind.execute(
            sa.text(
                "SELECT id FROM admin_role WHERE role_name = :name AND is_delete = 0"
            ),
            {"name": _DEFAULT_ADMIN_ROLE_NAME},
        ).scalar()
    else:
        super_role_id = existing_role[0]

    # ============================================================
    # 3. seed 默认超管账号（admin_user 表，幂等：已存在则跳过）
    # ============================================================
    existing_user = bind.execute(
        sa.text(
            "SELECT id FROM admin_user WHERE username = :name AND is_delete = 0"
        ),
        {"name": _DEFAULT_ADMIN_USERNAME},
    ).first()

    if existing_user is None and super_role_id is not None:
        hashed = _hash_password(_DEFAULT_ADMIN_PASSWORD)
        bind.execute(
            sa.text(
                "INSERT INTO admin_user (username, password, real_name, phone, email, "
                "role_id, status, is_delete, create_time, update_time) "
                "VALUES (:username, :password, :real_name, '', '', :role_id, 1, 0, NOW(), NOW())"
            ),
            {
                "username": _DEFAULT_ADMIN_USERNAME,
                "password": hashed,
                "real_name": _DEFAULT_ADMIN_REAL_NAME,
                "role_id": super_role_id,
            },
        )

    # ============================================================
    # 4. seed 默认菜单数据（admin_menu 表）
    # ============================================================
    existing_menu = bind.execute(
        sa.text(
            "SELECT id FROM admin_menu WHERE menu_code = 'menu:dashboard' AND is_delete = 0"
        )
    ).first()

    if existing_menu is None:
        menus = [
            ("menu:dashboard", "仪表盘", "/dashboard", "dashboard", "menu", 1, 0),
            ("menu:order", "订单管理", "/order", "order", "menu", 2, 0),
            ("menu:withdraw", "提现管理", "/withdraw", "withdraw", "menu", 3, 0),
            ("menu:settlement", "结算管理", "/settlement", "settlement", "menu", 4, 0),
            (
                "menu:reconciliation",
                "对账管理",
                "/reconciliation",
                "reconciliation",
                "menu",
                5,
                0,
            ),
            ("menu:config", "系统配置", "/config", "config", "menu", 6, 0),
            ("menu:rbac", "权限管理", "/rbac", "rbac", "menu", 7, 0),
            ("menu:audit", "审计日志", "/audit", "audit", "menu", 8, 0),
        ]
        for code, name, path, icon, mtype, sort, parent in menus:
            bind.execute(
                sa.text(
                    "INSERT INTO admin_menu (parent_id, menu_name, menu_code, menu_path, "
                    "menu_icon, menu_type, sort_num, status, remark, is_delete, "
                    "create_time, update_time) "
                    "VALUES (:parent_id, :name, :code, :path, :icon, :mtype, :sort, "
                    "1, '', 0, NOW(), NOW())"
                ),
                {
                    "parent_id": parent,
                    "name": name,
                    "code": code,
                    "path": path,
                    "icon": icon,
                    "mtype": mtype,
                    "sort": sort,
                },
            )


def downgrade() -> None:
    """回滚：删除 admin_menu 表（seed 到 admin_role/admin_user 的数据保留）"""
    op.drop_table("admin_menu")
