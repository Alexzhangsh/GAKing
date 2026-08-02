# @ai-generated
from decimal import Decimal
from enum import IntEnum, Enum

REDIS_PREFIX = "gaking:prod:"

CACHE_KEY_SYSTEM_CONFIG = f"{REDIS_PREFIX}config:system"
CACHE_KEY_PAY_CONFIG = f"{REDIS_PREFIX}config:pay"
CACHE_KEY_CLOUD_CONFIG = f"{REDIS_PREFIX}config:cloud"
CACHE_KEY_CHANNEL_MAPPING = f"{REDIS_PREFIX}mapping:channel"

# 订单/佣金查询缓存键 —— 统一前缀 gaking:prod: 由 REDIS_PREFIX 拼接
# 实际 Redis key 形如 gaking:prod:order:{order_id} / gaking:prod:commission_sum:{order_id}
CACHE_KEY_ORDER_DETAIL = f"{REDIS_PREFIX}order:"
CACHE_KEY_COMMISSION_SUM = f"{REDIS_PREFIX}commission_sum:"

LOCK_PREFIX = f"{REDIS_PREFIX}lock:"
LOCK_KEY_CHANNEL_MAPPING_REFRESH = f"{LOCK_PREFIX}channel_mapping_refresh"

RATE_LIMIT_PREFIX = f"{REDIS_PREFIX}rate:"

IDEMPOTENT_PREFIX = f"{REDIS_PREFIX}idempotent:"
IDEMPOTENT_KEY_ORDER_TEMPLATE = f"{IDEMPOTENT_PREFIX}order:"

TASK_PREFIX = f"{REDIS_PREFIX}task:"


class LockTimeout(IntEnum):
    NORMAL = 10
    TASK = 60


class OrderStatus(IntEnum):
    PENDING = 10
    FROZEN = 20
    SETTLABLE = 30
    SETTLED = 40
    INVALID = 50
    REFUNDED = 60


