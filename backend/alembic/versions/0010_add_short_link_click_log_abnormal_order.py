# @ai-generated
"""add short_link, click_log, abnormal_order tables (B05-4)

B05-4 短链跟单系统新增 3 张表：
- short_link      短链映射表：短链 key → user_id, goods_id, expire_at
- click_log       点击行为日志表：记录每次短链点击的 UA、IP、访问时间
- abnormal_order  异常订单表：无法归属用户的订单，供运营人工复核

设计原则：不修改已有表，仅 CREATE TABLE 新建 3 张表
执行方式：
  alembic upgrade head     # 建表
  alembic downgrade -1     # 回滚删表

Revision ID: 0010_add_short_link_click_log_abnormal_order
Revises: 0009_add_goods_sync_fields
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_add_short_link_click_log_abnormal_order"
down_revision: Union[str, None] = "0009_add_goods_sync_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新建 3 张表：short_link / click_log / abnormal_order"""

    # ── 1. short_link 短链映射表 ──────────────────────────
    op.create_table(
        "short_link",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("short_key", sa.String(length=32), nullable=False, comment="短链唯一标识"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("goods_id", sa.String(length=128), nullable=False, comment="商品ID"),
        sa.Column("goods_title", sa.String(length=256), server_default="", comment="商品标题"),
        sa.Column("channel_code", sa.String(length=32), server_default="", comment="渠道标识"),
        sa.Column("source_url", sa.Text(), nullable=True, comment="原始CPS推广链接（MySQL 8.0.13+ TEXT 禁止默认值，置 NULL 代替空串）"),
        sa.Column("expire_at", sa.DateTime(), nullable=False, comment="过期时间"),
        sa.Column("click_count", sa.Integer(), server_default="0", comment="累计点击次数"),
        sa.Column("last_click_at", sa.DateTime(), nullable=True, comment="最后点击时间"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("is_delete", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_comment="短链映射表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_short_key", "short_link", ["short_key"], unique=True)
    op.create_index("idx_user_id", "short_link", ["user_id"])
    op.create_index("idx_goods_id", "short_link", ["goods_id"])
    op.create_index("idx_expire_at", "short_link", ["expire_at"])

    # ── 2. click_log 点击行为日志表 ────────────────────────
    op.create_table(
        "click_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("short_key", sa.String(length=32), nullable=False, comment="关联短链key"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("goods_id", sa.String(length=128), nullable=False, comment="商品ID"),
        sa.Column("goods_title", sa.String(length=256), server_default="", comment="商品标题"),
        sa.Column("source_channel", sa.String(length=32), server_default="", comment="来源渠道"),
        sa.Column("user_agent", sa.String(length=512), server_default="", comment="User-Agent"),
        sa.Column("ip_address", sa.String(length=64), server_default="", comment="IP地址"),
        sa.Column("referer_url", sa.String(length=1024), server_default="", comment="来源URL"),
        sa.Column("access_time", sa.DateTime(), nullable=False, comment="访问时间"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("is_delete", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_comment="点击行为日志表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_short_key", "click_log", ["short_key"])
    op.create_index("idx_user_id", "click_log", ["user_id"])
    op.create_index("idx_goods_id", "click_log", ["goods_id"])
    op.create_index("idx_access_time", "click_log", ["access_time"])
    op.create_index("idx_goods_access", "click_log", ["goods_id", "access_time"])

    # ── 3. abnormal_order 异常订单表 ───────────────────────
    op.create_table(
        "abnormal_order",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("out_order_no", sa.String(length=64), nullable=False, comment="渠道订单号"),
        sa.Column("channel_code", sa.String(length=32), server_default="", comment="渠道标识"),
        sa.Column("order_data", sa.Text(), nullable=True, comment="原始订单数据JSON（MySQL 8.0.13+ TEXT 禁止默认值，置 NULL 代替）"),
        sa.Column("goods_id", sa.String(length=128), server_default="", comment="商品ID"),
        sa.Column("goods_title", sa.String(length=256), server_default="", comment="商品标题"),
        sa.Column(
            "pay_amount", sa.Numeric(precision=10, scale=2), server_default="0.00", nullable=False, comment="支付金额(元)"
        ),
        sa.Column(
            "total_commission", sa.Numeric(precision=10, scale=2), server_default="0.00", nullable=False, comment="总佣金(元)"
        ),
        sa.Column("order_status", sa.String(length=32), server_default="", comment="渠道原始状态"),
        sa.Column("pay_time", sa.DateTime(), nullable=True, comment="支付时间"),
        sa.Column("abnormal_reason", sa.String(length=512), server_default="", comment="异常原因"),
        sa.Column("matched_click_key", sa.String(length=32), server_default="", comment="最近匹配短链key"),
        sa.Column("matched_user_id", sa.BigInteger(), server_default="0", comment="可能匹配的用户ID"),
        sa.Column(
            "review_status", sa.String(length=32), server_default="PENDING", nullable=False, comment="复核状态"
        ),
        sa.Column("review_remark", sa.String(length=512), server_default="", comment="复核备注"),
        sa.Column("reviewed_by", sa.BigInteger(), server_default="0", comment="复核人管理员ID"),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="复核时间"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("is_delete", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_comment="异常订单表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_out_order_no", "abnormal_order", ["out_order_no"], unique=True)
    op.create_index("idx_review_status", "abnormal_order", ["review_status"])
    op.create_index("idx_channel_code", "abnormal_order", ["channel_code"])
    op.create_index("idx_create_time", "abnormal_order", ["created_at"])
    op.create_index("idx_goods_id", "abnormal_order", ["goods_id"])


def downgrade() -> None:
    """回滚：删除 3 张表"""
    # 先删索引再删表（abnormal_order）
    op.drop_index("idx_goods_id", table_name="abnormal_order")
    op.drop_index("idx_create_time", table_name="abnormal_order")
    op.drop_index("idx_channel_code", table_name="abnormal_order")
    op.drop_index("idx_review_status", table_name="abnormal_order")
    op.drop_index("idx_out_order_no", table_name="abnormal_order")
    op.drop_table("abnormal_order")

    # click_log
    op.drop_index("idx_goods_access", table_name="click_log")
    op.drop_index("idx_access_time", table_name="click_log")
    op.drop_index("idx_goods_id", table_name="click_log")
    op.drop_index("idx_user_id", table_name="click_log")
    op.drop_index("idx_short_key", table_name="click_log")
    op.drop_table("click_log")

    # short_link
    op.drop_index("idx_expire_at", table_name="short_link")
    op.drop_index("idx_goods_id", table_name="short_link")
    op.drop_index("idx_user_id", table_name="short_link")
    op.drop_index("idx_short_key", table_name="short_link")
    op.drop_table("short_link")