# @ai-generated
"""
M07-1 Sentry 全链路监控 - 后端单元测试

覆盖：
- EnvConfig Sentry 配置读取
- sentry_util 各函数在 DSN 为空时静默降级
- before_send 过滤逻辑（已知无害告警）
- 定时任务异常捕获上下文
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.env_config import EnvConfig
from src.common.sentry_util import (
    before_send_handler,
    before_send_transaction_handler,
    capture_exception,
    capture_message,
    clear_user_context,
    init_sentry,
    set_channel_tag,
    set_request_context,
    set_user_context,
)


class TestEnvConfigSentry:
    """EnvConfig Sentry 配置读取"""

    def test_sentry_dsn_default_empty(self):
        assert EnvConfig.SENTRY_DSN == ""

    def test_sentry_sample_rates_default(self):
        assert EnvConfig.SENTRY_TRACES_SAMPLE_RATE == 0.1
        assert EnvConfig.SENTRY_ERROR_SAMPLE_RATE == 1.0

    def test_sentry_config_loaded(self):
        """配置字段已从 env 加载（类型正确）"""
        assert isinstance(EnvConfig.SENTRY_DSN, str)
        assert isinstance(EnvConfig.SENTRY_TRACES_SAMPLE_RATE, float)
        assert isinstance(EnvConfig.SENTRY_ERROR_SAMPLE_RATE, float)


class TestSentryUtilDegrade:
    """DSN 为空时所有函数静默降级，不抛异常"""

    def test_init_sentry_disabled(self):
        # DSN 为空，不应抛异常
        init_sentry()

    def test_capture_exception_disabled(self):
        capture_exception(ValueError("test"))

    def test_capture_message_disabled(self):
        capture_message("test msg")

    def test_set_user_context_disabled(self):
        set_user_context(1, "admin", 1)

    def test_set_channel_tag_disabled(self):
        set_channel_tag("myq")

    def test_set_request_context_disabled(self):
        class FakeRequest:
            headers = {"X-Request-Id": "req_test"}
            url = type("URL", (), {"path": "/api/v1/test"})()
            method = "GET"

        set_request_context(FakeRequest())

    def test_clear_user_context_disabled(self):
        clear_user_context()


class TestBeforeSendFilter:
    """before_send 过滤逻辑"""

    def test_filter_health_check(self):
        event = {"request": {"url": "http://localhost:3001/health"}}
        assert before_send_handler(event, {}) is None

    def test_filter_channel_disabled(self):
        event = {"request": {"url": "http://localhost:3001/api/v1/test"}}
        hint = {"exc_info": (None, ValueError("渠道开关关闭，跳过执行"), None)}
        assert before_send_handler(event, hint) is None

    def test_filter_lock_conflict(self):
        event = {"request": {"url": "http://localhost:3001/api/v1/test"}}
        hint = {"exc_info": (None, ValueError("未获取到分布式锁，跳过"), None)}
        assert before_send_handler(event, hint) is None

    def test_pass_normal_event(self):
        event = {"request": {"url": "http://localhost:3001/api/v1/orders"}}
        hint = {"exc_info": (None, ValueError("数据库连接失败"), None)}
        assert before_send_handler(event, hint) is event

    def test_pass_no_exc_info(self):
        event = {"request": {"url": "http://localhost:3001/api/v1/orders"}}
        assert before_send_handler(event, {}) is event

    def test_filter_health_transaction(self):
        event = {"request": {"url": "http://localhost:3001/health"}}
        assert before_send_transaction_handler(event) is None

    def test_filter_healthz_transaction(self):
        event = {"request": {"url": "http://localhost:3001/healthz"}}
        assert before_send_transaction_handler(event) is None

    def test_filter_readyz_transaction(self):
        event = {"request": {"url": "http://localhost:3001/readyz"}}
        assert before_send_transaction_handler(event) is None

    def test_filter_healthz_event(self):
        event = {"request": {"url": "http://localhost:3001/healthz"}}
        assert before_send_handler(event, {}) is None

    def test_pass_normal_transaction(self):
        event = {"request": {"url": "http://localhost:3001/api/v1/orders"}}
        assert before_send_transaction_handler(event) is event


class TestSchedulerCaptureContext:
    """定时任务异常捕获上下文（模拟 _run_with_lock 的调用方式）"""

    def test_capture_with_task_context(self):
        # 模拟定时任务异常捕获，DSN 为空时静默
        try:
            raise RuntimeError("模拟定时任务失败")
        except Exception as e:
            capture_exception(
                e,
                context={
                    "layer": "backend",
                    "source": "scheduler",
                    "task_name": "close_expired_unpaid_orders",
                },
            )

    def test_capture_with_retry_context(self):
        try:
            raise ConnectionError("模拟网络错误")
        except Exception as e:
            capture_exception(
                e,
                context={
                    "layer": "backend",
                    "source": "scheduler",
                    "task_name": "order_sync_myq",
                    "retry_count": 3,
                },
            )