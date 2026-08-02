# @ai-generated
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from src.config.env_config import EnvConfig
from src.db.init_db import DatabaseManager
from src.common.redis_client import RedisClient

logger = logging.getLogger("health")

START_TIME = time.time()
_request_count = 0
_error_count = 0
_cache_hit_count = 0
_cache_miss_count = 0
_cps_error_count = 0

router = APIRouter(prefix="", tags=["health"])


@router.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "gaking-cps-backend",
    }


async def _check_mysql() -> Dict[str, str]:
    try:
        async with DatabaseManager.get_session() as session:
            result = await session.execute("SELECT 1")
            result.fetchone()
        return {"status": "connected", "message": "MySQL OK"}
    except Exception as e:
        logger.warning(f"MySQL health check failed: {e}")
        return {"status": "disconnected", "message": str(e)}


async def _check_redis() -> Dict[str, str]:
    try:
        await RedisClient.health_check()
        return {"status": "connected", "message": "Redis PING OK"}
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return {"status": "disconnected", "message": str(e)}


async def _check_obs() -> Dict[str, str]:
    try:
        import httpx
        url = f"{EnvConfig.OBS_ENDPOINT}/{EnvConfig.OBS_BUCKET_NAME}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.head(url)
            if resp.status_code in (200, 301, 403):
                return {"status": "connected", "message": f"OBS HEAD OK (status={resp.status_code})"}
            else:
                return {"status": "disconnected", "message": f"OBS HEAD returned status {resp.status_code}"}
    except ImportError:
        return {"status": "disconnected", "message": "httpx not installed"}
    except Exception as e:
        logger.warning(f"OBS health check failed: {e}")
        return {"status": "disconnected", "message": str(e)}


@router.get("/readyz")
async def readyz(response: Response):
    mysql_result, redis_result, obs_result = await asyncio.gather(
        _check_mysql(), _check_redis(), _check_obs()
    )

    all_ok = (
        mysql_result["status"] == "connected"
        and redis_result["status"] == "connected"
        and obs_result["status"] == "connected"
    )

    response.status_code = 200 if all_ok else 503

    return {
        "status": "ok" if all_ok else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "environment": EnvConfig.ENVIRONMENT,
        "checks": {
            "mysql": mysql_result,
            "redis": redis_result,
            "obs": obs_result,
        },
    }


@router.get("/metrics")
async def metrics():
    uptime_seconds = time.time() - START_TIME
    cache_total = _cache_hit_count + _cache_miss_count
    cache_hit_rate = (_cache_hit_count / cache_total * 100) if cache_total > 0 else 0.0

    db_pool_stats = ""
    try:
        engine = DatabaseManager._engine
        if engine:
            pool = engine.pool
            db_pool_stats = (
                f'db_pool_size {pool.size()}\n'
                f'db_pool_checkedin {pool.checkedin()}\n'
                f'db_pool_overflow {pool.overflow()}\n'
            )
    except Exception:
        pass

    redis_pool_stats = ""
    try:
        pool = RedisClient._pool
        if pool:
            redis_pool_stats = f'redis_max_connections {pool.max_connections}\n'
    except Exception:
        pass

    prometheus_output = (
        "# HELP gaking_requests_total Total number of requests\n"
        "# TYPE gaking_requests_total counter\n"
        f"gaking_requests_total {_request_count}\n"
        "# HELP gaking_errors_total Total number of errors\n"
        "# TYPE gaking_errors_total counter\n"
        f"gaking_errors_total {_error_count}\n"
        "# HELP gaking_cache_hit_rate Cache hit rate percentage\n"
        "# TYPE gaking_cache_hit_rate gauge\n"
        f"gaking_cache_hit_rate {cache_hit_rate:.2f}\n"
        "# HELP gaking_cache_hits_total Total cache hits\n"
        "# TYPE gaking_cache_hits_total counter\n"
        f"gaking_cache_hits_total {_cache_hit_count}\n"
        "# HELP gaking_cache_misses_total Total cache misses\n"
        "# TYPE gaking_cache_misses_total counter\n"
        f"gaking_cache_misses_total {_cache_miss_count}\n"
        "# HELP gaking_cps_errors_total Total CPS channel errors\n"
        "# TYPE gaking_cps_errors_total counter\n"
        f"gaking_cps_errors_total {_cps_error_count}\n"
        "# HELP gaking_uptime_seconds Service uptime in seconds\n"
        "# TYPE gaking_uptime_seconds counter\n"
        f"gaking_uptime_seconds {uptime_seconds:.0f}\n"
        "# HELP gaking_service_info Service information\n"
        "# TYPE gaking_service_info gauge\n"
        f'gaking_service_info{{env="{EnvConfig.ENVIRONMENT}",version="1.0.0"}} 1\n'
        f"{db_pool_stats}"
        f"{redis_pool_stats}"
    )

    return Response(
        content=prometheus_output,
        media_type="text/plain; version=0.0.4; charset=utf-8",
        headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
    )


def inc_request_count():
    global _request_count
    _request_count += 1


def inc_error_count():
    global _error_count
    _error_count += 1


def inc_cache_hit():
    global _cache_hit_count
    _cache_hit_count += 1


def inc_cache_miss():
    global _cache_miss_count
    _cache_miss_count += 1


def inc_cps_error():
    global _cps_error_count
    _cps_error_count += 1
