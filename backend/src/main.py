# @ai-generated
import asyncio
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
from src.common.lock_util import LockUtil

from src.scheduler.scheduler import TaskScheduler
from src.scheduler.tasks import register_tasks
from src.api.health import router as health_router, inc_request_count, inc_error_count

# B14 后台权限统一管控与系统配置模块（新建独立装配入口，不改动 B01-B13 基线）
from src.api.v1.admin.b14_setup import setup_b14, warmup_b14_config

# B13-补全 + B14-补全 商品管理 / C端用户管理 / 数据大盘 装配入口（新建独立文件，不改动 B01-B15 基线）
from src.api.v1.admin.b13_b14_setup import setup_b13_b14

# F04 营销消息 + 渠道配置管理（新建独立路由文件，不改动 B01-B15 基线）
from src.api.v1.admin.b15_message import router as b15_message_router
from src.api.v1.admin.b15_channel import router as b15_channel_router
# F04-2 渠道佣金策略管理
from src.api.v1.admin.f04_channel_commission import router as f04_channel_commission_router
# B06-1 渠道管理模块
from src.api.v1.admin.b06_channel import router as b06_channel_router
# B06-2 渠道报表导出与对账
from src.api.v1.admin.b06_2_channel import router as b06_2_channel_router
# B07-1 逆向佣金冲减
from src.api.v1.admin.b07_1_reverse_commission import router as b07_1_reverse_commission_router
# B08-1 用户佣金资产管理
from src.api.v1.admin.b08_1_account import router as b08_1_account_router
# B10-1 站内消息用户端
from src.api.v1.b10_message import router as b10_message_router
# F05 营销消息订阅用户端
from src.api.v1.b15_message_user import router as b15_message_user_router
# B10-1 后台消息管理
from src.api.v1.admin.b10_message import router as b10_message_admin_router
# B11-1 渠道信息用户端
from src.api.v1.b11_channel import router as b11_channel_router
# B11-1 后台渠道管理
from src.api.v1.admin.b11_channel import router as b11_channel_admin_router
# B17 多渠道对账与聚合统计
from src.api.v1.admin.b17_channel_reconciliation import (
    router as b17_channel_reconciliation_router,
)

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
    settlement_b12_router,
    reconciliation_b13_router,
    track_router,
    short_link_router,
    abnormal_order_router,
    commission_flow_validation_router,
    refund_deduction_router,
    scheduled_task_run_log_router,
    b10_message_router,
    ops_monitor_router,
    member_package_router,
    member_record_router,
)
from src.api.v1.c_user_auth import router as c_user_auth_router
from src.api.public import cps_goods_router
# B05-4 短链重定向公开路由（独立引入，挂载到 /s/）
from src.api.v1.short_link import public_router as short_link_public_router

logger = logging.getLogger("main")

http_client: httpx.AsyncClient = None

# 调度器领导选举：uvicorn 多 worker 下仅 leader worker 运行 APScheduler，
# 避免 4 个调度器实例竞争同一批 Redis 锁导致任务锁冲突
_SCHEDULER_LEADER_KEY = "scheduler:leader"
_SCHEDULER_LEADER_TTL = 600


async def _try_become_scheduler_leader() -> str:
    """尝试成为调度器 leader（Redis 原子锁），失败返回空串"""
    return await LockUtil.acquire_lock(_SCHEDULER_LEADER_KEY, timeout=_SCHEDULER_LEADER_TTL) or ""


