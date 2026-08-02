# @ai-generated
"""
CPS 适配器工厂
按 channel_code 选择 B01 已实现的渠道适配器实例，并包装熔断器
不修改 B01 适配器内部逻辑，仅做实例化选择 + 熔断增强
"""
import logging
from typing import Dict

from src.cps.adapter.base_adapter import BaseCpsAdapter
from src.cps.adapter.dataoke_adapter import DataokeAdapter
from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter
from src.cps.adapter.miaoyouquan_adapter import MiaoyouquanAdapter
from src.cps.circuit_breaker_adapter import CircuitBreakerAdapter

logger = logging.getLogger("cps.adapter_factory")


class AdapterFactory:
    """CPS 适配器工厂

    按 channel_code 返回对应渠道适配器实例（已包装熔断器）
    支持的渠道：myq(喵有券) / orderx(订单侠) / dta(大淘客)
    """

    # channel_code → 适配器类
    _ADAPTER_CLASSES: Dict[str, type] = {
        "myq": MiaoyouquanAdapter,
        "orderx": DingdanxiaAdapter,
        "dta": DataokeAdapter,
    }

    # 单例缓存（原始适配器，无状态可复用）
    _raw_instances: Dict[str, BaseCpsAdapter] = {}
    # 包装后适配器缓存（含熔断器）
    _wrapped_instances: Dict[str, BaseCpsAdapter] = {}

    @classmethod
    def get_adapter(cls, channel_code: str) -> BaseCpsAdapter:
        """获取指定渠道的适配器实例（已包装熔断器，单例）

        Args:
            channel_code: 渠道标识 myq / orderx / dta
        Returns:
            包装熔断器的适配器实例（CircuitBreakerAdapter）
        Raises:
            ValueError: 不支持的渠道
        """
        if channel_code not in cls._ADAPTER_CLASSES:
            raise ValueError(
                f"不支持的渠道标识: {channel_code}，支持的渠道: "
                f"{list(cls._ADAPTER_CLASSES.keys())}"
            )

        # 原始适配器单例
        if channel_code not in cls._raw_instances:
            adapter_cls = cls._ADAPTER_CLASSES[channel_code]
            cls._raw_instances[channel_code] = adapter_cls()
            logger.info(
                f"创建原始适配器实例: channel={channel_code} "
                f"name={cls._raw_instances[channel_code].get_channel_name()}"
            )

        # 包装熔断器（单例）
        if channel_code not in cls._wrapped_instances:
            cls._wrapped_instances[channel_code] = CircuitBreakerAdapter(
                cls._raw_instances[channel_code]
            )
            logger.info(f"创建熔断包装适配器: channel={channel_code}")

        return cls._wrapped_instances[channel_code]

    @classmethod
    def get_raw_adapter(cls, channel_code: str) -> BaseCpsAdapter:
        """获取原始适配器（不含熔断，仅调试/测试用）

        Args:
            channel_code: 渠道标识
        Returns:
            原始 B01 适配器实例
        """
        if channel_code not in cls._ADAPTER_CLASSES:
            raise ValueError(
                f"不支持的渠道标识: {channel_code}，支持的渠道: "
                f"{list(cls._ADAPTER_CLASSES.keys())}"
            )
        if channel_code not in cls._raw_instances:
            adapter_cls = cls._ADAPTER_CLASSES[channel_code]
            cls._raw_instances[channel_code] = adapter_cls()
        return cls._raw_instances[channel_code]

    @classmethod
    def get_supported_channels(cls) -> list:
        """返回支持的渠道标识列表"""
        return list(cls._ADAPTER_CLASSES.keys())

    @classmethod
    def clear_instances(cls) -> None:
        """清空单例缓存（测试用）"""
        cls._raw_instances.clear()
        cls._wrapped_instances.clear()
