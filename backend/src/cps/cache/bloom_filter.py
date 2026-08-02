# @ai-generated
"""
商品 ID 布隆过滤器（Redis bitmap 实现）

用途：防缓存穿透——goods_id 不在过滤器中时直接返回，不查缓存不回源。
特性：
- 存在 false positive（误判"可能存在"），但无 false negative（说"不存在"一定不存在）
- 误判率默认 1%，可配置
- 异常时降级为"可能存在"，避免阻断主流程（软依赖）
"""
import hashlib
import logging
import math
from typing import List

from src.common.redis_client import RedisClient

logger = logging.getLogger("cps.cache.bloom")


class GoodsBloomFilter:
    """基于 Redis bitmap 的布隆过滤器

    Args:
        key: Redis 键名（裸 key，RedisClient.add_prefix 会补 REDIS_PREFIX）
        capacity: 预期元素数量
        error_rate: 可接受的误判率（0~1）
    """

    DEFAULT_KEY = "goods:bloom"
    DEFAULT_CAPACITY = 1_000_000
    DEFAULT_ERROR_RATE = 0.01

    def __init__(
        self,
        key: str = DEFAULT_KEY,
        capacity: int = DEFAULT_CAPACITY,
        error_rate: float = DEFAULT_ERROR_RATE,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if not 0 < error_rate < 1:
            raise ValueError("error_rate must be in (0, 1)")
        self.key = key
        self.capacity = capacity
        self.error_rate = error_rate
        self.bit_size: int = self._optimal_bit_size(capacity, error_rate)
        self.hash_count: int = self._optimal_hash_count(self.bit_size, capacity)

    # ── 参数推导 ────────────────────────────────────────

    @staticmethod
    def _optimal_bit_size(n: int, p: float) -> int:
        """最优位数 m = -n*ln(p) / (ln(2)^2)"""
        return int(-n * math.log(p) / (math.log(2) ** 2))

    @staticmethod
    def _optimal_hash_count(m: int, n: int) -> int:
        """最优哈希函数数 k = (m/n) * ln(2)"""
        return max(1, int(m / n * math.log(2)))

    # ── 哈希位置生成 ────────────────────────────────────

    def _get_positions(self, value: str) -> List[int]:
        """基于 MD5 + 双重哈希生成 k 个位置

        使用 double hashing 技术：h_i(x) = (h1(x) + i * h2(x)) % m
        相比独立盐值更节省计算且分布均匀
        """
        h = hashlib.md5(value.encode("utf-8")).digest()
        # 取前 8 字节作 h1，后 8 字节作 h2
        h1 = int.from_bytes(h[:8], "big")
        h2 = int.from_bytes(h[8:16], "big")
        if h2 == 0:
            h2 = 1  # 避免 h2=0 导致所有位置相同
        positions: List[int] = []
        for i in range(self.hash_count):
            positions.append((h1 + i * h2) % self.bit_size)
        return positions

    # ── 核心操作 ────────────────────────────────────────

    async def add(self, value: str) -> bool:
        """将元素加入布隆过滤器

        Returns:
            True 成功 / False 失败（异常降级，不阻断主流程）
        """
        try:
            client = RedisClient.get_client()
            redis_key = RedisClient.add_prefix(self.key)
            for pos in self._get_positions(value):
                await client.setbit(redis_key, pos, 1)
            return True
        except Exception as e:
            logger.warning(f"BloomFilter add failed for '{value}': {e}")
            return False

    async def exists(self, value: str) -> bool:
        """判断元素是否可能存在

        Returns:
            True 可能存在（有误判）/ False 一定不存在 / 异常时返回 True（降级不阻断）
        """
        try:
            client = RedisClient.get_client()
            redis_key = RedisClient.add_prefix(self.key)
            for pos in self._get_positions(value):
                bit = await client.getbit(redis_key, pos)
                if not bit:
                    return False
            return True
        except Exception as e:
            logger.warning(f"BloomFilter exists failed for '{value}': {e}")
            # 异常时降级为"可能存在"，让主流程走缓存/回源，避免因布隆过滤器故障漏数据
            return True

    async def add_batch(self, values: List[str]) -> int:
        """批量添加元素，返回成功数量"""
        success = 0
        for v in values:
            if await self.add(v):
                success += 1
        return success

    async def clear(self) -> bool:
        """清空过滤器（慎用）"""
        return await RedisClient.delete(self.key) > 0

    # ── 状态查询 ────────────────────────────────────────

    def get_stats(self) -> dict:
        """返回过滤器配置参数（用于调试/监控）"""
        return {
            "key": self.key,
            "capacity": self.capacity,
            "error_rate": self.error_rate,
            "bit_size": self.bit_size,
            "hash_count": self.hash_count,
            "memory_kb": round(self.bit_size / 8 / 1024, 2),
        }
