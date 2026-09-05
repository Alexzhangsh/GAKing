# @ai-generated
"""0000 - ensure runtime tables (create_all 依赖表预建)

背景：项目存在 5 张由「应用启动 create_all」创建、迁移链从未建表的运行时表：
  - audit_logs            审计日志（src/db/models.py）
  - gaking_task_status    定时任务执行状态（src/db/models.py）
  - miniapp_user          小程序C端用户（src/models/business/miniapp_user_model.py）
  - track_event           埋点事件（src/models/business/track_event_model.py）
  - withdraw_review_log   提现审核日志（src/models/business/withdraw_review_log_model.py）

生产库由旧库演化（应用曾 create_all 建表）掩盖了该缺陷；全新库从零 upgrade head
必在此类表被引用时报 1146。本迁移在迁移链最前幂等预建这 5 张表（仅缺失时建，
不触碰迁移链负责的其他表），使全新库可完整升级。

（2026-09-05 发布测试发现：全新库迁移链在 0027/审计接口等环节因缺表失败）

执行方式：alembic upgrade head
"""
import alembic.op as op
from sqlalchemy import inspect

# revision identifiers
revision = "0000_ensure_runtime_tables"
down_revision = None
branch_labels = None
depends_on = None

# 运行时表清单（模型已注册到 Base.metadata）
RUNTIME_TABLES = [
    "audit_logs",
    "gaking_task_status",
    "miniapp_user",
    "track_event",
    "withdraw_review_log",
]


def upgrade() -> None:
    # 导入模型模块，确保对应 Table 注册进 Base.metadata（仅注册，不触发建表）
    import src.db.models  # noqa: F401  (admin_role/admin_user/audit_logs/gaking_task_status)
    import src.models.business.miniapp_user_model  # noqa: F401
    import src.models.business.track_event_model  # noqa: F401
    import src.models.business.withdraw_review_log_model  # noqa: F401

    from src.db.base import Base

    bind = op.get_bind()
    insp = inspect(bind)
    missing = [t for t in RUNTIME_TABLES if not insp.has_table(t)]
    if not missing:
        print("[0000] 运行时表已全部存在，跳过")
        return
    # 只建缺失的运行时表，其余表留给各自迁移（避免与迁移链建表冲突）
    tables = [Base.metadata.tables[t] for t in missing if t in Base.metadata.tables]
    Base.metadata.create_all(bind, tables=tables, checkfirst=True)
    print(f"[0000] 已预建运行时表: {missing}")


def downgrade() -> None:
    # 不删除：运行时表由应用 create_all 维护，回滚迁移链不应删表
    print("[0000] 跳过降级（运行时表由应用管理，不随迁移回滚删除）")
