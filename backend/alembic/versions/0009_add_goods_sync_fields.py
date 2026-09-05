# @ai-generated
"""add last_sync_time, popularity, last_visit_time, sync_status to goods_management (B16)

B16 商品预热定时任务新增字段：
- last_sync_time   最后同步时间（定时预热/刷新时更新）
- popularity       热度值（被用户访问次数，0=普通商品，>0=热门商品）
- last_visit_time  最后浏览时间（用于冷品清理判定）
- sync_status      同步状态：normal=正常，expired=过期（30天无浏览）

设计原则：不修改已基线固化的已有字段，仅 ADD COLUMN 扩展
执行方式：
  alembic upgrade head     # 加字段
  alembic downgrade -1     # 回滚删除字段

Revision ID: 0009_add_goods_sync_fields
Revises: 0008_add_message_templates
Create Date: 2026-08-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_add_goods_sync_fields"
down_revision: Union[str, None] = "0008_add_message_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """goods_management 表新增 4 个字段 + 1 个索引"""
    op.add_column(
        "goods_management",
        sa.Column(
            "last_sync_time",
            sa.DateTime(),
            nullable=True,
            comment="最后同步时间（定时预热/刷新时更新）",
        ),
    )
    op.add_column(
        "goods_management",
        sa.Column(
            "popularity",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="热度值(被访问次数)",
        ),
    )
    op.add_column(
        "goods_management",
        sa.Column(
            "last_visit_time",
            sa.DateTime(),
            nullable=True,
            comment="最后浏览时间（用于冷品清理判定）",
        ),
    )
    op.add_column(
        "goods_management",
        sa.Column(
            "sync_status",
            sa.String(length=16),
            nullable=False,
            server_default="normal",
            comment="同步状态: normal=正常 expired=过期",
        ),
    )
    # sync_status 单值索引 —— 按同步状态筛选
    op.create_index("idx_sync_status", "goods_management", ["sync_status"])


def downgrade() -> None:
    """回滚：删除 4 个字段 + 1 个索引"""
    op.drop_index("idx_sync_status", table_name="goods_management")
    op.drop_column("goods_management", "sync_status")
    op.drop_column("goods_management", "last_visit_time")
    op.drop_column("goods_management", "popularity")
    op.drop_column("goods_management", "last_sync_time")