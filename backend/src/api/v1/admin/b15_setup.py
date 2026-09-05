# @ai-generated
"""
B15 模块统一装配入口（全局 RBAC 鉴权中间件 + 增强路由）
新建独立文件，main.py 仅需调用 setup_b15(app) 一行即可挂载全部 B15 组件

职责：
1. 注册 B15RbacMiddleware 全局 RBAC 鉴权中间件（JWT 校验 + 黑名单 + 权限自动检测）
2. 挂载 B15 增强路由（auth/logout 登出销毁 JWT、auth/password 改密黑名单）
3. 与 B14 模块共存：B15 中间件先于 B14 中间件注册（执行顺序靠前），
   B15 路由先于 B14 路由注册（优先匹配）

执行顺序约束：
- 中间件必须在 include_router 前注册
- B15 路由必须在 B14 路由之前注册（相同路径优先匹配）
- 中间件注册顺序：B15RbacMiddleware（最外层，先拦截）→ B14AuditMiddleware → B14RateLimitMiddleware

与 B14 模块的兼容性：
- B15RbacMiddleware 提供基线防护，B14 require_any_permission 装饰器提供精确防护
- 双层防护不冲突，先通过中间件基线检查，再通过装饰器精确检查
- 存量 B14 接口无需修改，自动获得 B15 中间件防护
"""
import logging

from fastapi import FastAPI

from src.api.v1.admin.b15_auth import router as b15_auth_router
from src.common.b15_rbac_middleware import B15RbacMiddleware

logger = logging.getLogger("api.admin.b15_setup")


def setup_b15(app: FastAPI) -> None:
    """装配 B15 模块到 FastAPI app

    在 main.py 的 setup_b14(app) 之后调用：
        from src.api.v1.admin.b15_setup import setup_b15
        setup_b14(app)  # B14 先注册中间件和路由
        setup_b15(app)  # B15 后注册，B15 中间件在最外层

    注意：
    - B15RbacMiddleware 后注册但先执行（FastAPI 中间件栈是 LIFO 顺序）
    - B15 增强路由后注册，但 FastAPI 按注册顺序优先匹配
      所以 B15 路由的 POST /logout 和 PUT /password 会覆盖 B14 的对应路由
    """
    # 1. 注册全局 RBAC 鉴权中间件
    #    FastAPI 中间件栈：后注册的中间件先执行（LIFO）
    #    因此 B15RbacMiddleware 后注册，但先于 B14 中间件执行
    app.add_middleware(B15RbacMiddleware)
    logger.info("[b15_setup] 已注册全局 RBAC 鉴权中间件")

    # 2. 挂载 B15 增强路由（先于 B14 路由注册，优先匹配）
    #    B15 路由覆盖了 B14 的 /logout 和 /password 端点
    #    未覆盖的 /login 和 /me 仍由 B14 路由处理
    app.include_router(b15_auth_router)
    logger.info("[b15_setup] 已挂载 B15 增强认证路由: auth/logout, auth/password")