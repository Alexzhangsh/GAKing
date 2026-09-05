# @ai-generated
"""add message_template + push_record + subscribe_binding tables (F04)

新增 F04 营销消息模块所需的三张表：
- gaking_message_template  消息模板表（微信订阅消息 + 站内消息）
- gaking_push_record       推送记录表
- gaking_subscribe_binding 订阅消息绑定表（用户授权记录）

设计原则：不修改任何已基线固化的 B01-B15 存量表，仅新建表
执行方式：
  alembic upgrade head     # 建表
  alembic downgrade -1     # 回滚删除表

Revision ID: 0008_add_message_templates
Revises: 0007_add_b13_b14_admin_tables
Create Date: 2026-08-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_add_message_templates"
down_revision: Union[str, None] = "0007_add_b13_b14_admin_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """建表：gaking_message_template + gaking_push_record + gaking_subscribe_binding"""

    # 1. 消息模板表
    op.create_table(
        "gaking_message_template",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("template_name", sa.String(length=128), nullable=False, comment="模板名称"),
        sa.Column("template_type", sa.SmallInteger(), nullable=False, server_default="1", comment="模板类型：1=微信订阅消息 2=站内消息"),
        sa.Column("tmpl_id", sa.String(length=128), nullable=False, server_default="", comment="微信订阅消息模板ID（type=1时必填）"),
        sa.Column("title", sa.String(length=256), nullable=False, server_default="", comment="消息标题"),
        sa.Column("content", sa.Text(), nullable=False, comment="消息内容（支持占位符 {{keyword1}}）"),
        sa.Column("keywords", sa.JSON(), nullable=True, comment="关键词列表（微信订阅消息用）"),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1", comment="状态：1=启用 0=停用"),
        sa.Column("remark", sa.String(length=512), nullable=False, server_default="", comment="备注"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="软删除标记"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_template_type", "template_type"),
        sa.Index("idx_template_status", "status"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="消息模板表（微信订阅消息 + 站内消息）",
    )

    # 2. 推送记录表
    op.create_table(
        "gaking_push_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.BigInteger(), nullable=False, server_default="0", comment="关联消息模板ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, server_default="0", comment="推送目标用户ID"),
        sa.Column("push_status", sa.SmallInteger(), nullable=False, server_default="3", comment="推送状态：1=成功 2=失败 3=待发送"),
        sa.Column("push_time", sa.DateTime(), nullable=True, comment="实际推送时间"),
        sa.Column("error_msg", sa.String(length=512), nullable=False, server_default="", comment="失败原因"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="软删除标记"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_push_template", "template_id"),
        sa.Index("idx_push_user", "user_id"),
        sa.Index("idx_push_status", "push_status"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="推送记录表",
    )

    # 3. 订阅消息绑定表
    op.create_table(
        "gaking_subscribe_binding",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, server_default="0", comment="C端用户ID"),
        sa.Column("template_id", sa.BigInteger(), nullable=False, server_default="0", comment="关联消息模板ID"),
        sa.Column("subscribe_status", sa.SmallInteger(), nullable=False, server_default="1", comment="订阅状态：1=已订阅 0=已取消"),
        sa.Column("subscribe_time", sa.DateTime(), nullable=True, comment="订阅时间"),
        sa.Column("expire_time", sa.DateTime(), nullable=True, comment="过期时间（微信订阅消息1次性模板有效期7天）"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="软删除标记"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "template_id", name="uq_user_template"),
        sa.Index("idx_sub_user", "user_id"),
        sa.Index("idx_sub_template", "template_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="订阅消息绑定表（用户授权记录）",
    )


def downgrade() -> None:
    """回滚：删除三张表"""
    op.drop_table("gaking_subscribe_binding")
    op.drop_table("gaking_push_record")
    op.drop_table("gaking_message_template")
