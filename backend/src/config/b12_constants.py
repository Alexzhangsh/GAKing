# @ai-generated
"""
B12-1 订单状态机管控模块常量定义

内容：
1. B12 新增权限码
2. 订单状态流转约束（完整状态机定义）
3. 操作类型枚举
4. 订单状态中文映射
5. Redis 键与缓存配置
6. 定时任务配置
"""
from enum import IntEnum, Enum

from src.config.b14_constants import ALL_ADMIN_PERMISSIONS as _B14_PERMS
from src.config.constants import OrderStatus


# ════════════════════════════════════════════════════════════
# 1. B12 新增权限码
# ════════════════════════════════════════════════════════════
PERM_ORDER_STATE_MACHINE = "order:state_machine"  # 订单状态机管理
PERM_ORDER_OPERATION_LOG = "order:operation_log"  # 订单操作日志查询

# B12 新增权限码集合
B12_PERMISSIONS = [
    PERM_ORDER_STATE_MACHINE,
    PERM_ORDER_OPERATION_LOG,
]

# 全部 admin 权限码字典（B14 基线 + B12 新增）
ALL_ADMIN_PERMISSIONS = _B14_PERMS + [
    {"code": PERM_ORDER_STATE_MACHINE, "name": "订单状态机管理", "module": "B12"},
    {"code": PERM_ORDER_OPERATION_LOG, "name": "订单操作日志查询", "module": "B12"},
]


# ════════════════════════════════════════════════════════════
# 2. 订单状态流转约束（完整状态机定义）
# ════════════════════════════════════════════════════════════
# 状态机核心规则：
#   正向流转：PENDING(10) → FROZEN(20) → SETTLABLE(30) → SETTLED(40)
#   异常分支：PENDING(10) → INVALID(50) / REFUNDED(60)
#             FROZEN(20) → INVALID(50)
#             SETTLABLE(30) → INVALID(50)
#             SETTLED(40) → REFUNDED(60)
#   终态：INVALID(50)、REFUNDED(60) 不可再流转
#
# 每个状态流转的前置条件（见 ORDER_STATUS_TRANSITION_CONDITIONS）

# 状态机合法流转映射：前置状态 → 允许的目标状态集合
ORDER_STATUS_TRANSITIONS: dict = {
    OrderStatus.PENDING: {
        OrderStatus.FROZEN,     # 支付成功 → 冻结（等待确认收货）
        OrderStatus.INVALID,    # 超时未支付 → 失效
        OrderStatus.REFUNDED,   # 支付前退款 → 已退款
    },
    OrderStatus.FROZEN: {
        OrderStatus.SETTLABLE,  # 确认收货 → 可结算
        OrderStatus.INVALID,    # 订单异常 → 失效
    },
    OrderStatus.SETTLABLE: {
        OrderStatus.SETTLED,    # 结算完成 → 已结算
        OrderStatus.INVALID,    # 订单异常 → 失效
    },
    OrderStatus.SETTLED: {
        OrderStatus.REFUNDED,   # 售后退款 → 已退款
    },
    OrderStatus.INVALID: set(),    # 终态，不可再流转
    OrderStatus.REFUNDED: set(),   # 终态，不可再流转
}

# 状态流转前置条件校验规则
# 格式：{ (from_status, to_status): "条件描述" }
ORDER_STATUS_TRANSITION_CONDITIONS: dict = {
    (OrderStatus.PENDING, OrderStatus.FROZEN): "订单已支付，支付金额 > 0",
    (OrderStatus.PENDING, OrderStatus.INVALID): "超时未支付或手动取消",
    (OrderStatus.PENDING, OrderStatus.REFUNDED): "支付前退款或订单取消退款",
    (OrderStatus.FROZEN, OrderStatus.SETTLABLE): "渠道确认收货，结算周期到达",
    (OrderStatus.FROZEN, OrderStatus.INVALID): "订单异常或渠道标记失效",
    (OrderStatus.SETTLABLE, OrderStatus.SETTLED): "佣金结算完成",
    (OrderStatus.SETTLABLE, OrderStatus.INVALID): "订单异常或渠道标记失效",
    (OrderStatus.SETTLED, OrderStatus.REFUNDED): "售后退款冲减完成",
}

# 终态集合
TERMINAL_STATUSES = {OrderStatus.INVALID, OrderStatus.REFUNDED}

# 可手动干预的状态集合（后台人工操作）
MANUAL_OVERRIDEABLE_STATUSES = {
    OrderStatus.PENDING,
    OrderStatus.FROZEN,
    OrderStatus.SETTLABLE,
}


# ════════════════════════════════════════════════════════════
# 3. 操作类型枚举
# ════════════════════════════════════════════════════════════
class SettlementStatus(IntEnum):
    """结算状态枚举"""
    ORDERED = 10    # 已下单
    SETTLABLE = 20  # 可结算
    SETTLED = 30    # 已结算
    PAID = 40       # 已付款


