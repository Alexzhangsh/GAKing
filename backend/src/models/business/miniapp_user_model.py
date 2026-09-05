# @ai-generated
"""
小程序C端用户 ORM 模型
表名：miniapp_user
业务说明：存储微信小程序用户的 openid ↔ 平台 user_id 映射关系，
         支持微信OAuth授权登录（wx.login → code2session → openid）
"""
from sqlalchemy import Column, String, BigInteger, Integer, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class MiniappUser(Base, SerializableMixin, SoftDeleteMixin):
    """小程序C端用户表

    通过 wx.login 获取 code，后端调用微信 code2session 换取 openid，
    按 openid 查找或创建用户记录，user_id 作为全平台统一用户标识
    （与 orders.user_id / user_commission_account.user_id 联动）。
    """

    __tablename__ = "miniapp_user"
    __table_args__ = (
        # openid 唯一索引 —— 微信登录按 openid 查找用户
        Index("idx_openid", "openid", unique=True),
        # user_id 唯一索引 —— 平台用户ID防重
        Index("idx_user_id", "user_id", unique=True),
        {"comment": "小程序C端用户表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 平台用户ID（与 orders / user_commission_account 联动，全局唯一）
    user_id = Column(BigInteger, nullable=False, comment="平台用户ID（全局唯一）")
    # 微信小程序 openid（用户在该小程序的唯一标识）
    openid = Column(String(64), nullable=False, comment="微信小程序openid")
    # 微信_unionid（同主体小程序/公众号互通，可为空）
    unionid = Column(String(64), default="", nullable=False, comment="微信unionid（可为空）")
    # 用户昵称
    nickname = Column(String(64), default="微信用户", nullable=False, comment="用户昵称")
    # 头像URL
    avatar = Column(String(512), default="", nullable=False, comment="头像URL")
    # 会话密钥（code2session 返回，用于解密 encryptedData，短期有效）
    session_key = Column(String(128), default="", nullable=False, comment="微信会话密钥")
    # 账号状态：0-正常 1-禁用
    status = Column(Integer, default=0, nullable=False, comment="账号状态：0-正常 1-禁用")
    # ── 提款报税所需个人资料（用户在个人资料页维护） ──
    phone = Column(String(20), default="", nullable=False, comment="手机号")
    real_name = Column(String(64), default="", nullable=False, comment="真实姓名")
    id_card = Column(String(32), default="", nullable=False, comment="身份证号")
    bank_card = Column(String(32), default="", nullable=False, comment="银行卡号")
    bank_name = Column(String(64), default="", nullable=False, comment="发卡银行（BIN自动识别）")
    bank_branch = Column(String(128), default="", nullable=False, comment="开户支行（用户手动输入）")
