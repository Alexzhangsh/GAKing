# @ai-generated
"""
Mock 用户工具（X01-1 新建）

职责：
1. 识别 mock 用户 openid（dev_ 前缀，开发兜底登录生成）
2. 生成 mock 转账批次号（开发环境模拟打款，避免用假 openid 调真实微信接口）
3. 判定是否应模拟转账（仅 mock openid 且非生产环境）

设计要点：
- 纯函数、无 IO，可安全被 Service/API/测试复用
- mock openid 判定规则与 miniapp_user_service._dev_mock_openid 保持一致（dev_ 前缀）
- 生产环境绝不模拟转账：真实用户走真实微信打款；
  若生产环境出现 mock openid（异常数据），返回 False 走人工打款处理，避免资金状态误判
"""
import logging

from src.config.env_config import EnvConfig

logger = logging.getLogger("common.mock_user_util")

# mock openid 前缀（与 miniapp_user_service._dev_mock_openid 生成规则一致）
MOCK_OPENID_PREFIX = "dev_"
# mock 转账批次号前缀（开发环境模拟打款，便于与真实微信批次区分）
MOCK_TRANSFER_BATCH_PREFIX = "MOCKBATCH"


def is_mock_openid(openid: str) -> bool:
    """判断 openid 是否为开发 mock openid（dev_ 前缀）

    Args:
        openid: 微信 openid（真实 openid 或开发 mock openid）
    Returns:
        True 表示 mock openid
    """
    if not openid:
        return False
    return openid.startswith(MOCK_OPENID_PREFIX)


def gen_mock_transfer_batch_id(apply_no: str) -> str:
    """生成 mock 转账批次号（开发环境模拟打款用）

    Args:
        apply_no: 提现申请单号（GAKW 开头，全局唯一）
    Returns:
        mock 批次号，如 MOCKBATCHGAKW20260814120000123456
    """
    return f"{MOCK_TRANSFER_BATCH_PREFIX}{apply_no}"


def should_simulate_transfer(openid: str) -> bool:
    """是否应模拟微信转账（mock openid 且非生产环境）

    边界规则：
    - 真实 openid → 不模拟，走真实微信打款
    - mock openid + 非生产环境 → 模拟打款成功，打通全流程自测
    - mock openid + 生产环境 → 不模拟（异常数据），转人工打款处理

    Args:
        openid: 收款用户微信 openid
    Returns:
        True 表示应模拟转账
    """
    if not is_mock_openid(openid):
        return False
    if EnvConfig.is_production():
        logger.warning(
            "[mock_user] 生产环境出现 mock openid=%s，禁止模拟转账，转人工处理",
            openid[:12] + "***",
        )
        return False
    return True
