# @ai-generated
"""
微信 V3 支付配置表 ORM 模型
表名：gaking_pay_config
业务说明：存储微信V3支付商户号、证书序列号、私钥路径、APIv3密钥、
转账场景ID、回调地址等支付相关配置
"""
from sqlalchemy import Column, String, Boolean, Numeric

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class PayConfig(Base, SerializableMixin, SoftDeleteMixin):
    """微信V3支付配置表"""

    __tablename__ = "gaking_pay_config"
    __table_args__ = (
        {
            "comment": "微信V3支付配置表",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 微信商户号
    mch_id = Column(String(64), nullable=False, comment="微信商户号")
    # 商户证书序列号
    serial_no = Column(String(128), default="", comment="商户证书序列号")
    # 商户私钥文件路径
    private_key_path = Column(String(256), default="", comment="商户私钥文件路径")
    # APIv3 密钥（用于回调解密）
    v3_secret = Column(String(128), default="", comment="APIv3密钥，用于回调解密")
    # 微信转账场景ID（商家转账到零钱）
    transfer_scene_id = Column(String(64), default="", comment="微信转账场景ID")
    # 支付/转账回调地址
    notify_url = Column(String(256), default="", comment="支付回调地址")
    # 状态：True-启用 False-禁用
    status = Column(
        Boolean, default=True, nullable=False, comment="状态：0-禁用 1-启用"
    )
    # 备注说明
    remark = Column(String(512), default="", comment="备注说明")
    # 提现费率（动态配置，替代 constants.WITHDRAW_FEE_RATE=0.001）：0.001 = 0.1%
    # 为空时由 PayConfigUtil 兜底使用 constants.WITHDRAW_FEE_RATE，保证降级可用
    withdraw_rate = Column(
        Numeric(5, 4),
        nullable=True,
        comment="提现费率(0~1)，如0.001=0.1%；空值兜底常量",
    )
    # 单笔最低手续费（动态配置，替代 constants.WITHDRAW_FEE_MIN=1.00）
    # 为空时由 PayConfigUtil 兜底使用 constants.WITHDRAW_FEE_MIN，保证降级可用
    withdraw_min_fee = Column(
        Numeric(10, 2),
        nullable=True,
        comment="单笔最低手续费(元)，如1.00；空值兜底常量",
    )
