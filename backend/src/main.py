# @ai-generated
import logging
import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config.env_config import EnvConfig
from src.db.init_db import DatabaseManager
from src.common.redis_client import RedisClient
from src.common.cdn_url_util import CdnUrlUtil
from src.common.obs_util import ObsUtil
from src.common.log_util import LogConfig
from src.common.auth_util import JwtAuthGuard
from src.common.security_middleware import SecurityMiddleware
from src.scheduler.scheduler import TaskScheduler
from src.scheduler.tasks import register_tasks
from src.api.health import router as health_router, inc_request_count, inc_error_count

# TODO(2026-08-01): config_router 暂停挂载——config_service.py / schemas/config.py 仍基于
# 旧 Gaking* 模型 schema（sort_num/config_desc/pay_type/third_field 等），与已迁移至
# src/models/system/ 的新模型(SystemConfig/PayConfig/CloudConfig/ChannelMapping)字段不兼容，
# 且 ChannelMapping 语义已从"字段映射表"改为"渠道API凭证表"。需单独排期重写 config API 层后恢复。
# from src.api.config import router as config_router
from src.api.v1 import (
    cps_order_router,
    cps_commission_router,
    withdraw_router,
    withdraw_review_router,
    order_sync_router,
    commission_settlement_router,
)
from src.api.public import cps_goods_router

logger = logging.getLogger("main")

http_client: httpx.AsyncClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        f"[startup] Starting GAKing CPS Backend (env={EnvConfig.ENVIRONMENT})..."
    )
    logger.info(
        f"[startup] Loaded config: db={EnvConfig.DB_HOST}:{EnvConfig.DB_PORT}/{EnvConfig.DB_DATABASE}, "
        f"redis={EnvConfig.REDIS_HOST}:{EnvConfig.REDIS_PORT}"
    )

    EnvConfig.validate()
    logger.info("[startup] EnvConfig validation passed")

    LogConfig.initialize()
    logger.info("[startup] Logging initialized")

    DatabaseManager.initialize()
    logger.info(f"[startup] MySQL engine initialized: {EnvConfig.get_db_url_safe()}")

    RedisClient.initialize()
    logger.info(
        f"[startup] Redis client initialized: {EnvConfig.REDIS_HOST}:{EnvConfig.REDIS_PORT}"
    )

    global http_client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    logger.info("[startup] httpx global AsyncClient initialized")

    CdnUrlUtil.initialize()
    logger.info("[startup] CDN URL utility initialized")

    ObsUtil.initialize()
    logger.info("[startup] OBS utility initialized")

    JwtAuthGuard.initialize()
    logger.info("[startup] JWT auth guard initialized")

    if EnvConfig.SCHEDULER_ENABLE:
        TaskScheduler.initialize()
        register_tasks()
        TaskScheduler.start()
        logger.info("[startup] APScheduler started with registered tasks")

    logger.info("[startup] GAKing CPS Backend started successfully")
    yield

    logger.info("[shutdown] Shutting down GAKing CPS Backend...")

    if EnvConfig.SCHEDULER_ENABLE:
        TaskScheduler.shutdown(wait=False)
        logger.info("[shutdown] APScheduler stopped")

    if http_client is not None:
        await http_client.aclose()
        logger.info("[shutdown] httpx client closed")

    await RedisClient.close()
    logger.info("[shutdown] Redis client closed")

    await DatabaseManager.dispose()
    logger.info("[shutdown] MySQL engine disposed")

    logger.info("[shutdown] GAKing CPS Backend shut down completely")


app = FastAPI(
    title="金角大王CPS返利微信小程序",
    version="1.0.0",
    description="金角大王CPS返利微信小程序后端API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=EnvConfig.CORS_ORIGINS.split(",") if EnvConfig.CORS_ORIGINS else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SecurityMiddleware)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    inc_request_count()
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        inc_error_count()
        raise


app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(health_router)
# config_router 暂停挂载（见上方 TODO）
# app.include_router(config_router)
app.include_router(cps_order_router)
app.include_router(cps_commission_router)
app.include_router(withdraw_router)
app.include_router(withdraw_review_router)
app.include_router(cps_goods_router)
app.include_router(order_sync_router)
app.include_router(commission_settlement_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    inc_error_count()
    return Response(
        status_code=500,
        content={"detail": "Internal server error", "message": str(exc)},
        media_type="application/json",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=EnvConfig.PORT,
        reload=EnvConfig.is_development(),
    )
