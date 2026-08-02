# @ai-generated
import os
import sys
import time
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.helpers import load_mock_json, WEBHOOK_TIMESTAMP_THRESHOLD


@pytest.fixture
def mock_product():
    return load_mock_json("test_product.json")


@pytest.fixture
def mock_internal_order():
    return load_mock_json("test_order.json")


@pytest.fixture
def mock_cps_callback():
    return load_mock_json("cps_order_callback.json")


@pytest.fixture
def mock_wxpay_callback():
    return load_mock_json("wxpay_transfer_callback.json")


@pytest.fixture
def sample_webhook_secret():
    return "test_webhook_secret_2026"


@pytest.fixture
def sample_timestamp():
    return int(time.time())


@pytest.fixture
def expired_timestamp():
    return int(time.time()) - (WEBHOOK_TIMESTAMP_THRESHOLD + 60)


@pytest.fixture
def sample_request_id():
    return "gaking_test_request_20260731001"


@pytest.fixture
def db_session_mock():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.execute.return_value.fetchone = AsyncMock(return_value=(1,))
    session.execute.return_value.fetchall = AsyncMock(return_value=[])
    return session


@pytest.fixture
def redis_client_mock():
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=0)
    client.expire = AsyncMock(return_value=True)
    return client


@pytest.fixture
def httpx_client_mock():
    client = AsyncMock()
    return client


@pytest.fixture
def mock_app():
    from fastapi import FastAPI
    from tests.api.mock_api import router
    app = FastAPI()
    app.include_router(router)
    return app
