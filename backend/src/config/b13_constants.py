# @ai-generated
"""
B13 全链路数据对账模块专属常量（独立新建，不修改 B01-B12 任何基线 constants 文件）
四方核对：订单原始佣金 ↔ B12结算入账 ↔ B08资产账户余额 ↔ B10微信打款流水
所有定时任务参数、Redis 键、状态枚举均在此定义，禁止在业务代码内硬编码
"""
from enum import Enum


# ════════════════════════════════════════════════════════════════════
# 对账批次状态机
# ════════════════════════════════════════════════════════════════════
# PENDING:  对账批次已创建，尚未开始执行
# RUNNING:  对账正在执行中
# SUCCESS:  对账完成，无差异（全部平账）
# PARTIAL:  对账完成，存在差异（部分平账）
# FAILED:   对账执行异常（熔断/DB异常等）


class ReconciliationStatus(str, Enum):
    """对账批次状态机"""

    PENDING = "PENDING"  # 待执行
    RUNNING = "RUNNING"  # 执行中
    SUCCESS = "SUCCESS"  # 完成-无差异
    PARTIAL = "PARTIAL"  # 完成-有差异
    FAILED = "FAILED"  # 异常终止


# ════════════════════════════════════════════════════════════════════
# 对账类型
# ════════════════════════════════════════════════════════════════════


class ReconciliationType(str, Enum):
    """对账触发类型"""

    DAILY = "DAILY"  # 每日自动对账
    MANUAL = "MANUAL"  # 手动触发对账


# ════════════════════════════════════════════════════════════════════
# 差异类型（四方核对产生的差异分类）
# ════════════════════════════════════════════════════════════════════
# ORDER_SETTLEMENT_MISMATCH:     订单佣金 ↔ 结算入账 金额不一致
# SETTLEMENT_ACCOUNT_MISMATCH:   结算入账 ↔ 账户余额 汇总不一致
# ACCOUNT_WITHDRAW_MISMATCH:     账户累计提现 ↔ 提现流水 汇总不一致
# WITHDRAW_TRANSFER_MISMATCH:    提现流水 ↔ 微信打款 状态/金额不一致
# SINGLE_SIDE_ORDER:             单边账-订单存在但无结算单
# SINGLE_SIDE_SETTLEMENT:        单边账-结算单存在但订单缺失
# SINGLE_SIDE_WITHDRAW:          单边账-提现流水无对应账户记录


class DiffType(str, Enum):
    """差异类型枚举"""

    ORDER_SETTLEMENT_MISMATCH = "ORDER_SETTLEMENT_MISMATCH"
    SETTLEMENT_ACCOUNT_MISMATCH = "SETTLEMENT_ACCOUNT_MISMATCH"
    ACCOUNT_WITHDRAW_MISMATCH = "ACCOUNT_WITHDRAW_MISMATCH"
    WITHDRAW_TRANSFER_MISMATCH = "WITHDRAW_TRANSFER_MISMATCH"
    SINGLE_SIDE_ORDER = "SINGLE_SIDE_ORDER"
    SINGLE_SIDE_SETTLEMENT = "SINGLE_SIDE_SETTLEMENT"
    SINGLE_SIDE_WITHDRAW = "SINGLE_SIDE_WITHDRAW"


# 差异来源端类型（四方核对的数据来源标识）
SOURCE_TYPE_ORDER = "ORDER"
SOURCE_TYPE_SETTLEMENT = "SETTLEMENT"
SOURCE_TYPE_ACCOUNT = "ACCOUNT"
SOURCE_TYPE_WITHDRAW = "WITHDRAW"


# ════════════════════════════════════════════════════════════════════
# 差异状态机（人工复核流程）
# ════════════════════════════════════════════════════════════════════
# PENDING:    待复核（新发现的差异）
# REVIEWING:  复核中（运营已认领）
# RESOLVED:   已调平（运营确认差异已处理）
# IGNORED:    已忽略（运营判定为正常差异，如精度误差）


class DiffStatus(str, Enum):
    """差异复核状态机"""

    PENDING = "PENDING"  # 待复核
    REVIEWING = "REVIEWING"  # 复核中
    RESOLVED = "RESOLVED"  # 已调平
    IGNORED = "IGNORED"  # 已忽略


