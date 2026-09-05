# @ai-generated
"""M07-2 运维监控 API 与渠道报错统计 单元测试"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.sentry_stats_util import (  # noqa: E402
    _channel_codes,
    _fetch_from_local_log,
    get_channel_error_stats,
)
from src.config.env_config import EnvConfig  # noqa: E402
from src.config.b13_b14_constants import PERM_OPS_MONITOR  # noqa: E402


class TestChannelCodes:
    """渠道编码枚举读取"""

    def test_contains_myq(self):
        assert "myq" in _channel_codes()

    def test_contains_orderx(self):
        assert "orderx" in _channel_codes()


class TestLocalLogFallback:
    """本地日志回退统计"""

    def test_missing_log_returns_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.common.sentry_stats_util._LOG_DIR", str(tmp_path))
        data = _fetch_from_local_log(7)
        assert data["channels"]["myq"]["error_count"] == 0

    def test_counts_channel_errors(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "app.log"
        now = datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        log_file.write_text(
            f"{ts},123 - api.channel - ERROR - [myq] 渠道请求失败\n"
            f"{ts},123 - api.channel - ERROR - [喵有券] 超时\n"
            f"{ts},123 - api.channel - ERROR - [orderx] 签名错误\n"
            f"{ts},123 - api.channel - INFO - [myq] 正常请求\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("src.common.sentry_stats_util._LOG_DIR", str(log_dir))
        data = _fetch_from_local_log(7)
        assert data["channels"]["myq"]["error_count"] == 2
        assert data["channels"]["orderx"]["error_count"] == 1
        assert data["channels"]["myq"]["last_error_at"] == ts


class TestGetChannelErrorStats:
    """渠道报错统计入口"""

    def test_fallback_when_sentry_not_configured(self, monkeypatch):
        monkeypatch.setattr(EnvConfig, "SENTRY_AUTH_TOKEN", "")
        monkeypatch.setattr(EnvConfig, "SENTRY_ORG_SLUG", "")
        monkeypatch.setattr(EnvConfig, "SENTRY_PROJECT_SLUG", "")
        monkeypatch.setattr(
            "src.common.sentry_stats_util._fetch_from_local_log",
            lambda days: {"channels": {"myq": {"error_count": 1, "last_error_at": ""}}},
        )
        data = asyncio.run(get_channel_error_stats(7))
        assert data["source"] == "local_log"
        assert data["channels"]["myq"]["error_count"] == 1

    def test_sentry_path_when_configured(self, monkeypatch):
        monkeypatch.setattr(EnvConfig, "SENTRY_AUTH_TOKEN", "token")
        monkeypatch.setattr(EnvConfig, "SENTRY_ORG_SLUG", "org")
        monkeypatch.setattr(EnvConfig, "SENTRY_PROJECT_SLUG", "proj")

        async def fake_fetch(days):
            return {"channels": {"myq": {"error_count": 5, "last_error_at": "2026-08-14 10:00:00"}}}

        monkeypatch.setattr("src.common.sentry_stats_util._fetch_from_sentry", fake_fetch)
        data = asyncio.run(get_channel_error_stats(7))
        assert data["source"] == "sentry"
        assert data["channels"]["myq"]["error_count"] == 5

    def test_sentry_failure_falls_back(self, monkeypatch):
        monkeypatch.setattr(EnvConfig, "SENTRY_AUTH_TOKEN", "token")
        monkeypatch.setattr(EnvConfig, "SENTRY_ORG_SLUG", "org")
        monkeypatch.setattr(EnvConfig, "SENTRY_PROJECT_SLUG", "proj")

        async def fake_fetch(days):
            raise RuntimeError("Sentry API down")

        monkeypatch.setattr("src.common.sentry_stats_util._fetch_from_sentry", fake_fetch)
        monkeypatch.setattr(
            "src.common.sentry_stats_util._fetch_from_local_log",
            lambda days: {"channels": {"myq": {"error_count": 2, "last_error_at": ""}}},
        )
        data = asyncio.run(get_channel_error_stats(7))
        assert data["source"] == "local_log"
        assert data["channels"]["myq"]["error_count"] == 2


class TestOpsMonitorPermission:
    """运维监控权限码"""

    def test_permission_constant(self):
        assert PERM_OPS_MONITOR == "ops:monitor"
