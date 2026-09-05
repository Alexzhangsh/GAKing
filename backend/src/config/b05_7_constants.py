# @ai-generated
"""
B05-7 批量订单结算定时任务配置
独立文件，不修改 B01-B07 已有常量
"""
from enum import IntEnum

# ── 定时任务：批量订单结算 —— 每15分钟（与B07错峰，复用B07的查询逻辑） ──
TASK_CRON_BATCH_SETTLE = "*/15 * * * *"  # 每15分钟
TASK_BATCH_SETTLE_ENABLE = True  # 任务开关
TASK_BATCH_SETTLE_LOCK_TIMEOUT = 300  # 分布式锁超时（秒），单轮最长5分钟
TASK_BATCH_SETTLE_BATCH_SIZE = 200  # 单轮处理订单上限

# ── 定时任务运行日志清理 ──────────────────────────────────────────
TASK_RUN_LOG_RETENTION_DAYS = 30  # 日志保留天数，超期自动清理

# ── Redis 键（裸key，LockUtil.acquire_lock 内部补 LOCK_PREFIX） ──────
# 实际 Redis key：gaking:prod:lock:scheduler:batch_settle_b05_7
LOCK_KEY_BATCH_SETTLE_B05_7 = "scheduler:batch_settle_b05_7"