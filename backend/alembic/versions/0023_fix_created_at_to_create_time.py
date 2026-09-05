# @ai-generated
"""
0023 - fix created_at/updated_at -> create_time/update_time

S05 线上回归发现：多个迁移文件建表时使用 created_at/updated_at 列名，
但 ORM 基类 Base（src/db/base.py）定义的是 create_time/update_time，
导致所有 INSERT/UPDATE 报 "Unknown column 'create_time'"。

本迁移将以下 12 张表的 created_at/updated_at 重命名为 create_time/update_time：
  abnormal_order, abnormal_order_operation_log, click_log,
  commission_flow_validation_log, gaking_channel_blacklist,
  gaking_channel_config_log, gaking_channel_daily_stat,
  gaking_order_operation_log, gaking_user_message,
  order_refund_operation_log, scheduled_task_run_log, short_link

MySQL ALTER TABLE CHANGE COLUMN 重命名列时，该列上的索引会自动跟随更新。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers
revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

# 需修复的表清单（迁移建表时误用 created_at/updated_at）
TABLES = [
    "abnormal_order",
    "abnormal_order_operation_log",
    "click_log",
    "commission_flow_validation_log",
    "gaking_channel_blacklist",
    "gaking_channel_config_log",
    "gaking_channel_daily_stat",
    "gaking_order_operation_log",
    "gaking_user_message",
    "order_refund_operation_log",
    "scheduled_task_run_log",
    "short_link",
]


def _rename_columns(table: str, bind) -> None:
    """幂等重命名：仅当旧列存在且新列不存在时才执行，避免重复/部分执行报错"""
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns(table)}
    if "created_at" in cols and "create_time" not in cols:
        op.alter_column(
            table,
            "created_at",
            new_column_name="create_time",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            existing_server_default=sa.text("CURRENT_TIMESTAMP"),
        )
    if "updated_at" in cols and "update_time" not in cols:
        op.alter_column(
            table,
            "updated_at",
            new_column_name="update_time",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            existing_server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        )


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        _rename_columns(table, bind)


def downgrade() -> None:
    for table in TABLES:
        op.alter_column(
            table,
            "create_time",
            new_column_name="created_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            existing_server_default=sa.text("CURRENT_TIMESTAMP"),
        )
        op.alter_column(
            table,
            "update_time",
            new_column_name="updated_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            existing_server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        )
