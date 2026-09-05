# @ai-generated
"""
B07-1 退款逆向佣金冲减服务：新建逆向佣金冲减记录表

迁移内容：
1. 新建逆向佣金冲减记录表 gaking_reverse_commission_record
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gaking_reverse_commission_record",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键ID"),
        sa.Column("order_id", sa.BigInteger(), nullable=False, comment="关联订单ID"),
        sa.Column("out_order_no", sa.String(64), server_default="", comment="渠道订单号"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, server_default="0", comment="用户ID"),
        sa.Column("channel_code", sa.String(32), server_default="", comment="渠道标识"),
        sa.Column("original_commission", sa.Numeric(10, 2), nullable=False, server_default="0.00", comment="原始佣金金额(元)"),
        sa.Column("deducted_amount", sa.Numeric(10, 2), nullable=False, server_default="0.00", comment="实际扣减金额(元)"),
        sa.Column("flow_type", sa.String(32), server_default="", comment="原始流水类型：ORDER/SUPPLEMENT"),
        sa.Column("flow_transfer_status", sa.String(32), server_default="", comment="原始流水转账状态：PENDING/SUCCESS"),
        sa.Column("status", sa.String(32), nullable=False, server_default="IDENTIFIED", comment="冲减状态：IDENTIFIED/FROZEN/CLAWBACK_DONE/FAILED/ADJUSTED"),
        sa.Column("retry_count", sa.Integer(), server_default="0", comment="已重试次数"),
        sa.Column("max_retry", sa.Integer(), server_default="3", comment="最大重试次数"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息（MySQL 8.0.13+ TEXT 禁止默认值，置 NULL 代替）"),
        sa.Column("deduct_flow_id", sa.BigInteger(), nullable=True, default=None, comment="关联扣减流水ID"),
        sa.Column("operator_id", sa.BigInteger(), nullable=False, server_default="0", comment="操作人ID"),
        sa.Column("operator_name", sa.String(64), server_default="", comment="操作人姓名"),
        sa.Column("remark", sa.String(512), server_default="", comment="备注"),
        sa.Column("frozen_at", sa.DateTime(), nullable=True, comment="冻结时间"),
        sa.Column("clawback_at", sa.DateTime(), nullable=True, comment="回扣完成时间"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default="0", comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
        sa.Index("idx_order_id", "order_id"),
        sa.Index("idx_user_id", "user_id"),
        sa.Index("idx_status", "status"),
        sa.Index("idx_create_time", "create_time"),
        sa.Index("idx_status_create_time", "status", "create_time"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="逆向佣金冲减记录表",
    )


def downgrade():
    op.drop_table("gaking_reverse_commission_record")