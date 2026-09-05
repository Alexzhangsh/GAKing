# @ai-generated
"""add reconciliation record and diff tables (B13)

新增 2 张全链路对账业务表（B13）：
- reconciliation_record   全链路对账批次表（四方核对汇总 + 执行状态）
- reconciliation_diff     全链路对账差异明细表（差异记录 + 人工复核调平）

四方核对：订单原始佣金 ↔ B12结算入账 ↔ B08资产账户余额 ↔ B10微信打款流水

执行方式：
  alembic upgrade head     # 建表
  alembic downgrade -1     # 回滚删除表

Revision ID: 0005_add_reconciliation_b13_tables
Revises: 0004_add_settlement_b12_tables
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_add_reconciliation_b13_tables"
down_revision: Union[str, None] = "0004_add_settlement_b12_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 2 张 B13 全链路对账业务表 + 索引"""

    # ============================================================
    # 1. reconciliation_record 全链路对账批次表
    # ============================================================
    op.create_table(
        "reconciliation_record",
        sa.Column(
            "id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "reconciliation_no",
            sa.String(length=64),
            nullable=False,
            comment="对账批次号",
        ),
        sa.Column("reconcile_date", sa.Date(), nullable=False, comment="对账日期"),
        sa.Column(
            "reconcile_type",
            sa.String(length=32),
            nullable=False,
            comment="对账类型：DAILY/MANUAL",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="对账状态：PENDING/RUNNING/SUCCESS/PARTIAL/FAILED",
        ),
        sa.Column("user_count", sa.Integer(), nullable=False, comment="对账用户数"),
        sa.Column("order_count", sa.Integer(), nullable=False, comment="对账订单数"),
        sa.Column("matched_count", sa.Integer(), nullable=False, comment="平账数"),
        sa.Column("diff_count", sa.Integer(), nullable=False, comment="差异数"),
        sa.Column(
            "total_order_commission",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="订单佣金总额(元)",
        ),
        sa.Column(
            "total_settlement_commission",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="结算入账总额(元)",
        ),
        sa.Column(
            "total_account_balance",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="账户余额总额(元)",
        ),
        sa.Column(
            "total_withdrawn",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="累计提现总额(元)",
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="对账开始时间"),
        sa.Column("completed_at", sa.DateTime(), nullable=True, comment="对账完成时间"),
        sa.Column("operator_id", sa.BigInteger(), nullable=True, comment="操作人ID"),
        sa.Column(
            "error_message", sa.String(length=1024), nullable=False, comment="失败原因"
        ),
        sa.Column("remark", sa.String(length=512), nullable=False, comment="备注说明"),
        sa.Column(
            "is_delete",
            sa.Boolean(),
            nullable=False,
            comment="软删除：0-未删除 1-已删除",
        ),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="全链路对账批次表（B13）",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # reconciliation_record 索引
    op.create_index(
        "idx_reconciliation_no",
        "reconciliation_record",
        ["reconciliation_no"],
        unique=True,
    )
    op.create_index("idx_rr_date", "reconciliation_record", ["reconcile_date"])
    op.create_index("idx_rr_status", "reconciliation_record", ["status"])
    op.create_index("idx_rr_create_time", "reconciliation_record", ["create_time"])

    # ============================================================
    # 2. reconciliation_diff 全链路对账差异明细表
    # ============================================================
    op.create_table(
        "reconciliation_diff",
        sa.Column(
            "id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "reconciliation_id",
            sa.BigInteger(),
            nullable=False,
            comment="关联对账批次ID",
        ),
        sa.Column("order_id", sa.BigInteger(), nullable=True, comment="关联订单ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="关联用户ID"),
        sa.Column(
            "settlement_id", sa.BigInteger(), nullable=True, comment="关联结算单ID"
        ),
        sa.Column(
            "withdraw_id", sa.BigInteger(), nullable=True, comment="关联提现申请ID"
        ),
        sa.Column(
            "diff_type", sa.String(length=64), nullable=False, comment="差异类型"
        ),
        sa.Column(
            "source_type",
            sa.String(length=32),
            nullable=False,
            comment="源端类型：ORDER/SETTLEMENT/ACCOUNT/WITHDRAW",
        ),
        sa.Column(
            "target_type",
            sa.String(length=32),
            nullable=False,
            comment="目标端类型：ORDER/SETTLEMENT/ACCOUNT/WITHDRAW",
        ),
        sa.Column(
            "source_amount",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="源端金额(元)",
        ),
        sa.Column(
            "target_amount",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="目标端金额(元)",
        ),
        sa.Column(
            "diff_amount",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="差异金额(元)",
        ),
        sa.Column(
            "alert_level",
            sa.String(length=32),
            nullable=False,
            comment="告警级别：INFO/WARNING/CRITICAL",
        ),
        sa.Column(
            "alert_sent",
            sa.String(length=8),
            nullable=False,
            comment="是否已推送告警：Y/N",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="复核状态：PENDING/REVIEWING/RESOLVED/IGNORED",
        ),
        sa.Column("review_user_id", sa.BigInteger(), nullable=True, comment="复核人ID"),
        sa.Column(
            "review_remark",
            sa.String(length=512),
            nullable=False,
            comment="复核备注（调平说明）",
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="复核时间"),
        sa.Column("remark", sa.Text(), nullable=True, comment="差异详情描述"),
        sa.Column(
            "is_delete",
            sa.Boolean(),
            nullable=False,
            comment="软删除：0-未删除 1-已删除",
        ),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="全链路对账差异明细表（B13）",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # reconciliation_diff 索引
    op.create_index(
        "idx_rd_reconciliation_id", "reconciliation_diff", ["reconciliation_id"]
    )
    op.create_index("idx_rd_order_id", "reconciliation_diff", ["order_id"])
    op.create_index("idx_rd_user_id", "reconciliation_diff", ["user_id"])
    op.create_index("idx_rd_diff_type", "reconciliation_diff", ["diff_type"])
    op.create_index("idx_rd_status", "reconciliation_diff", ["status"])
    op.create_index("idx_rd_alert_level", "reconciliation_diff", ["alert_level"])
    op.create_index("idx_rd_create_time", "reconciliation_diff", ["create_time"])


def downgrade() -> None:
    """回滚：删除 2 张 B13 业务表"""
    op.drop_table("reconciliation_diff")
    op.drop_table("reconciliation_record")
