# @ai-generated
"""
X01-1 Mock 用户工具单元测试（纯函数，无 IO 依赖）

覆盖范围：
1. is_mock_openid
   - dev_ 前缀 → True
   - 真实 openid → False
   - 空字符串 / None → False
   - 大小写敏感（dev_ 前缀精确匹配）
2. gen_mock_transfer_batch_id
   - 生成 MOCKBATCH 前缀批次号
   - 与 apply_no 一一对应（确定性）
3. should_simulate_transfer
   - mock openid + 非生产环境 → True
   - mock openid + 生产环境 → False（异常数据，转人工）
   - 真实 openid（任意环境）→ False
"""
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, ".")

from src.common.mock_user_util import (
    MOCK_OPENID_PREFIX,
    MOCK_TRANSFER_BATCH_PREFIX,
    gen_mock_transfer_batch_id,
    is_mock_openid,
    should_simulate_transfer,
)


# ══════════════════════════════════════════════════════
# is_mock_openid
# ══════════════════════════════════════════════════════


class TestIsMockOpenid:
    def test_dev_prefix_true(self):
        assert is_mock_openid("dev_abc123") is True

    def test_real_openid_false(self):
        assert is_mock_openid("oX8Kj5tQ2mWvYzAbCdEfGhIjKlMnOpQr") is False

    def test_empty_string_false(self):
        assert is_mock_openid("") is False

    def test_none_false(self):
        assert is_mock_openid(None) is False

    def test_prefix_case_sensitive(self):
        # 前缀精确匹配，大小写敏感
        assert is_mock_openid("DEV_abc") is False
        assert is_mock_openid("Dev_abc") is False

    def test_dev_prefix_not_at_start_false(self):
        # 仅前缀开头命中，非开头不算
        assert is_mock_openid("ox_dev_abc") is False


# ══════════════════════════════════════════════════════
# gen_mock_transfer_batch_id
# ══════════════════════════════════════════════════════


class TestGenMockTransferBatchId:
    def test_prefix_and_apply_no(self):
        batch_id = gen_mock_transfer_batch_id("GAKW20260814120000123456")
        assert batch_id == "MOCKBATCHGAKW20260814120000123456"
        assert batch_id.startswith(MOCK_TRANSFER_BATCH_PREFIX)

    def test_deterministic(self):
        assert gen_mock_transfer_batch_id("GAKW001") == gen_mock_transfer_batch_id(
            "GAKW001"
        )

    def test_different_apply_no_different_batch(self):
        assert gen_mock_transfer_batch_id("GAKW001") != gen_mock_transfer_batch_id(
            "GAKW002"
        )

    def test_prefix_constant_aligned(self):
        assert MOCK_OPENID_PREFIX == "dev_"
        assert MOCK_TRANSFER_BATCH_PREFIX == "MOCKBATCH"


# ══════════════════════════════════════════════════════
# should_simulate_transfer
# ══════════════════════════════════════════════════════


class TestShouldSimulateTransfer:
    @pytest.mark.parametrize("env", ["development", "testing", "staging"])
    def test_mock_openid_non_production_true(self, env):
        with patch("src.common.mock_user_util.EnvConfig.ENVIRONMENT", env):
            assert should_simulate_transfer("dev_abc123") is True

    def test_mock_openid_production_false(self):
        with patch("src.common.mock_user_util.EnvConfig.ENVIRONMENT", "production"):
            assert should_simulate_transfer("dev_abc123") is False

    def test_real_openid_development_false(self):
        with patch("src.common.mock_user_util.EnvConfig.ENVIRONMENT", "development"):
            assert should_simulate_transfer("oX8Kj5tQ2mWvYzAbCdEfGhIjKlMnOpQr") is False

    def test_real_openid_production_false(self):
        with patch("src.common.mock_user_util.EnvConfig.ENVIRONMENT", "production"):
            assert should_simulate_transfer("oX8Kj5tQ2mWvYzAbCdEfGhIjKlMnOpQr") is False

    def test_empty_openid_false(self):
        with patch("src.common.mock_user_util.EnvConfig.ENVIRONMENT", "development"):
            assert should_simulate_transfer("") is False