# 合法差异状态流转映射
DIFF_TRANSITIONS: dict = {
    DiffStatus.PENDING.value: {
        DiffStatus.REVIEWING.value,
        DiffStatus.RESOLVED.value,
        DiffStatus.IGNORED.value,
    },
    DiffStatus.REVIEWING.value: {
        DiffStatus.RESOLVED.value,
        DiffStatus.IGNORED.value,
    },
    DiffStatus.RESOLVED.value: set(),  # 终态
    DiffStatus.IGNORED.value: set(),  # 终态
}

# 终态集合
DIFF_TERMINAL_STATES = frozenset({DiffStatus.RESOLVED.value, DiffStatus.IGNORED.value})


# ════════════════════════════════════════════════════════════════════
# 告警级别
# ════════════════════════════════════════════════════════════════════


class AlertLevel(str, Enum):
    """告警级别"""

    INFO = "INFO"  # 信息（如单边账-订单无结算单，可能是正常时序差）
    WARNING = "WARNING"  # 警告（金额不一致，需人工核查）
    CRITICAL = "CRITICAL"  # 严重（账户余额不一致/提现打款异常，需立即处理）


# 告警级别映射（差异类型 → 默认告警级别）
DIFF_ALERT_LEVEL_MAP: dict = {
    DiffType.ORDER_SETTLEMENT_MISMATCH.value: AlertLevel.WARNING.value,
    DiffType.SETTLEMENT_ACCOUNT_MISMATCH.value: AlertLevel.CRITICAL.value,
    DiffType.ACCOUNT_WITHDRAW_MISMATCH.value: AlertLevel.CRITICAL.value,
    DiffType.WITHDRAW_TRANSFER_MISMATCH.value: AlertLevel.CRITICAL.value,
    DiffType.SINGLE_SIDE_ORDER.value: AlertLevel.INFO.value,
    DiffType.SINGLE_SIDE_SETTLEMENT.value: AlertLevel.WARNING.value,
    DiffType.SINGLE_SIDE_WITHDRAW.value: AlertLevel.CRITICAL.value,
}


# ════════════════════════════════════════════════════════════════════
# B13 定时任务配置（错峰执行，避免与 B07/B12 任务冲突）
# ════════════════════════════════════════════════════════════════════
# 任务10：每日全链路对账 —— 每日 02:00 执行（凌晨低峰期，B07/B12 已完成当日结算）
# 对账前一日 [昨天 00:00, 今天 00:00) 的全链路数据一致性
TASK_CRON_DAILY_RECONCILIATION = "0 2 * * *"
TASK_DAILY_RECONCILIATION_ENABLE = True  # 任务开关
TASK_DAILY_RECONCILIATION_LOCK_TIMEOUT = 600  # 分布式锁超时（秒），对账可能较久
TASK_DAILY_RECONCILIATION_BATCH_SIZE = 500  # 单轮对账用户上限


# ════════════════════════════════════════════════════════════════════
# Redis 键配置（裸 key，LockUtil.acquire_lock 内部补 LOCK_PREFIX）
# ════════════════════════════════════════════════════════════════════
# 任务级分布式锁：gaking:prod:lock:reconciliation_daily:
LOCK_KEY_RECONCILIATION_DAILY = "reconciliation_daily:"
# 单批次对账幂等锁（防止同日重复对账）：gaking:prod:lock:reconciliation:{reconcile_date}
LOCK_KEY_RECONCILIATION_OP = "reconciliation:"
RECONCILIATION_OP_LOCK_TIMEOUT = 600  # 单批次对账幂等锁超时（秒）

# 对账日期幂等缓存 key（记录当日已对账状态）：gaking:prod:reconciliation:date:{date}
CACHE_KEY_RECONCILIATION_DATE = "reconciliation:date:"
CACHE_TTL_RECONCILIATION_DATE = 86400  # 24 小时（当日防重复）


# ════════════════════════════════════════════════════════════════════
# B04 熔断器配置
# ════════════════════════════════════════════════════════════════════
# 对账流程接入 B04 熔断，channel_code 独立
# 熔断触发场景：对账查询连续失败（DB 异常）→ 熔断后跳过对账
RECONCILIATION_BREAKER_CHANNEL = "reconciliation"


# ════════════════════════════════════════════════════════════════════
# 对账批次号生成前缀
# ════════════════════════════════════════════════════════════════════
RECONCILIATION_NO_PREFIX = "GAKR"  # 金角大王对账批次号前缀


# ════════════════════════════════════════════════════════════════════
# 金额精度容忍度（浮点/Decimal 精度误差，小于此值视为平账）
# ════════════════════════════════════════════════════════════════════
from decimal import Decimal

RECONCILIATION_TOLERANCE = Decimal("0.01")  # 1 分钱容忍度
