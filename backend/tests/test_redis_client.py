# @ai-generated
import pytest
from unittest.mock import AsyncMock, patch
from src.common.redis_client import RedisClient


@pytest.mark.asyncio
async def test_redis_prefix():
    assert RedisClient.add_prefix("test_key") == "gaking:prod:test_key"
    assert RedisClient.add_prefix("gaking:prod:existing_key") == "gaking:prod:existing_key"


@pytest.mark.asyncio
async def test_redis_get_set():
    mock_client = AsyncMock()
    mock_client.get.return_value = "test_value"
    
    with patch.object(RedisClient, '_client', mock_client):
        result = await RedisClient.get("test_key")
        assert result == "test_value"
        mock_client.get.assert_called_once_with("gaking:prod:test_key")


@pytest.mark.asyncio
async def test_redis_set():
    mock_client = AsyncMock()
    mock_client.set.return_value = True
    
    with patch.object(RedisClient, '_client', mock_client):
        result = await RedisClient.set("test_key", "test_value", 60)
        assert result == True
        mock_client.set.assert_called_once_with("gaking:prod:test_key", "test_value")
        mock_client.expire.assert_called_once_with("gaking:prod:test_key", 60)


@pytest.mark.asyncio
async def test_redis_json_operations():
    mock_client = AsyncMock()
    mock_client.get.return_value = '{"key": "value"}'
    
    with patch.object(RedisClient, '_client', mock_client):
        result = await RedisClient.get_json("test_key")
        assert result == {"key": "value"}
    
    mock_client.set.return_value = True
    with patch.object(RedisClient, '_client', mock_client):
        result = await RedisClient.set_json("test_key", {"key": "value"}, 60)
        assert result == True