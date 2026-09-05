# @ai-generated
"""
B10 消息通知模块常量

消息类型枚举：
- COMMISSION: 佣金到账通知
- WITHDRAW: 提现审核结果通知
- ORDER: 订单成交通知
- REFUND: 退款冲减通知

Redis 键统一前缀 gaking:prod:（由 REDIS_PREFIX 拼接）
"""
from decimal import Decimal
from enum import Enum

from src.config.constants import REDIS_PREFIX, LOCK_PREFIX, TASK_PREFIX


# ════════════════════════════════════════════════════════════════════
# 消息类型枚举
# ════════════════════════════════════════════════════════════════════


class MessageType(str, Enum):
    """站内消息业务类型

    COMMISSION: 佣金到账通知（跳转佣金明细页）
    WITHDRAW: 提现审核结果通知（跳转提现记录页）
    ORDER: 订单成交通知（跳转订单详情页）
    REFUND: 退款冲减通知（跳转退款记录页）
    """

    COMMISSION = "commission"  # 佣金到账
    WITHDRAW = "withdraw"  # 提现审核结果
    ORDER = "order"  # 订单成交
    REFUND = "refund"  # 退款冲减


# 消息类型与业务跳转路径映射（前端路由）
MESSAGE_TYPE_ROUTE_MAP = {
    MessageType.COMMISSION.value: "/pages/commission/list",
    MessageType.WITHDRAW.value: "/pages/withdraw/list",
    MessageType.ORDER.value: "/pages/order/detail",
    MessageType.REFUND.value: "/pages/refund/list",
}


# ════════════════════════════════════════════════════════════════════
# Redis 缓存键
# ════════════════════════════════════════════════════════════════════

# 用户未读消息计数缓存：gaking:prod:user:unread_count:{user_id}
CACHE_KEY_USER_UNREAD_COUNT = f"{REDIS_PREFIX}user:unread_count:"
# 用户未读消息计数缓存 TTL（秒）：10 分钟，低频变更
CACHE_TTL_UNREAD_COUNT = 600


# ════════════════════════════════════════════════════════════════════
# 定时任务配置
# ════════════════════════════════════════════════════════════════════

# 消息推送巡检任务 cron 表达式：每 5 分钟
TASK_CRON_MESSAGE_PUSH_PATROL = "*/5 * * * *"
# 消息推送任务开关
TASK_MESSAGE_PUSH_PATROL_ENABLE = True
# 消息推送任务分布式锁超时（秒）
TASK_MESSAGE_PUSH_PATROL_LOCK_TIMEOUT = 120
# 单次巡检最大推送消息数
TASK_MESSAGE_PUSH_PATROL_BATCH_SIZE = 100
# 消息推送重试最大次数
TASK_MESSAGE_PUSH_MAX_RETRY = 3
# 消息推送重试间隔（秒）
TASK_MESSAGE_PUSH_RETRY_INTERVAL = 60