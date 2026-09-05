# @ai-generated
"""
B17 多渠道对账差异处理与多渠道聚合统计 专属常量（独立新建，不修改 B01-B16 基线）
渠道对账：按渠道维度对比订单佣金 ↔ 结算入账，支持 myq/orderx 双渠道
聚合统计：大盘报表佣金/订单/成交数据分渠道汇总展示
"""
from enum import Enum


# ════════════════════════════════════════════════════════════════════
# 渠道对账差异类型（B17 新增，与 B13 用户维度差异类型互补）
# ════════════════════════════════════════════════════════════════════
# CHANNEL_ORDER_SETTLEMENT_MISMATCH: 渠道订单佣金 ↔ 渠道结算入账 金额不一致
# CHANNEL_SINGLE_SIDE_ORDER:         渠道有订单但无结算单（单边账-订单侧）
# CHANNEL_SINGLE_SIDE_SETTLEMENT:    渠道有结算单但订单缺失（单边账-结算侧）
# CHANNEL_ORDER_MISSING:             渠道侧订单在系统内缺失（渠道拉取 vs 系统存储）
# CHANNEL_ORDER_AMOUNT_MISMATCH:     渠道侧订单金额与系统内不一致


class ChannelDiffType(str, Enum):
    """渠道对账差异类型枚举"""

    CHANNEL_ORDER_SETTLEMENT_MISMATCH = "CHANNEL_ORDER_SETTLEMENT_MISMATCH"
    CHANNEL_SINGLE_SIDE_ORDER = "CHANNEL_SINGLE_SIDE_ORDER"
    CHANNEL_SINGLE_SIDE_SETTLEMENT = "CHANNEL_SINGLE_SIDE_SETTLEMENT"
    CHANNEL_ORDER_MISSING = "CHANNEL_ORDER_MISSING"
    CHANNEL_ORDER_AMOUNT_MISMATCH = "CHANNEL_ORDER_AMOUNT_MISMATCH"


# 渠道对账差异类型 → 默认告警级别
CHANNEL_DIFF_ALERT_LEVEL_MAP: dict = {
    ChannelDiffType.CHANNEL_ORDER_SETTLEMENT_MISMATCH.value: "WARNING",
    ChannelDiffType.CHANNEL_SINGLE_SIDE_ORDER.value: "INFO",
    ChannelDiffType.CHANNEL_SINGLE_SIDE_SETTLEMENT.value: "WARNING",
    ChannelDiffType.CHANNEL_ORDER_MISSING.value: "CRITICAL",
    ChannelDiffType.CHANNEL_ORDER_AMOUNT_MISMATCH.value: "WARNING",
}


# ════════════════════════════════════════════════════════════════════
# 渠道对账批次状态机
# ════════════════════════════════════════════════════════════════════


class ChannelReconciliationStatus(str, Enum):
    """渠道对账批次状态机"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


# ════════════════════════════════════════════════════════════════════
# 渠道对账定时任务配置
# ════════════════════════════════════════════════════════════════════
# 每日 02:30 执行（错峰：B13 每日 02:00 全链路对账之后）
TASK_CRON_CHANNEL_RECONCILIATION = "30 2 * * *"
TASK_CHANNEL_RECONCILIATION_ENABLE = True  # 任务开关
TASK_CHANNEL_RECONCILIATION_LOCK_TIMEOUT = 600  # 分布式锁超时（秒）

# 支持渠道对账的渠道列表（myq-喵有券 / orderx-订单侠）
CHANNEL_RECONCILIATION_CHANNELS = ["myq", "orderx"]


# ════════════════════════════════════════════════════════════════════
# Redis 键配置（裸 key，LockUtil.acquire_lock 内部补 LOCK_PREFIX）
# ════════════════════════════════════════════════════════════════════
# 渠道对账幂等锁：gaking:prod:lock:channel_reconciliation:{date}
LOCK_KEY_CHANNEL_RECONCILIATION = "channel_reconciliation:"
# 渠道对账日期幂等缓存：gaking:prod:channel_reconciliation:date:{date}
CACHE_KEY_CHANNEL_RECONCILIATION_DATE = "channel_reconciliation:date:"
CACHE_TTL_CHANNEL_RECONCILIATION_DATE = 86400  # 24 小时


# ════════════════════════════════════════════════════════════════════
# 渠道对账批次号前缀
# ════════════════════════════════════════════════════════════════════
CHANNEL_RECONCILIATION_NO_PREFIX = "GAKCR"  # 金角大王渠道对账批次号前缀


# ════════════════════════════════════════════════════════════════════
# 渠道聚合统计常量
# ════════════════════════════════════════════════════════════════════
# 大盘渠道统计缓存 key：gaking:prod:dashboard:channel_stats
CACHE_KEY_DASHBOARD_CHANNEL_STATS = "dashboard:channel_stats"
CACHE_TTL_DASHBOARD_CHANNEL_STATS = 300  # 5 分钟

# 渠道成交状态集合（已付款/已结算，计入成交数据）
CHANNEL_DEAL_STATUSES = [30, 40]  # 30-已付款 40-已结算
