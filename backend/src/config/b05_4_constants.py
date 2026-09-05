# @ai-generated
"""
B05-4 短链跟单系统常量配置
不修改 B01-B05 已有常量，独立文件单独管理
"""
from enum import IntEnum

# ── 短链参数 ──────────────────────────────────────────────────────
SHORT_LINK_KEY_LENGTH = 8       # 短链 key 长度（base62 编码）
SHORT_LINK_EXPIRE_HOURS = 72    # 短链过期时间（小时），与跟单窗口期一致

# ── 跟单匹配参数 ──────────────────────────────────────────────────
ATTRIBUTION_WINDOW_HOURS = 72            # 跟单窗口期（小时）
ATTRIBUTION_STRATEGY_DEFAULT = "short_link"  # 默认匹配策略：short_link
ATTRIBUTION_STRATEGY_RELATION_ID = "relation_id"  # 预留的 relation-id 模式

# ── 异常订单复核状态 ──────────────────────────────────────────────
class AbnormalReviewStatus:
    PENDING = "PENDING"     # 待审核
    REVIEWED = "REVIEWED"   # 已复核
    IGNORED = "IGNORED"     # 已忽略

# ── 异常原因常量 ──────────────────────────────────────────────────
ABNORMAL_REASON_NO_CLICK = "72小时窗口内无匹配点击记录"
ABNORMAL_REASON_MULTI_USER = "72小时窗口内存在多个用户点击记录，无法自动归属"
ABNORMAL_REASON_CLICK_EXPIRED = "短链已过期且无有效点击记录"

# ── Redis 键前缀（B05-4 专用） ────────────────────────────────────
# 由 constants.py 中的 REDIS_PREFIX 拼接，此处仅定义后缀
CACHE_KEY_SHORT_LINK_PREFIX = "short_link:"  # 短链缓存：gaking:prod:short_link:{key}
CACHE_TTL_SHORT_LINK = 3600  # 短链缓存 TTL（秒），1小时

# ── 短链重定向 URL 前缀 ──────────────────────────────────────────
# 生产环境需通过 EnvConfig 或后台配置，此处为兜底占位
SHORT_LINK_REDIRECT_BASE_URL = "/s"

# ── 异常订单定时巡检参数 ──────────────────────────────────────────
# 任务开关
TASK_ABNORMAL_WATCHDOG_ENABLE = True
# 执行频率：每 2 小时
TASK_CRON_ABNORMAL_WATCHDOG = "0 */2 * * *"
# 分布式锁超时（秒）
TASK_ABNORMAL_WATCHDOG_LOCK_TIMEOUT = 120
# 巡检告警阈值：当日新增异常订单数超过此值输出 WARNING 级别日志
TASK_ABNORMAL_WATCHDOG_WARN_THRESHOLD = 50