# @ai-generated
"""
B11-1 渠道佣金比例配置、渠道黑名单、渠道订单数据统计模块常量定义

内容：
1. B11 新增权限码（channel:stat）
2. 黑名单类型枚举
3. 操作类型枚举
4. Redis 键与缓存配置
5. 定时统计任务配置
"""
from enum import IntEnum, Enum

from src.config.b14_constants import ALL_ADMIN_PERMISSIONS as _B14_PERMS


# ════════════════════════════════════════════════════════════
# 1. B11 新增权限码
# ════════════════════════════════════════════════════════════
PERM_CHANNEL_STAT = "channel:stat"  # 渠道数据统计
PERM_CHANNEL_BLACKLIST = "channel:blacklist"  # 渠道黑名单管理

# B11 新增权限码集合
B11_PERMISSIONS = [
    PERM_CHANNEL_STAT,
    PERM_CHANNEL_BLACKLIST,
]

# 全部 admin 权限码字典（B14 基线 + B11 新增）
ALL_ADMIN_PERMISSIONS = _B14_PERMS + [
    {"code": PERM_CHANNEL_STAT, "name": "渠道数据统计", "module": "B11"},
    {"code": PERM_CHANNEL_BLACKLIST, "name": "渠道黑名单管理", "module": "B11"},
]


# ════════════════════════════════════════════════════════════
# 2. 黑名单类型枚举
# ════════════════════════════════════════════════════════════
class BlacklistType(str, Enum):
    """黑名单类型枚举"""

    USER = "user"  # 用户黑名单
    IP = "ip"  # IP黑名单
    ORDER = "order"  # 订单黑名单


# 黑名单类型中文映射
BLACKLIST_TYPE_LABELS = {
    BlacklistType.USER: "用户黑名单",
    BlacklistType.IP: "IP黑名单",
    BlacklistType.ORDER: "订单黑名单",
}


# ════════════════════════════════════════════════════════════
# 3. 操作类型枚举
# ════════════════════════════════════════════════════════════
class OperationType(str, Enum):
    """配置变更操作类型枚举"""

    BLACKLIST_ADD = "blacklist_add"  # 新增黑名单
    BLACKLIST_REMOVE = "blacklist_remove"  # 移除黑名单
    BLACKLIST_UPDATE = "blacklist_update"  # 更新黑名单
    BLACKLIST_TOGGLE = "blacklist_toggle"  # 启停黑名单
    COMMISSION_CONFIG = "commission_config"  # 佣金比例配置变更
    CHANNEL_CONFIG = "channel_config"  # 渠道通用配置变更


# 操作类型中文映射
OPERATION_TYPE_LABELS = {
    OperationType.BLACKLIST_ADD: "新增黑名单",
    OperationType.BLACKLIST_REMOVE: "移除黑名单",
    OperationType.BLACKLIST_UPDATE: "更新黑名单",
    OperationType.BLACKLIST_TOGGLE: "启停黑名单",
    OperationType.COMMISSION_CONFIG: "佣金比例配置变更",
    OperationType.CHANNEL_CONFIG: "渠道通用配置变更",
}


# ════════════════════════════════════════════════════════════
# 4. Redis 键与缓存配置
# ════════════════════════════════════════════════════════════
from src.config.constants import REDIS_PREFIX

# 渠道黑名单缓存：gaking:prod:channel:blacklist:{channel_code}
CACHE_KEY_CHANNEL_BLACKLIST = f"{REDIS_PREFIX}channel:blacklist:"
CACHE_TTL_CHANNEL_BLACKLIST = 5 * 60  # 5分钟

# 渠道每日统计缓存：gaking:prod:channel:daily_stat:{channel_code}:{date}
CACHE_KEY_CHANNEL_DAILY_STAT = f"{REDIS_PREFIX}channel:daily_stat:"
CACHE_TTL_CHANNEL_DAILY_STAT = 10 * 60  # 10分钟

# 渠道统计汇总缓存：gaking:prod:channel:stat_summary
CACHE_KEY_CHANNEL_STAT_SUMMARY = f"{REDIS_PREFIX}channel:stat_summary"
CACHE_TTL_CHANNEL_STAT_SUMMARY = 5 * 60  # 5分钟


# ════════════════════════════════════════════════════════════
# 5. 定时统计任务配置
# ════════════════════════════════════════════════════════════
# 渠道每日统计任务：每日 01:00
TASK_CRON_CHANNEL_DAILY_STAT = "0 1 * * *"
# 任务开关
TASK_CHANNEL_DAILY_STAT_ENABLE = True
# 分布式锁超时（秒）
TASK_CHANNEL_DAILY_STAT_LOCK_TIMEOUT = 600