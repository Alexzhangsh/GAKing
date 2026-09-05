# @ai-generated
"""
0025 - add F04-2 channel commission strategy tables

F04-2 渠道佣金策略可视化配置：
1. 新建渠道佣金策略主表 gaking_channel_commission_strategy
   - channel_code 唯一（多渠道独立分佣）
   - enabled 生效开关 / tier_dimension 阶梯维度
2. 新建阶梯佣金明细表 gaking_channel_commission_tier
   - strategy_id 关联主表，user_type 区分普通用户/付费会员
   - tier_min/tier_max 阶梯区间，user/platform 双比例

幂等：仅当表不存在时创建，避免重复执行报错。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers
revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    # ── 1. 渠道佣金策略主表 ────────────────────────────────
    if not _table_exists("gaking_channel_commission_strategy"):
        op.create_table(
            "gaking_channel_commission_strategy",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键ID"),
            sa.Column("channel_code", sa.String(32), nullable=False, comment="渠道标识：myq-喵有券 / orderx-订单侠 / dta-大淘客"),
            sa.Column("strategy_name", sa.String(128), nullable=False, server_default="", comment="策略名称"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="0", comment="策略生效开关：True-生效 False-停用"),
            sa.Column("tier_dimension", sa.Integer(), nullable=False, server_default="1", comment="阶梯维度：1-按订单金额 2-按订单数量"),
            sa.Column("remark", sa.String(512), server_default="", comment="备注说明"),
            sa.Column("is_delete", sa.Boolean(), nullable=False, server_default="0", comment="软删除：0-未删除 1-已删除"),
            sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="创建时间"),
            sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
            sa.UniqueConstraint("channel_code", name="uk_strategy_channel_code"),
            sa.Index("idx_strategy_channel_code", "channel_code"),
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
            comment="渠道佣金策略主表",
        )

    # ── 2. 阶梯佣金明细表 ──────────────────────────────────
    if not _table_exists("gaking_channel_commission_tier"):
        op.create_table(
            "gaking_channel_commission_tier",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键ID"),
            sa.Column("strategy_id", sa.Integer(), nullable=False, comment="策略主表ID"),
            sa.Column("user_type", sa.Integer(), nullable=False, comment="用户类型：1-普通用户 2-付费会员"),
            sa.Column("tier_name", sa.String(64), server_default="", comment="阶梯名称"),
            sa.Column("tier_min", sa.Numeric(12, 2), nullable=False, server_default="0.00", comment="阶梯下限（含）"),
            sa.Column("tier_max", sa.Numeric(12, 2), nullable=False, server_default="0.00", comment="阶梯上限（不含），0表示无上限"),
            sa.Column("user_commission_rate", sa.Numeric(5, 4), nullable=False, server_default="0.0000", comment="用户返利比例(0~1)"),
            sa.Column("platform_retention_rate", sa.Numeric(5, 4), nullable=False, server_default="0.0000", comment="平台留存比例(0~1)"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="排序号"),
            sa.Column("is_delete", sa.Boolean(), nullable=False, server_default="0", comment="软删除：0-未删除 1-已删除"),
            sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="创建时间"),
            sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
            sa.Index("idx_tier_strategy_id", "strategy_id"),
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
            comment="渠道佣金阶梯明细表",
        )


def downgrade() -> None:
    if _table_exists("gaking_channel_commission_tier"):
        op.drop_table("gaking_channel_commission_tier")
    if _table_exists("gaking_channel_commission_strategy"):
        op.drop_table("gaking_channel_commission_strategy")
