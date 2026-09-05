# @ai-generated
"""add assigned_user_id to abnormal_order (B05-4-2)

B05-4-2 异常订单后台操作完善：
- 新增 assigned_user_id 字段，用于人工复核时手动指定归属用户

执行方式：
  alembic upgrade head     # 新增字段
  alembic downgrade -1     # 回滚删除字段

Revision ID: 0011_add_assigned_user_id_to_abnormal_order
Revises: 0010_add_short_link_click_log_abnormal_order
Create Date: 2026-08-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_add_assigned_user_id_to_abnormal_order"
down_revision: Union[str, None] = "0010_add_short_link_click_log_abnormal_order"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 assigned_user_id 字段"""
    op.add_column(
        "abnormal_order",
        sa.Column(
            "assigned_user_id",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
            comment="复核指定归属用户ID",
        ),
    )


def downgrade() -> None:
    """回滚删除 assigned_user_id 字段"""
    op.drop_column("abnormal_order", "assigned_user_id")