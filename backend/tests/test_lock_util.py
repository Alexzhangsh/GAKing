# @ai-generated
"""
S04 P2-1 定时任务锁冲突逻辑优化单元测试
覆盖：
1. acquire_lock：Lua 原子脚本获取锁（成功/失败/异常）
2. release_lock：Lua 原子释放锁（成功/非owner不删）
3. is_locked / renew_lock / force_release / get_lock_owner / get_remaining_time
4. record_lock_conflict：锁冲突计数 + TTL
5. acquire_with_wait：等待重试获取锁

覆盖率目标：src/common/lock_util.py 核心分支 ≥90%
"""
import sys
import time
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, ".")

from src.common.lock_util import LockUtil
from src.config.constants import LOCK_PREFIX


# ══════════════════════════════════════════════════════
# 1. 获取锁（Lua 原子脚本）
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_acquire_lock_success():
    """获取锁成功：eval_script 返回 1 → 返回 owner"""
    with patch("src.common.lock_util.RedisClient.eval_script", new=AsyncMock(return_value=1)) as mock_eval:
        owner = await LockUtil.acquire_lock("task:sync", timeout=30)
    assert owner is not None
    mock_eval.assert_awaited_once()
    args = mock_eval.call_args.args
    assert args[1] == 1  # numkeys
    assert args[2] == f"{LOCK_PREFIX}task:sync"  # lock_key
    assert args[3] == owner  # owner


@pytest.mark.asyncio
async def test_acquire_lock_failure():
    """获取锁失败：eval_script 返回 0 → 返回 None"""
    with patch("src.common.lock_util.RedisClient.eval_script", new=AsyncMock(return_value=0)):
        owner = await LockUtil.acquire_lock("task:sync", timeout=30)
    assert owner is None


@pytest.mark.asyncio
async def test_acquire_lock_eval_error_returns_none():
    """eval_script 异常返回 None → acquire 返回 None"""
    with patch("src.common.lock_util.RedisClient.eval_script", new=AsyncMock(return_value=None)):
        owner = await LockUtil.acquire_lock("task:sync", timeout=30)
    assert owner is None


# ══════════════════════════════════════════════════════
# 2. 释放锁（Lua 原子脚本）
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_release_lock_success():
    """释放锁成功：eval_script 返回 1 → True"""
    with patch("src.common.lock_util.RedisClient.eval_script", new=AsyncMock(return_value=1)) as mock_eval:
        ok = await LockUtil.release_lock("task:sync", "owner-1")
    assert ok is True
    args = mock_eval.call_args.args
    assert args[1] == 1
    assert args[2] == f"{LOCK_PREFIX}task:sync"
    assert args[3] == "owner-1"


@pytest.mark.asyncio
async def test_release_lock_not_owner():
    """非 owner 释放：eval_script 返回 0 → False"""
    with patch("src.common.lock_util.RedisClient.eval_script", new=AsyncMock(return_value=0)):
        ok = await LockUtil.release_lock("task:sync", "wrong-owner")
    assert ok is False


# ══════════════════════════════════════════════════════
# 3. 锁状态查询 / 续期 / 强制释放
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_is_locked_true():
    """锁存在且未过期 → True"""
    with patch("src.common.lock_util.RedisClient.get", new=AsyncMock(return_value="owner:99999999999")):
        locked = await LockUtil.is_locked("task:sync")
    assert locked is True


@pytest.mark.asyncio
async def test_is_locked_expired():
    """锁存在但已过期 → False"""
    with patch("src.common.lock_util.RedisClient.get", new=AsyncMock(return_value="owner:1")):
        locked = await LockUtil.is_locked("task:sync")
    assert locked is False


@pytest.mark.asyncio
async def test_is_locked_missing():
    """锁不存在 → False"""
    with patch("src.common.lock_util.RedisClient.get", new=AsyncMock(return_value=None)):
        locked = await LockUtil.is_locked("task:sync")
    assert locked is False


@pytest.mark.asyncio
async def test_renew_lock_success():
    """续期成功：owner 匹配 → set + expire"""
    with patch("src.common.lock_util.RedisClient.get", new=AsyncMock(return_value="owner-1:99999999999")), \
         patch("src.common.lock_util.RedisClient.set", new=AsyncMock(return_value=True)) as mock_set, \
         patch("src.common.lock_util.RedisClient.expire", new=AsyncMock(return_value=True)) as mock_expire:
        ok = await LockUtil.renew_lock("task:sync", "owner-1", timeout=30)
    assert ok is True
    mock_set.assert_awaited_once()
    mock_expire.assert_awaited_once()


@pytest.mark.asyncio
async def test_renew_lock_wrong_owner():
    """续期失败：owner 不匹配 → False"""
    with patch("src.common.lock_util.RedisClient.get", new=AsyncMock(return_value="other:99999999999")), \
         patch("src.common.lock_util.RedisClient.set", new=AsyncMock()) as mock_set:
        ok = await LockUtil.renew_lock("task:sync", "owner-1", timeout=30)
    assert ok is False
    mock_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_force_release():
    """强制释放：delete 返回 >0 → True"""
    with patch("src.common.lock_util.RedisClient.delete", new=AsyncMock(return_value=1)):
        ok = await LockUtil.force_release("task:sync")
    assert ok is True


@pytest.mark.asyncio
async def test_get_lock_owner():
    """获取锁 owner"""
    with patch("src.common.lock_util.RedisClient.get", new=AsyncMock(return_value="owner-1:99999999999")):
        owner = await LockUtil.get_lock_owner("task:sync")
    assert owner == "owner-1"


@pytest.mark.asyncio
async def test_get_remaining_time():
    """获取剩余时间"""
    future = time.time() + 25
    with patch("src.common.lock_util.RedisClient.get", new=AsyncMock(return_value=f"owner-1:{future}")):
        remaining = await LockUtil.get_remaining_time("task:sync")
    assert 20 <= remaining <= 25


# ══════════════════════════════════════════════════════
# 4. 锁冲突记录（运维观测）
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_record_lock_conflict():
    """记录锁冲突：incr + expire(7天)"""
    with patch("src.common.lock_util.RedisClient.incr", new=AsyncMock(return_value=1)) as mock_incr, \
         patch("src.common.lock_util.RedisClient.expire", new=AsyncMock(return_value=True)) as mock_expire:
        await LockUtil.record_lock_conflict("order_sync")
    mock_incr.assert_awaited_once()
    mock_expire.assert_awaited_once()
    # TTL = 7 天
    assert mock_expire.call_args.args[1] == 7 * 24 * 3600


# ══════════════════════════════════════════════════════
# 5. 等待获取锁
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_acquire_with_wait_success_first_try():
    """等待获取：首次即成功"""
    with patch("src.common.lock_util.LockUtil.acquire_lock", new=AsyncMock(return_value="owner-1")):
        owner = await LockUtil.acquire_with_wait("task:sync", timeout=30, wait_timeout=5)
    assert owner == "owner-1"


@pytest.mark.asyncio
async def test_acquire_with_wait_timeout():
    """等待获取：超时返回 None"""
    with patch("src.common.lock_util.LockUtil.acquire_lock", new=AsyncMock(return_value=None)):
        owner = await LockUtil.acquire_with_wait(
            "task:sync", timeout=30, wait_timeout=0.1, poll_interval=0.05
        )
    assert owner is None
