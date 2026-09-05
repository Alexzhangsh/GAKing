# @ai-generated
"""
微信支付V3模块（B10 新建）

模块结构：
  exceptions.py  - 异常定义与错误码映射
  constants.py   - API常量、Redis键、熔断配置
  signer.py      - 证书加载、SHA256-RSA签名、验签、回调解密
  client.py      - HTTP客户端（httpx async + 重试 + B04熔断）
  service.py     - 转账业务服务层（单笔/批量/查询/回调/幂等）

对外导出：
  WechatPayError           - 统一异常
  WechatPaySigner          - 签名/验签工具
  WechatPayClient          - HTTP客户端
  WechatPayTransferService - 转账业务服务
  create_wechat_pay_service - 工厂方法（从配置创建服务实例）
"""
from src.common.wechat_pay.client import WechatPayClient
from src.common.wechat_pay.exceptions import (
    WechatPayError,
    map_wechat_api_error,
    raise_from_http_error,
)
from src.common.wechat_pay.service import (
    WechatPayTransferService,
    create_wechat_pay_service,
)
from src.common.wechat_pay.signer import WechatPaySigner

__all__ = [
    "WechatPayError",
    "WechatPaySigner",
    "WechatPayClient",
    "WechatPayTransferService",
    "create_wechat_pay_service",
    "map_wechat_api_error",
    "raise_from_http_error",
]
