# @ai-generated
"""
前端行为埋点 & 错误日志 ORM 模型
表名：track_event
业务说明：存储小程序前端上报的行为埋点（页面进入/商品点击/分享/下单/提现）
         与错误日志（JS 异常 / 接口报错 / Promise 拒绝）

设计要点：
1. 行为埋点与错误日志共用一张表，通过 event_type 区分
2. 支持批量写入（前端防抖合并上报）
3. user_id 可为 0（匿名用户），登录后携带
4. params / device_info 为 JSON 字符串，便于扩展
"""
from sqlalchemy import Column, String, BigInteger, Integer, Text, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class TrackEvent(Base, SerializableMixin, SoftDeleteMixin):
    """前端行为埋点 & 错误日志表"""

    __tablename__ = "track_event"
    __table_args__ = (
        # event_type 索引 —— 按事件类型查询
        Index("idx_event_type", "event_type"),
        # user_id 索引 —— 按用户查询行为
        Index("idx_track_user_id", "user_id"),
        # create_time 索引 —— 按时间范围查询
        Index("idx_track_create_time", "create_time"),
        # session_id 索引 —— 按会话查询
        Index("idx_session_id", "session_id"),
        {"comment": "前端行为埋点&错误日志表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 用户ID（0=匿名用户，登录后携带）
    user_id = Column(BigInteger, default=0, nullable=False, comment="用户ID（0=匿名）")
    # 事件类型：page_view/goods_click/share/order_create/withdraw_apply/js_error/api_error/promise_reject
    event_type = Column(String(32), nullable=False, comment="事件类型")
    # 事件名称（具体页面/操作名，如 "首页" "商品详情" "复制购买链接"）
    event_name = Column(String(128), default="", nullable=False, comment="事件名称")
    # 页面路径（事件发生时所在页面）
    page_path = Column(String(256), default="", nullable=False, comment="页面路径")
    # 事件参数（JSON 字符串，如 goods_id/share_target/amount 等）
    params = Column(Text, default="", nullable=False, comment="事件参数(JSON)")
    # 设备信息（JSON 字符串，如机型/系统/小程序版本）
    device_info = Column(Text, default="", nullable=False, comment="设备信息(JSON)")
    # 会话ID（前端生成，用于串联同一次小程序会话的所有行为）
    session_id = Column(String(64), default="", nullable=False, comment="会话ID")
    # 事件发生时间戳（ms，前端生成，解决批量上报时间差）
    client_timestamp = Column(BigInteger, default=0, nullable=False, comment="客户端事件时间戳(ms)")
