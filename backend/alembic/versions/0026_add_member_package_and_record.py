# @ai-generated
"""
0026 - add X02-1 member package and user member record tables

X02-1 会员套餐管理：
1. 新建会员套餐表 member_package
   - package_code 唯一，status 上下架，duration_days 有效期
   - member_commission_rate 会员分佣比例升级配置
2. 新建用户会员记录表 user_member_record
   - user_id 关联平台用户，status active/expired/revoked
   - package_name / member_commission_rate 快照

幂等：仅当表不存在时创建，避免重复执行报错。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers
revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    # ── 1. 会员套餐表 ────────────────────────────────────────
    if not _table_exists("member_package"):
        op.create_table(
            "member_package",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键ID"),
            sa.Column("package_code", sa.String(32), nullable=False, comment="套餐编码（唯一）"),
            sa.Column("package_name", sa.String(64), nullable=False, comment="套餐名称"),
            sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default="0.00", comment="套餐价格（元）"),
            sa.Column("duration_days", sa.Integer(), nullable=False, server_default="30", comment="有效期（天）"),
            sa.Column("member_commission_rate", sa.Numeric(5, 4), nullable=False, server_default="0.0000", comment="会员分佣比例(0~1)"),
            sa.Column("status", sa.Integer(), nullable=False, server_default="1", comment="上下架状态：1-上架 0-下架"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="排序号"),
            sa.Column("description", sa.String(512), server_default="", comment="套餐描述"),
            sa.Column("is_delete", sa.Boolean(), nullable=False, server_default="0", comment="软删除：0-未删除 1-已删除"),
            sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="创建时间"),
            sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
            sa.UniqueConstraint("package_code", name="uk_member_package_code"),
            sa.Index("idx_member_package_status", "status"),
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
            comment="会员套餐表",
        )

    # ── 2. 用户会员记录表 ────────────────────────────────────
    if not _table_exists("user_member_record"):
        op.create_table(
            "user_member_record",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键ID"),
            sa.Column("user_id", sa.BigInteger(), nullable=False, comment="平台用户ID"),
            sa.Column("package_id", sa.Integer(), nullable=False, comment="会员套餐ID"),
            sa.Column("package_name", sa.String(64), nullable=False, server_default="", comment="套餐名称快照"),
            sa.Column("member_commission_rate", sa.Numeric(5, 4), nullable=False, server_default="0.0000", comment="会员分佣比例快照(0~1)"),
            sa.Column("status", sa.String(16), nullable=False, server_default="active", comment="会员状态：active-生效中 expired-已到期 revoked-已撤销"),
            sa.Column("started_at", sa.DateTime(), nullable=False, comment="开通时间"),
            sa.Column("expire_at", sa.DateTime(), nullable=False, comment="到期时间"),
            sa.Column("order_id", sa.BigInteger(), nullable=True, comment="开通来源订单ID"),
            sa.Column("remark", sa.String(256), server_default="", comment="备注"),
            sa.Column("is_delete", sa.Boolean(), nullable=False, server_default="0", comment="软删除：0-未删除 1-已删除"),
            sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="创建时间"),
            sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
            sa.Index("idx_member_record_user_id", "user_id"),
            sa.Index("idx_member_record_status", "status"),
            sa.Index("idx_member_record_expire_at", "expire_at"),
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
            comment="用户会员开通/到期记录表",
        )


def downgrade() -> None:
    if _table_exists("user_member_record"):
        op.drop_table("user_member_record")
    if _table_exists("member_package"):
        op.drop_table("member_package")