class OrderOperationType(str, Enum):
    """订单操作类型枚举"""

    STATUS_TRANSITION = "status_transition"  # 状态流转
    MANUAL_OVERRIDE = "manual_override"  # 人工干预状态
    SYNC_UPDATE = "sync_update"  # 渠道同步更新
    ANOMALY_MARK = "anomaly_mark"  # 异常标记
    ANOMALY_FIX = "anomaly_fix"  # 异常修复
    REFUND_DEDUCT = "refund_deduct"  # 退款冲减
    SETTLEMENT = "settlement"  # 结算操作


# 操作类型中文映射
ORDER_OPERATION_TYPE_LABELS = {
    OrderOperationType.STATUS_TRANSITION: "状态流转",
    OrderOperationType.MANUAL_OVERRIDE: "人工干预",
    OrderOperationType.SYNC_UPDATE: "渠道同步",
    OrderOperationType.ANOMALY_MARK: "异常标记",
    OrderOperationType.ANOMALY_FIX: "异常修复",
    OrderOperationType.REFUND_DEDUCT: "退款冲减",
    OrderOperationType.SETTLEMENT: "结算操作",
}


# ════════════════════════════════════════════════════════════
# 4. 订单状态中文映射
# ════════════════════════════════════════════════════════════
ORDER_STATUS_LABELS = {
    OrderStatus.PENDING: "待付款",
    OrderStatus.FROZEN: "已付款(冻结)",
    OrderStatus.SETTLABLE: "可结算",
    OrderStatus.SETTLED: "已结算",
    OrderStatus.INVALID: "已失效",
    OrderStatus.REFUNDED: "已退款",
}


# ════════════════════════════════════════════════════════════
# 5. Redis 键与缓存配置
# ════════════════════════════════════════════════════════════
from src.config.constants import REDIS_PREFIX

# 订单操作日志缓存
CACHE_KEY_ORDER_OPERATION_LOG = f"{REDIS_PREFIX}order:operation_log:"
CACHE_TTL_ORDER_OPERATION_LOG = 5 * 60  # 5分钟

# 订单状态机规则缓存
CACHE_KEY_ORDER_STATE_MACHINE = f"{REDIS_PREFIX}order:state_machine"
CACHE_TTL_ORDER_STATE_MACHINE = 30 * 60  # 30分钟


# ════════════════════════════════════════════════════════════
# 6. 定时任务配置
# ════════════════════════════════════════════════════════════
# 订单异常巡检任务：每 30 分钟
TASK_CRON_ORDER_ANOMALY_PATROL = "*/30 * * * *"
# 任务开关
TASK_ORDER_ANOMALY_PATROL_ENABLE = True
# 分布式锁超时（秒）
TASK_ORDER_ANOMALY_PATROL_LOCK_TIMEOUT = 300
# 异常告警阈值（当日异常订单数 >= 此值时输出 WARNING 日志）
TASK_ORDER_ANOMALY_WARN_THRESHOLD = 50


# ════════════════════════════════════════════════════════════
# 7. 结算单常量（B12 结算状态机，settlement_b12_jobs / settlement_b12.py 共用）
# ════════════════════════════════════════════════════════════
# 结算延迟天数（从 system_config 读取，兜底值）
CONFIG_KEY_SETTLEMENT_DELAY_DAYS = "settlement_delay_days"
SETTLEMENT_DELAY_DAYS_DEFAULT = 30
SETTLEMENT_DELAY_DAYS_CACHE_TTL = 300  # 5 分钟缓存

# 结算单编号前缀
SETTLEMENT_NO_PREFIX = "ST"

# 结算操作类型（记入 operation_log）
ACTION_CREATE_SETTLEMENT = "create_settlement"
ACTION_FREEZE = "freeze"
ACTION_MARK_PAID = "mark_paid"
ACTION_UNFREEZE = "unfreeze"

# Redis 分布式锁
LOCK_KEY_SETTLEMENT_OP = f"{REDIS_PREFIX}settlement:op:"
SETTLEMENT_OP_LOCK_TIMEOUT = 10  # 秒

# 熔断器渠道
SETTLEMENT_BREAKER_CHANNEL = "settlement"

# 结算单状态机：合法流转映射
# ORDERED → SETTLABLE → SETTLED → PAID
SETTLEMENT_TRANSITIONS: dict = {
    SettlementStatus.ORDERED.value: {SettlementStatus.SETTLABLE.value},
    SettlementStatus.SETTLABLE.value: {SettlementStatus.SETTLED.value},
    SettlementStatus.SETTLED.value: {SettlementStatus.PAID.value},
    SettlementStatus.PAID.value: set(),
}

# 终态集合
SETTLEMENT_TERMINAL_STATES = {SettlementStatus.PAID.value}

# 定时任务配置
TASK_CRON_SETTLEMENT_FREEZE = "*/12 * * * *"  # 每 12 分钟
TASK_CRON_SETTLEMENT_UNFREEZE = "*/8 * * * *"  # 每 8 分钟
TASK_SETTLEMENT_FREEZE_BATCH_SIZE = 50
TASK_SETTLEMENT_FREEZE_ENABLE = True
TASK_SETTLEMENT_FREEZE_LOCK_TIMEOUT = 300
TASK_SETTLEMENT_UNFREEZE_BATCH_SIZE = 50
TASK_SETTLEMENT_UNFREEZE_ENABLE = True
TASK_SETTLEMENT_UNFREEZE_LOCK_TIMEOUT = 300