class TransferStatus(str, Enum):
    """佣金/订单转账状态（与 CommissionFlow.transfer_status / Order.transfer_status 字段对应）"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class PayType(IntEnum):
    WECHAT = 1


class ChannelCode(Enum):
    MIAOQUAN = "myq"
    DATAOK = "dta"
    ORDERX = "orderx"


class PlatformType(IntEnum):
    TAOBAO = 1
    JD = 2
    PDD = 3
    DOUYIN = 4


class CacheTTL(IntEnum):
    HOT_GOODS_SEARCH = 30 * 60
    NORMAL_GOODS_SEARCH = 5 * 60
    COLD_GOODS_SEARCH = 10 * 60
    EMPTY_SEARCH_RESULT = 60
    USER_COMMISSION = 60 * 60
    CONFIG_PERMANENT = 0
    # 订单详情/佣金汇总查询缓存：10 分钟 + RedisClient 内置 ±20% 抖动，防雪崩
    ORDER_DETAIL = 10 * 60
    COMMISSION_SUM = 10 * 60
    # 用户佣金账户缓存：10 分钟 + ±20% 抖动
    USER_ACCOUNT = 10 * 60


class RateLimitType(Enum):
    NORMAL = "normal"
    SEARCH = "search"
    TRANSFORM = "transform"
    PAY = "pay"
    DATAOK_SEARCH = "datoke_search"
    DATAOK_TRANSFORM = "datoke_transform"


# ── 定时任务作业配置（scheduler_jobs.py 使用，禁止在业务代码内硬编码） ──────
# 任务1：超时未支付订单自动关闭
TASK_CRON_CLOSE_EXPIRED_ORDERS = "*/5 * * * *"  # 执行频率：每5分钟
TASK_ORDER_EXPIRE_MINUTES = 30  # 待支付订单超时阈值（分钟）
TASK_CLOSE_EXPIRED_ORDERS_ENABLE = True  # 任务开关
TASK_CLOSE_EXPIRED_ORDERS_LOCK_TIMEOUT = 120  # 分布式锁超时（秒）

# 任务2：每日佣金对账统计
TASK_CRON_DAILY_COMMISSION_RECONCILIATION = "10 0 * * *"  # 执行频率：每日 00:10
TASK_DAILY_COMMISSION_RECONCILIATION_ENABLE = True  # 任务开关
TASK_DAILY_COMMISSION_RECONCILIATION_LOCK_TIMEOUT = 300  # 分布式锁超时（秒）


# ── 用户佣金提现配置 ──────────────────────────────────────────────────────
# 来源：4级《金角大王 CPS V2.0 分润规则定稿》+ 用户确认（max(0.1%, 1元)）。
# 费率/最低手续费已支持动态配置：gaking_pay_config.withdraw_rate / withdraw_min_fee
# （迁移 0003 新增，由 PayConfigUtil 读取）。下列常量作为「兜底默认值」：
# 配置表无启用行 / 字段为空 / 读取异常时，PayConfigUtil 自动回退到这些常量，保证降级可用。
WITHDRAW_MIN_AMOUNT = Decimal("10.00")  # 最低提现门槛：10 金角币（1:1 元，暂不动态化）
WITHDRAW_FEE_RATE = Decimal("0.001")  # 手续费率 0.1%（动态配置兜底值）
WITHDRAW_FEE_MIN = Decimal(
    "1.00"
)  # 单笔最低手续费 1 元（动态配置兜底值，公式：max(amount×rate, min_fee)）
WITHDRAW_FEE_QUANTIZE = Decimal("0.01")  # 手续费精度（2 位小数）


class WithdrawStatus(str, Enum):
    """提现申请状态机（5 态）

    流转：PENDING → APPROVED → PROCESSING → SUCCESS
          任一审核中/通过状态可 → REJECTED（驳回退余额）
          打款失败 → REJECTED（退回可用余额，reject_reason 记失败原因）
    """

    PENDING = "PENDING"  # 待审核（已扣冻结余额）
    APPROVED = "APPROVED"  # 审核通过（待发起转账，余额仍冻结）
    PROCESSING = "PROCESSING"  # 转账处理中（已发起微信转账，待确认）
    SUCCESS = "SUCCESS"  # 打款完成（冻结余额释放，资金已转出）
    REJECTED = "REJECTED"  # 已驳回（含审核驳回 / 打款失败，余额退回可用）


# ── 提现相关 Redis 键 ────────────────────────────────────────────────────
# 用户佣金账户读穿缓存：gaking:prod:user_account:{user_id}
CACHE_KEY_USER_ACCOUNT = f"{REDIS_PREFIX}user_account:"
# 提现手续费动态配置读穿缓存：gaking:prod:config:withdraw（单条 JSON，全局共享）
CACHE_KEY_WITHDRAW_CONFIG = f"{REDIS_PREFIX}config:withdraw"
# 提现手续费配置缓存 TTL（秒）：配置低频变更，5 分钟刷新足够感知后台改值
CACHE_TTL_WITHDRAW_CONFIG = 300
# 提现防重复提交幂等键：gaking:prod:idempotent:withdraw_submit:{user_id}
# （RedisClient.add_prefix 会自动去重 REDIS_PREFIX，故此处含全前缀安全）
IDEMPOTENT_KEY_WITHDRAW_SUBMIT = f"{IDEMPOTENT_PREFIX}withdraw_submit:"
# 提现分布式锁（裸 key，传给 LockUtil.acquire_lock，由其内部补 LOCK_PREFIX）
# 实际 Redis key：gaking:prod:lock:withdraw:{user_id} / gaking:prod:lock:withdraw_apply:{apply_id}
# 约定对齐 scheduler_jobs.py（传裸 key 如 "scheduler:{name}"），避免双重前缀
LOCK_KEY_WITHDRAW_USER = "withdraw:"
LOCK_KEY_WITHDRAW_APPLY = "withdraw_apply:"
# 同一用户连续提现最小间隔（秒），用于吸收双击/快速重复提交
WITHDRAW_SUBMIT_INTERVAL = 5


# ════════════════════════════════════════════════════════════════════
# B05 订单批量同步任务配置（scheduler/order_sync_jobs.py 使用，禁止硬编码）
# ════════════════════════════════════════════════════════════════════

# ── 三渠道错峰 cron 表达式（每10分钟一轮，错峰3分钟避免并发限流） ──────
TASK_CRON_ORDER_SYNC_MYQ = "*/10 * * * *"  # 0/10/20/30/40/50 分
TASK_CRON_ORDER_SYNC_ORDERX = "3-59/10 * * * *"  # 3/13/23/33/43/53 分
TASK_CRON_ORDER_SYNC_DTA = "6-59/10 * * * *"  # 6/16/26/36/46/56 分

# ── 任务开关与锁超时 ──────────────────────────────────────────────
TASK_ORDER_SYNC_ENABLE = True  # 总开关（False 时三渠道任务全跳过）
TASK_ORDER_SYNC_LOCK_TIMEOUT = 600  # 分布式锁超时（秒），单渠道单轮最长10分钟
TASK_ORDER_SYNC_MYQ_ENABLE = True  # 喵有券渠道开关
TASK_ORDER_SYNC_ORDERX_ENABLE = True  # 订单侠渠道开关
TASK_ORDER_SYNC_DTA_ENABLE = True  # 大淘客渠道开关

# ── 拉取与重试参数 ────────────────────────────────────────────────
TASK_ORDER_SYNC_WINDOW_MINUTES = 30  # 单次拉取时间窗口长度（分钟）
TASK_ORDER_SYNC_INITIAL_LOOKBACK_MINUTES = 60  # 首次运行（游标为空）回溯时长（分钟）
TASK_ORDER_SYNC_MAX_RETRY = 3  # 单窗口拉取失败重试次数
TASK_ORDER_SYNC_RETRY_BASE_DELAY = 1  # 重试基础退避（秒），实际=base*2^(attempt-1)
TASK_ORDER_SYNC_MAX_WINDOWS_PER_RUN = 10  # 单轮任务最多拉取窗口数（防积压时无限拉取）

# ── Redis 键配置（裸 key，RedisClient.add_prefix 自动补 gaking:prod: 前缀） ──
# 游标：gaking:prod:order_sync:cursor:{channel}，存最后成功同步的 ISO 时间戳
CACHE_KEY_ORDER_SYNC_CURSOR = "order_sync:cursor:"
# 失败队列：gaking:prod:order_sync:failed:{channel}，List（LPUSH 写入 / RPOP 取出补发）
CACHE_KEY_ORDER_SYNC_FAILED = "order_sync:failed:"
# 分布式锁（裸 key，传给 LockUtil.acquire_lock，由其内部补 LOCK_PREFIX）
# 实际 Redis key：gaking:prod:lock:order_sync:{channel}
LOCK_KEY_ORDER_SYNC = "order_sync:"
# 游标 TTL（秒）：7 天，长期未同步自动失效后从默认回溯时间重新开始
CACHE_TTL_ORDER_SYNC_CURSOR = 7 * 24 * 3600
# 失败队列 TTL（秒）：30 天，超期自动清理
CACHE_TTL_ORDER_SYNC_FAILED = 30 * 24 * 3600


# ── 渠道订单状态字符串 → OrderStatus 枚举映射 ─────────────────────
# 渠道返回的 OrderDTO.order_status 是原始字符串（中文名/英文枚举/数字码），
# 需映射到 OrderStatus 枚举值。冲突状态码（如 "3"）通过渠道专属映射表区分。
#
# 映射规则（用户已确认决策）：
#   渠道「已付款/已确认收货」→ SETTLABLE(30)，复用现有 PENDING→SETTLABLE→SETTLED 三态状态机
#   不新增 OrderStatus.PAID 枚举值，避免侵入 B07 佣金计算模块
#   未知状态返回 None（不变更订单状态）

# 通用状态字符串映射（中文名/英文枚举，无渠道冲突）
CHANNEL_ORDER_STATUS_COMMON_MAP: dict = {
    "待付款": int(OrderStatus.PENDING),
    "PAYING": int(OrderStatus.PENDING),
    "已付款": int(OrderStatus.SETTLABLE),
    "PAID": int(OrderStatus.SETTLABLE),
    "已确认收货": int(OrderStatus.SETTLABLE),
    "CONFIRMED": int(OrderStatus.SETTLABLE),
    "已结算": int(OrderStatus.SETTLED),
    "SETTLED": int(OrderStatus.SETTLED),
    "订单失效": int(OrderStatus.INVALID),
    "失效": int(OrderStatus.INVALID),
    "INVALID": int(OrderStatus.INVALID),
    "已退款": int(OrderStatus.REFUNDED),
    "REFUNDED": int(OrderStatus.REFUNDED),
}

# 渠道专属数字状态码映射（解决同码不同义冲突，如 "3" 在喵有券=付款中、在大淘客=结算）
CHANNEL_ORDER_STATUS_MYQ_MAP: dict = {
    "3": int(OrderStatus.PENDING),  # 喵有券 code=3 付款中
    "12": int(OrderStatus.SETTLABLE),  # 喵有券 code=12 已付款
    "14": int(OrderStatus.SETTLABLE),  # 喵有券 code=14 已确认收货
    "4": int(OrderStatus.SETTLED),  # 喵有券 code=4 已结算
    "13": int(OrderStatus.INVALID),  # 喵有券 code=13 失效
}

CHANNEL_ORDER_STATUS_ORDERX_MAP: dict = {
    "3": int(OrderStatus.PENDING),  # 订单侠 code=3 付款中
    "12": int(OrderStatus.SETTLABLE),  # 订单侠 code=12 已付款
    "14": int(OrderStatus.SETTLABLE),  # 订单侠 code=14 已确认收货
    "4": int(OrderStatus.SETTLED),  # 订单侠 code=4 已结算
    "13": int(OrderStatus.INVALID),  # 订单侠 code=13 失效
}

CHANNEL_ORDER_STATUS_DTA_MAP: dict = {
    "1": int(OrderStatus.PENDING),  # 大淘客 code=1 待付款
    "2": int(OrderStatus.SETTLABLE),  # 大淘客 code=2 已付款
    "3": int(
        OrderStatus.SETTLED
    ),  # 大淘客 code=3 已结算（注意：与喵有券/订单侠的 3 冲突）
    "-1": int(OrderStatus.INVALID),  # 大淘客 code=-1 失效
}

# channel_code → 渠道专属映射表
CHANNEL_ORDER_STATUS_BY_CODE: dict = {
    "myq": CHANNEL_ORDER_STATUS_MYQ_MAP,
    "orderx": CHANNEL_ORDER_STATUS_ORDERX_MAP,
    "dta": CHANNEL_ORDER_STATUS_DTA_MAP,
}
