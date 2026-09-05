# @ai-generated
"""
微信支付V3常量定义（B10 新建）

职责：
1. 微信支付V3 API 基础 URL 与接口路径
2. Redis 幂等键前缀与 TTL
3. 熔断器 channel_code（复用 B04 CircuitBreaker）
4. 请求超时、重试次数等参数

约束：不修改 B01-B09 基线代码中的常量，全部新增
"""
from src.config.constants import REDIS_PREFIX

# ── 微信支付V3 API 基础配置 ────────────────────────────

WECHAT_PAY_BASE_URL = "https://api.mch.weixin.qq.com"

# API 路径
WECHAT_PAY_API_TRANSFER_BATCH = "/v3/transfer/batches"
WECHAT_PAY_API_QUERY_BATCH = "/v3/transfer/batches/batch-id/{batch_id}"
WECHAT_PAY_API_QUERY_DETAIL = (
    "/v3/transfer/batches/batch-id/{batch_id}/details/detail-id/{detail_id}"
)
WECHAT_PAY_API_DOWNLOAD_BILL = "/v3/bill/down/bill"


# ── Redis 幂等键配置（gaking:prod 统一前缀）────────────

# 转账单号幂等记录：gaking:prod:wechat_pay:transfer:{out_batch_no}
# 值：转账结果 JSON（batch_id + 状态 + 创建时间）
CACHE_KEY_TRANSFER_IDEMPOTENT = f"{REDIS_PREFIX}wechat_pay:transfer:"
CACHE_TTL_TRANSFER_IDEMPOTENT = 7 * 24 * 3600  # 7天（覆盖微信对账周期）

# 平台证书缓存：gaking:prod:wechat_pay:platform_cert:{serial_no}
# 值：PEM 格式平台证书（用于验签）
CACHE_KEY_PLATFORM_CERT = f"{REDIS_PREFIX}wechat_pay:platform_cert:"
CACHE_TTL_PLATFORM_CERT = 12 * 3600  # 12小时（微信平台证书有效期通常较长）

# 熔断器 channel_code（复用 B04 CircuitBreaker，独立 channel 不影响 CPS 渠道）
WECHAT_PAY_BREAKER_CHANNEL = "wechat_pay"


# ── HTTP 请求参数 ──────────────────────────────────────

WECHAT_PAY_REQUEST_TIMEOUT = 15.0  # 请求超时（秒）
WECHAT_PAY_MAX_RETRY = 3  # 最大重试次数（不含首次）
WECHAT_PAY_RETRY_BASE_DELAY = 1.0  # 重试基础退避（秒），实际 = base × 2^(attempt-1)


# ── 转账状态映射 ───────────────────────────────────────

# 微信支付V3 转账明细状态 → 统一状态
# 来源：微信支付V3文档
WECHAT_TRANSFER_STATUS_MAP = {
    "ACCEPTED": "PROCESSING",  # 已受理，转账处理中
    "PROCESSING": "PROCESSING",  # 转账中
    "FINISHED": "SUCCESS",  # 转账完成
    "FAIL": "FAILED",  # 转账失败
}


# ── 回调通知常量 ───────────────────────────────────────

# 微信回调请求头字段名
WECHAT_HEADER_TIMESTAMP = "Wechatpay-Timestamp"
WECHAT_HEADER_NONCE = "Wechatpay-Nonce"
WECHAT_HEADER_SIGNATURE = "Wechatpay-Signature"
WECHAT_HEADER_SERIAL = "Wechatpay-Serial"


# ── 转账场景 ───────────────────────────────────────────

# 转账场景ID（由 gaking_pay_config.transfer_scene_id 动态读取，此处仅文档注释）
# 来源：微信支付V3「商家转账到零钱」文档
