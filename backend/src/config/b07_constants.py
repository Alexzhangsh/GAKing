# @ai-generated
"""
B07 佣金计算与结算模块专属常量
独立文件，避免修改 B05 已改的 constants.py
所有定时任务参数、Redis 键、佣金比例配置均在此定义，禁止在业务代码内硬编码
"""
from decimal import Decimal
from enum import Enum


# ── 佣金比例默认值（兜底，与 commission_service.py / order_sync_service.py 一致） ──
DEFAULT_USER_COMMISSION_RATE = Decimal("0.80")  # 用户返利比例 80%
DEFAULT_PLATFORM_COMMISSION_RATE = Decimal("0.20")  # 平台留存比例 20%

# 金额精度（2 位小数）
COMMISSION_QUANTIZE = Decimal("0.01")

# 比例总和校验误差容忍度（浮点精度问题）
RATE_SUM_TOLERANCE = Decimal("0.0001")


class UserType(str, Enum):
    """用户类型枚举（当前仅 NORMAL，VIP 预留扩展）

    分润模型：普通用户 / 付费会员两套规则
    每套约束：用户返利比例 + 平台留存比例 = 100%
    """

    NORMAL = "NORMAL"  # 普通用户
    VIP = "VIP"  # 付费会员（预留，当前无会员体系）


# ── SystemConfig 配置键（gaking_system_config 表，JSON 格式存储） ──────────────
# 默认分润规则：{"NORMAL": {"user_rate": "0.80", "platform_rate": "0.20"}, "VIP": {...}}
CONFIG_KEY_COMMISSION_RULE_DEFAULT = "commission_rule:default"
# 渠道专属规则：commission_rule:channel:{channel_code}
# {"NORMAL": {"user_rate": "0.85", "platform_rate": "0.15"}, "VIP": {...}}
CONFIG_KEY_COMMISSION_RULE_CHANNEL = "commission_rule:channel:"

# 配置缓存 TTL（秒）：规则低频变更，5 分钟刷新足够感知后台改值
CACHE_TTL_COMMISSION_RULE = 300


# ════════════════════════════════════════════════════════════════════
# B07 定时任务配置
# ════════════════════════════════════════════════════════════════════

# ── 任务3：批量佣金结算 —— 每15分钟（与订单同步错峰） ──────────────────
TASK_CRON_BATCH_SETTLE_COMMISSION = "*/15 * * * *"
TASK_BATCH_SETTLE_ENABLE = True  # 任务开关
TASK_BATCH_SETTLE_LOCK_TIMEOUT = 300  # 分布式锁超时（秒），单轮最长5分钟
TASK_BATCH_SETTLE_BATCH_SIZE = 200  # 单轮处理订单上限

# ── 任务4：退款佣金扣减 —— 每10分钟 ──────────────────────────────
TASK_CRON_REFUND_DEDUCT = "*/10 * * * *"
TASK_REFUND_DEDUCT_ENABLE = True  # 任务开关
TASK_REFUND_DEDUCT_LOCK_TIMEOUT = 300  # 分布式锁超时（秒）
TASK_REFUND_DEDUCT_BATCH_SIZE = 100  # 单轮处理订单上限


# ── Redis 键配置（裸 key，LockUtil.acquire_lock 内部补 LOCK_PREFIX） ──────────
# 实际 Redis key：gaking:prod:lock:commission_settle: / gaking:prod:lock:refund_deduct:
LOCK_KEY_BATCH_SETTLE = "commission_settle:"
LOCK_KEY_REFUND_DEDUCT = "refund_deduct:"

# 佣金规则缓存键（裸 key，RedisClient.add_prefix 自动补 gaking:prod: 前缀）
# 实际 Redis key：gaking:prod:commission_rule:default / gaking:prod:commission_rule:channel:{code}
CACHE_KEY_COMMISSION_RULE_DEFAULT = "commission_rule:default"
CACHE_KEY_COMMISSION_RULE_CHANNEL = "commission_rule:channel:"
