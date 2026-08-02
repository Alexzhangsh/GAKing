# @ai-generated
"""
CPS 渠道抽象基类 BaseCpsAdapter
定义统一标准接口，三个渠道子类必须全部实现抽象方法
对外统一调用入口，上层业务无需区分渠道
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.cps.adapter.dto import (
    GoodsDTO,
    GoodsSearchResult,
    ConvertLinkResult,
    OrderDTO,
    OrderPullResult,
)

logger = logging.getLogger("cps.adapter.base")


class BaseCpsAdapter(ABC):
    """CPS 渠道抽象基类

    所有 CPS 渠道适配器必须继承此类并实现全部抽象方法
    统一对外接口：商品搜索、链接转链、订单同步、健康探测
    """

    # ── 抽象方法（子类必须实现） ──────────────────────────

    @abstractmethod
    def get_channel_name(self) -> str:
        """获取渠道名称（如 '订单侠' / '喵有券' / '大淘客'）"""
        ...

    @abstractmethod
    def get_channel_code(self) -> str:
        """获取渠道标识（如 'orderx' / 'myq' / 'dta'）"""
        ...

    @abstractmethod
    async def search_goods(
        self,
        keyword: str,
        page: int = 1,
        size: int = 20,
    ) -> GoodsSearchResult:
        """商品搜索接口

        Args:
            keyword: 搜索关键词
            page: 页码（从1开始）
            size: 每页条数
        Returns:
            标准化商品搜索结果（GoodsSearchResult）
        """
        ...

    @abstractmethod
    async def convert_link(
        self,
        original_url: str,
        user_channel_id: str,
    ) -> ConvertLinkResult:
        """链接转链接口

        Args:
            original_url: 原始商品链接
            user_channel_id: 用户渠道溯源标识
        Returns:
            标准化转链结果（ConvertLinkResult）
        """
        ...

    @abstractmethod
    async def pull_order(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> OrderPullResult:
        """订单同步拉取接口

        Args:
            start_time: 拉取起始时间
            end_time: 拉取结束时间
        Returns:
            标准化订单列表（OrderPullResult）
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """渠道健康探测

        Returns:
            渠道接口是否连通
        """
        ...

    # ── 非抽象通用方法（基类提供默认实现） ─────────────────

    def get_pid(self) -> str:
        """获取默认 PID（子类可覆盖）"""
        return ""

    def get_api_key(self) -> str:
        """获取 API Key（子类可覆盖）"""
        return ""

    def get_goods_by_id(self, goods_id: str) -> Optional[GoodsDTO]:
        """通过商品 ID 获取单个商品信息（子类可覆盖）

        默认返回 None，表示当前渠道不支持商品详情查询
        """
        return None

    # ── 内部工具方法 ──────────────────────────────────────

    def _log(self, level: int, msg: str, *args: object) -> None:
        """带渠道标识的日志"""
        tag = f"[{self.get_channel_name()}]"
        if level == logging.DEBUG:
            logger.debug(f"{tag} {msg}", *args)
        elif level == logging.INFO:
            logger.info(f"{tag} {msg}", *args)
        elif level == logging.WARNING:
            logger.warning(f"{tag} {msg}", *args)
        elif level == logging.ERROR:
            logger.error(f"{tag} {msg}", *args)
        elif level == logging.CRITICAL:
            logger.critical(f"{tag} {msg}", *args)
