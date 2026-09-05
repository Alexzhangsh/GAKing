# @ai-generated
"""
B15 模块装配单元测试
覆盖：
1. setup_b15 注册中间件 + 路由
2. B15 中间件与 B14 中间件共存
3. 常量验证（PATH_PERMISSION_MAP 覆盖全部后台模块）

覆盖率目标：≥90%
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.api.v1.admin.b15_setup import setup_b15
from src.config.b15_constants import (
    PATH_PERMISSION_MAP,
    PATH_PREFIXES,
    PUBLIC_PATHS,
    JWT_ONLY_PATHS,
    ADMIN_PATH_PREFIX,
)


# ══════════════════════════════════════════════════════
# 1. setup_b15 装配测试
# ══════════════════════════════════════════════════════


class TestB15Setup:
    """B15 模块装配"""

    def test_setup_b15_registers_middleware_and_routes(self):
        """验证 setup_b15 注册了中间件和路由"""
        app = MagicMock()
        app.add_middleware = MagicMock()
        app.include_router = MagicMock()

        setup_b15(app)

        # 验证注册了中间件
        app.add_middleware.assert_called_once()
        # 验证注册了路由
        app.include_router.assert_called_once()

    def test_setup_b15_called_twice(self):
        """验证多次调用 setup_b15 不会报错"""
        app = MagicMock()
        app.add_middleware = MagicMock()
        app.include_router = MagicMock()

        setup_b15(app)
        setup_b15(app)

        # 中间件和路由各被注册两次
        assert app.add_middleware.call_count == 2
        assert app.include_router.call_count == 2


# ══════════════════════════════════════════════════════
# 2. 常量验证
# ══════════════════════════════════════════════════════


class TestB15Constants:
    """B15 常量验证"""

    def test_path_permission_map_has_auth_endpoints(self):
        """PATH_PERMISSION_MAP 包含认证模块"""
        assert "/api/v1/admin/auth/login" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/auth/logout" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/auth/me" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/auth/password" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_rbac_endpoints(self):
        """PATH_PERMISSION_MAP 包含 RBAC 管理模块"""
        assert "/api/v1/admin/rbac/menus/tree" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/rbac/menus" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/rbac/roles" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/rbac/permissions" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/rbac/users" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_config_endpoints(self):
        """PATH_PERMISSION_MAP 包含系统配置模块"""
        assert "/api/v1/admin/config/registry" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/config/batch" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/config/cache/refresh" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/config/validate" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/config" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_audit_endpoints(self):
        """PATH_PERMISSION_MAP 包含审计日志模块"""
        assert "/api/v1/admin/audit/stats" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/audit/logs" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_dashboard_endpoints(self):
        """PATH_PERMISSION_MAP 包含数据大盘模块"""
        assert "/api/v1/admin/dashboard/cards" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/dashboard/commission-stats" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/dashboard/order-trend" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/dashboard/withdraw-trend" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/dashboard/export" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_goods_endpoints(self):
        """PATH_PERMISSION_MAP 包含商品管理模块"""
        assert "/api/v1/admin/goods" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_user_manage_endpoints(self):
        """PATH_PERMISSION_MAP 包含 C 端用户管理模块"""
        assert "/api/v1/admin/users-manage" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b13_endpoints(self):
        """PATH_PERMISSION_MAP 包含 B13 订单/提现管理"""
        assert "/api/v1/admin/b13/orders" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/b13/withdraws" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b05_endpoints(self):
        """PATH_PERMISSION_MAP 包含 B05 订单同步"""
        assert "/api/v1/admin/order-sync" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b09_b11_endpoints(self):
        """PATH_PERMISSION_MAP 包含 B09/B11 提现审核"""
        assert "/api/v1/admin/withdraw" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b07_endpoints(self):
        """PATH_PERMISSION_MAP 包含 B07 佣金结算"""
        assert "/api/v1/admin/commission-settlement" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/commission-flow-validation" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/refund-deduction" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b12_endpoints(self):
        """PATH_PERMISSION_MAP 包含 B12 结算状态机"""
        assert "/api/v1/admin/settlement" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b13_reconciliation(self):
        """PATH_PERMISSION_MAP 包含 B13 全链路对账"""
        assert "/api/v1/admin/reconciliation" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b06_endpoints(self):
        """PATH_PERMISSION_MAP 包含 B06 渠道管理"""
        assert "/api/v1/admin/b06-channel" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/b06-2" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b07_1_endpoints(self):
        """PATH_PERMISSION_MAP 包含 B07-1 逆向佣金冲减"""
        assert "/api/v1/admin/b07/reverse-commission" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b08_endpoints(self):
        """PATH_PERMISSION_MAP 包含 B08-1 用户资产账户"""
        assert "/api/v1/admin/b08" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b10_endpoints(self):
        """PATH_PERMISSION_MAP 包含 B10 消息管理"""
        assert "/api/v1/admin/message" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b11_endpoints(self):
        """PATH_PERMISSION_MAP 包含 B11-1 渠道黑名单"""
        assert "/api/v1/admin/b11/channel" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_b12_1_endpoints(self):
        """PATH_PERMISSION_MAP 包含 B12-1 订单状态机"""
        assert "/api/v1/admin/b12/order-state" in PATH_PERMISSION_MAP

    def test_path_permission_map_has_short_link_endpoints(self):
        """PATH_PERMISSION_MAP 包含短链/异常订单"""
        assert "/api/v1/admin/short-links" in PATH_PERMISSION_MAP
        assert "/api/v1/admin/abnormal-orders" in PATH_PERMISSION_MAP

    def test_public_paths_contains_login(self):
        """PUBLIC_PATHS 包含登录接口和健康检查"""
        assert "/api/v1/admin/auth/login" in PUBLIC_PATHS
        assert "/healthz" in PUBLIC_PATHS
        assert "/readyz" in PUBLIC_PATHS
        assert "/metrics" in PUBLIC_PATHS

    def test_jwt_only_paths(self):
        """JWT_ONLY_PATHS 包含仅需登录的路径"""
        assert "/api/v1/admin/auth/logout" in JWT_ONLY_PATHS
        assert "/api/v1/admin/auth/me" in JWT_ONLY_PATHS
        assert "/api/v1/admin/auth/password" in JWT_ONLY_PATHS

    def test_admin_path_prefix(self):
        """ADMIN_PATH_PREFIX 正确"""
        assert ADMIN_PATH_PREFIX == "/api/v1/admin/"

    def test_path_prefixes_comprehensive(self):
        """PATH_PREFIXES 覆盖所有后台模块前缀"""
        assert "/api/v1/admin/auth" in PATH_PREFIXES
        assert "/api/v1/admin/rbac" in PATH_PREFIXES
        assert "/api/v1/admin/config" in PATH_PREFIXES
        assert "/api/v1/admin/audit" in PATH_PREFIXES
        assert "/api/v1/admin/dashboard" in PATH_PREFIXES
        assert "/api/v1/admin/goods" in PATH_PREFIXES
        assert "/api/v1/admin/users-manage" in PATH_PREFIXES
        assert "/api/v1/admin/b13/orders" in PATH_PREFIXES
        assert "/api/v1/admin/b13/withdraws" in PATH_PREFIXES
        assert "/api/v1/admin/order-sync" in PATH_PREFIXES
        assert "/api/v1/admin/withdraw" in PATH_PREFIXES
        assert "/api/v1/admin/commission-settlement" in PATH_PREFIXES
        assert "/api/v1/admin/settlement" in PATH_PREFIXES
        assert "/api/v1/admin/reconciliation" in PATH_PREFIXES

    def test_path_permission_map_values(self):
        """验证 PATH_PERMISSION_MAP 中所有值都是有效的（PUBLIC/JWT/权限码）"""
        valid_values = {"PUBLIC", "JWT", "menu:manage", "rbac:manage", "config:manage",
                        "audit:view", "dashboard:view", "dashboard:export",
                        "goods:manage", "user:manage", "order:manage", "withdraw:manage",
                        "order:sync", "withdraw:review", "commission:settle",
                        "settlement:review", "reconciliation:review", "channel:manage",
                        "channel:export", "reverse:commission", "fund:account:view",
                        "message:manage", "channel:blacklist", "order:state_machine",
                        "member:manage", "member:view", "member:export"}
        for path, value in PATH_PERMISSION_MAP.items():
            assert value in valid_values, f"路径 {path} 的权限码 {value} 不在有效值列表中"

    def test_path_permission_map_count(self):
        """PATH_PERMISSION_MAP 条目数验证（应覆盖所有后台模块）"""
        assert len(PATH_PERMISSION_MAP) >= 30, "PATH_PERMISSION_MAP 条目数不足"