async def _renew_scheduler_leader(owner: str) -> None:
    """后台续期 leader 锁，续期失败（锁被接管）则退出"""
    while True:
        await asyncio.sleep(_SCHEDULER_LEADER_TTL / 2)
        if not await LockUtil.renew_lock(_SCHEDULER_LEADER_KEY, owner, timeout=_SCHEDULER_LEADER_TTL):
            logger.warning("[scheduler] leader 锁续期失败，退出调度器")
            break


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

    # B14: 预热系统配置缓存（DB → 内存 → Redis 双层缓存）
    await warmup_b14_config()

    scheduler_leader_owner = ""
    scheduler_renew_task = None
    if EnvConfig.SCHEDULER_ENABLE:
        scheduler_leader_owner = await _try_become_scheduler_leader()
        if scheduler_leader_owner:
            TaskScheduler.initialize()
            register_tasks()
            TaskScheduler.start()
            scheduler_renew_task = asyncio.create_task(_renew_scheduler_leader(scheduler_leader_owner))
            logger.info("[startup] APScheduler started (leader worker)")
        else:
            logger.info("[startup] APScheduler skipped (non-leader worker)")

    logger.info("[startup] GAKing CPS Backend started successfully")
    yield

    logger.info("[shutdown] Shutting down GAKing CPS Backend...")

    if EnvConfig.SCHEDULER_ENABLE:
        if scheduler_renew_task is not None:
            scheduler_renew_task.cancel()
            try:
                await scheduler_renew_task
            except asyncio.CancelledError:
                pass
        TaskScheduler.shutdown(wait=False)
        if scheduler_leader_owner:
            await LockUtil.release_lock(_SCHEDULER_LEADER_KEY, scheduler_leader_owner)
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
app.include_router(settlement_b12_router)
app.include_router(reconciliation_b13_router)
app.include_router(ops_monitor_router)
app.include_router(member_package_router)
app.include_router(member_record_router)
app.include_router(c_user_auth_router)
app.include_router(track_router)

# B05-4 短链管理 & 异常订单管理
app.include_router(short_link_router)
app.include_router(abnormal_order_router)
# B05-4 短链重定向公开路由（挂载到 /s/）
app.include_router(short_link_public_router)

# B05-5 佣金流水结算前置校验
app.include_router(commission_flow_validation_router)

# B05-6 退款冲减管理
app.include_router(refund_deduction_router)

# B05-7 定时任务运行日志管理
app.include_router(scheduled_task_run_log_router)


# B14: 装配后台权限统一管控与系统配置模块（中间件 + 异常处理器 + 4 个路由）
setup_b14(app)

# B15: 装配全局 RBAC 鉴权中间件 + 增强认证路由（中间件 JWT 黑名单校验 + 权限自动检测）
# 必须在 setup_b14 之后调用，B15 中间件后注册但先执行（FastAPI 中间件栈 LIFO）
# B15 路由后注册但优先匹配（FastAPI 路由按注册顺序匹配）
from src.api.v1.admin.b15_setup import setup_b15

setup_b15(app)

# B13-补全 + B14-补全：商品管理 / C端用户管理 / 数据大盘（3 个路由）
setup_b13_b14(app)

# F04：营销消息 + 渠道配置管理（2 个路由）
app.include_router(b15_message_router)
app.include_router(b15_channel_router)

# F04-2：渠道佣金策略管理
app.include_router(f04_channel_commission_router)

# B06-1：渠道管理模块（渠道CRUD + 佣金比例配置 + 数据看板）
app.include_router(b06_channel_router)

# B06-2：渠道订单报表导出与佣金账单对账
app.include_router(b06_2_channel_router)

# B07-1：退款逆向佣金冲减服务
app.include_router(b07_1_reverse_commission_router)

# B08-1：用户佣金资产账户管理
app.include_router(b08_1_account_router)

# B10-1：站内消息用户端 + 后台消息管理
app.include_router(b10_message_router)
app.include_router(b10_message_admin_router)

# F05：营销消息订阅用户端
app.include_router(b15_message_user_router)

# B11-1：渠道信息用户端 + 后台渠道管理
app.include_router(b11_channel_router)
app.include_router(b11_channel_admin_router)

# B12-1：订单状态机管控（状态校验 + 流转执行 + 操作日志）
from src.api.v1.admin.b12_order_state_machine import router as b12_order_state_machine_router
app.include_router(b12_order_state_machine_router)

# B17：多渠道对账差异处理与多渠道聚合统计
app.include_router(b17_channel_reconciliation_router)


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
