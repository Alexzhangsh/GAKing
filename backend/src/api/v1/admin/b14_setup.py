# @ai-generated
"""
B14 模块统一装配入口（路由 + 中间件 + 异常处理器 + 配置预热）
新建独立文件，main.py 仅需调用 setup_b14(app) 一行即可挂载全部 B14 组件

职责：
1. 注册 B14RateLimitMiddleware（admin 接口限流，gaking:prod:rate:admin:{ip}）
2. 注册 B14AuditMiddleware（admin 写操作自动审计）
3. 注册 B14 统一异常处理器（HTTPException/ValueError/PyJWT/ValidationError）
4. 挂载 4 个 B14 路由（auth/config/rbac/audit）
5. 启动时预热 B14ConfigUtil（DB → 内存 → Redis 双层缓存）

执行顺序约束：
- 中间件必须在 include_router 前注册
- 异常处理器优先于 main.py 既有的 @app.exception_handler(Exception) 兜底
- 配置预热在 lifespan 中调用（DatabaseManager 初始化后）
"""
import logging

from fastapi import FastAPI

from src.api.v1.admin.b14_audit import router as b14_audit_router
from src.api.v1.admin.b14_auth import router as b14_auth_router
from src.api.v1.admin.b14_config import router as b14_config_router
from src.api.v1.admin.b14_rbac import router as b14_rbac_router
from src.common.b14_audit_middleware import B14AuditMiddleware
from src.common.b14_config_util import B14ConfigUtil
from src.common.b14_exception_handlers import register_b14_exception_handlers
from src.common.b14_rate_limit_middleware import B14RateLimitMiddleware

logger = logging.getLogger("api.admin.b14_setup")


def setup_b14(app: FastAPI) -> None:
    """装配 B14 模块到 FastAPI app

    在 main.py 的 app 创建后、lifespan 启动前调用：
        from src.api.v1.admin.b14_setup import setup_b14
        setup_b14(app)

    包含：
    1. 注册限流 + 审计中间件
    2. 注册统一异常处理器
    3. 挂载 4 个 B14 路由
    """
    # 1. 中间件（注册顺序：后注册先执行；限流最外层，审计次之）
    app.add_middleware(B14AuditMiddleware)
    app.add_middleware(B14RateLimitMiddleware)
    logger.info("[b14_setup] 已注册限流 + 审计中间件")

    # 2. 异常处理器
    register_b14_exception_handlers(app)
    logger.info("[b14_setup] 已注册 B14 统一异常处理器")

    # 3. 路由挂载
    app.include_router(b14_auth_router)
    app.include_router(b14_config_router)
    app.include_router(b14_rbac_router)
    app.include_router(b14_audit_router)
    logger.info(
        "[b14_setup] 已挂载 4 个 B14 路由: auth / config / rbac / audit"
    )


async def warmup_b14_config() -> None:
    """预热 B14 系统配置缓存（在 lifespan 启动阶段调用）

    DatabaseManager 初始化后调用，将 gaking_system_config 全量加载到内存 + Redis
    失败不阻塞启动（B14ConfigUtil 内部已降级处理）
    """
    try:
        await B14ConfigUtil.load_all()
        loaded = len(B14ConfigUtil.get_all_memory())
        logger.info(
            "[b14_setup] B14 系统配置预热完成，加载 %s 项配置", loaded
        )
    except Exception as e:
        logger.warning(
            "[b14_setup] B14 系统配置预热失败，运行时降级到注册表默认值: %s",
            e,
        )
