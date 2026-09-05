# @ai-generated
"""
B14 系统配置管理 Service（CRUD + 批量更新 + 缓存刷新 + 注册表元信息）
新建独立文件，不修改 B01-B13 任何基线 service

业务流程：
1. list_configs：分页查询 SystemConfig 表（可选 key 模糊筛选）
2. get_config_detail：单 key 详情（含 B14_CONFIG_REGISTRY 元信息 + 当前值）
3. create_config / update_config：写 DB + 失效缓存（B14ConfigUtil.invalidate）
4. batch_update_configs：批量更新开关类配置（仅 task_*_enable 前缀）
5. refresh_cache：手动触发 B14ConfigUtil.refresh()（运维兜底）
6. list_registry：全量注册表 + 当前值（前端配置中心渲染用）
7. validate_config_value：更新前预校验值合法性（类型 + min/max）

设计要点：
- 配置 key 必须在 B14_CONFIG_REGISTRY 白名单内才能创建/更新
- 写操作后调用 B14ConfigUtil.invalidate(key) 触发热生效（DB→内存→Redis）
- 业务异常统一 ValueError，API 层由 handle_service_exception 转 400
"""
import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.b14_config_util import B14ConfigUtil
from src.config.b14_constants import (
    B14_CONFIG_REGISTRY,
    BATCH_UPDATE_KEY_PREFIX,
)
from src.dao.system_config_b14_dao import SystemConfigB14DAO
from src.db.init_db import DatabaseManager
from src.models.system.system_config import SystemConfig
from src.schemas.b14_config import (
    SystemConfigBatchUpdateItem,
    SystemConfigBatchUpdateResponse,
    SystemConfigCreateRequest,
    SystemConfigRegistryItem,
    SystemConfigUpdateRequest,
)

logger = logging.getLogger("service.b14_config")


class B14ConfigService:
    """系统配置管理服务（B14 新建）"""

    # ════════════════════════════════════════════════════
    # 1. 查询
    # ════════════════════════════════════════════════════

    @classmethod
    async def list_configs(
        cls,
        page: int = 1,
        page_size: int = 20,
        config_key: Optional[str] = None,
    ) -> Tuple[List[SystemConfig], int]:
        """分页查询系统配置列表

        Args:
            page: 页码（1 开始）
            page_size: 每页条数
            config_key: 配置键模糊筛选
        Returns:
            (配置列表, 总数)
        """
        async with DatabaseManager.get_session() as session:
            dao = SystemConfigB14DAO(session)
            return await dao.list_with_pagination(
                config_key=config_key,
                page=page,
                page_size=page_size,
            )

    @classmethod
    async def get_config_by_key(cls, config_key: str) -> Optional[SystemConfig]:
        """按 key 查询配置（仅 DB 视角，不含注册表元信息）"""
        async with DatabaseManager.get_session() as session:
            dao = SystemConfigB14DAO(session)
            return await dao.get_by_key(config_key)

    @classmethod
    async def get_config_detail(cls, config_key: str) -> Dict[str, Any]:
        """获取配置详情（DB 记录 + 注册表元信息 + 当前生效值）

        Args:
            config_key: 配置键
        Returns:
            {db_record, registry_meta, current_value}
        Raises:
            ValueError: 配置 key 不在注册表白名单
        """
        registry = B14_CONFIG_REGISTRY.get(config_key)
        if registry is None:
            raise ValueError(f"配置 key '{config_key}' 不在注册表白名单内")

        db_record = await cls.get_config_by_key(config_key)
        current_value = await B14ConfigUtil.get(config_key)

        return {
            "config_key": config_key,
            "config_type": registry["type"],
            "default_value": registry["default"],
            "current_value": current_value,
            "min_value": registry.get("min"),
            "max_value": registry.get("max"),
            "desc": registry.get("desc", ""),
            "db_record": cls._serialize_config(db_record) if db_record else None,
        }

    @classmethod
    async def list_registry(cls) -> List[Dict[str, Any]]:
        """获取全量注册表 + 当前值（前端配置中心渲染用）

        Returns:
            注册表项列表，每项含 key/type/default/current/min/max/desc/config_name
        """
        items: List[Dict[str, Any]] = []
        for key, registry in B14_CONFIG_REGISTRY.items():
            current_value = await B14ConfigUtil.get(key)
            db_record = await cls.get_config_by_key(key)

            def _serialize(val: Any) -> Any:
                """将 Decimal 转为 float，确保 JSON 可序列化"""
                if isinstance(val, Decimal):
                    return float(val)
                return val

            items.append(
                {
                    "config_key": key,
                    "config_type": registry["type"],
                    "default_value": _serialize(registry["default"]),
                    "current_value": _serialize(current_value),
                    "min_value": _serialize(registry.get("min")),
                    "max_value": _serialize(registry.get("max")),
                    "desc": registry.get("desc", ""),
                    "config_name": db_record.config_name if db_record else "",
                }
            )
        return items

    # ════════════════════════════════════════════════════
    # 2. 写操作
    # ════════════════════════════════════════════════════

    @classmethod
    async def create_config(
        cls, request: SystemConfigCreateRequest
    ) -> SystemConfig:
        """新增系统配置

        Args:
            request: 配置创建请求体
        Returns:
            创建的配置实例
        Raises:
            ValueError: key 不在白名单 / 值类型不合法 / key 已存在
        """
        # 校验 key 在注册表白名单内
        if request.config_key not in B14_CONFIG_REGISTRY:
            raise ValueError(
                f"配置 key '{request.config_key}' 不在注册表白名单内，禁止创建"
            )

        # 校验值合法性
        cls._validate_value(request.config_key, request.config_value)

        # 校验 key 未被占用
        existing = await cls.get_config_by_key(request.config_key)
        if existing is not None:
            raise ValueError(f"配置 key '{request.config_key}' 已存在")

        async with DatabaseManager.get_session() as session:
            dao = SystemConfigB14DAO(session)
            config = await dao.upsert_by_key(
                config_key=request.config_key,
                config_value=request.config_value,
                config_name=request.config_name or request.config_key,
                remark=request.remark,
            )
            # 写审计日志（在 API 层由 audit_action 装饰器补全操作人信息）
            logger.info(
                "[b14_config] 新增配置 key=%s value=%s",
                request.config_key,
                request.config_value,
            )

        # 失效缓存（热生效）
        await B14ConfigUtil.invalidate(request.config_key)
        return config

    @classmethod
    async def update_config(
        cls,
        config_key: str,
        request: SystemConfigUpdateRequest,
    ) -> SystemConfig:
        """更新系统配置（仅允许更新 value/name/remark）

        Args:
            config_key: 配置键
            request: 更新请求体
        Returns:
            更新后的配置实例
        Raises:
            ValueError: key 不在白名单 / 值类型不合法
        """
        if config_key not in B14_CONFIG_REGISTRY:
            raise ValueError(
                f"配置 key '{config_key}' 不在注册表白名单内，禁止更新"
            )

        cls._validate_value(config_key, request.config_value)

        existing = await cls.get_config_by_key(config_key)
        if existing is None:
            raise ValueError(f"配置 key '{config_key}' 不存在，请先创建")

        async with DatabaseManager.get_session() as session:
            dao = SystemConfigB14DAO(session)
            config = await dao.upsert_by_key(
                config_key=config_key,
                config_value=request.config_value,
                config_name=request.config_name or "",
                remark=request.remark or "",
            )
            logger.info(
                "[b14_config] 更新配置 key=%s value=%s",
                config_key,
                request.config_value,
            )

        await B14ConfigUtil.invalidate(config_key)
        return config

    @classmethod
    async def batch_update_configs(
        cls, items: List[SystemConfigBatchUpdateItem]
    ) -> SystemConfigBatchUpdateResponse:
        """批量更新配置（仅允许 task_*_enable 开关类）

        Args:
            items: 批量更新项列表
        Returns:
            {updated, skipped, failed}
        """
        updated: List[str] = []
        skipped: List[str] = []
        failed: List[str] = []

        for item in items:
            key = item.config_key
            try:
                # 仅允许 task_*_enable 前缀
                if not key.startswith(BATCH_UPDATE_KEY_PREFIX) and not key.endswith(
                    "_enable"
                ):
                    skipped.append(key)
                    continue

                if key not in B14_CONFIG_REGISTRY:
                    skipped.append(key)
                    continue

                # 校验 bool 类型
                registry = B14_CONFIG_REGISTRY[key]
                if registry["type"] != "bool":
                    skipped.append(key)
                    continue

                # 校验值
                if item.config_value.lower() not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
                    failed.append(key)
                    continue

                async with DatabaseManager.get_session() as session:
                    dao = SystemConfigB14DAO(session)
                    await dao.upsert_by_key(
                        config_key=key,
                        config_value=item.config_value,
                    )
                await B14ConfigUtil.invalidate(key)
                updated.append(key)
                logger.info(
                    "[b14_config] 批量更新 key=%s value=%s", key, item.config_value
                )
            except Exception as e:
                logger.warning(
                    "[b14_config] 批量更新失败 key=%s: %s", key, e
                )
                failed.append(key)

        return SystemConfigBatchUpdateResponse(
            updated=updated, skipped=skipped, failed=failed
        )

    @classmethod
    async def delete_config(cls, config_key: str) -> bool:
        """删除系统配置（软删除）

        Args:
            config_key: 配置键
        Returns:
            True-删除成功
        Raises:
            ValueError: 配置不存在
        """
        existing = await cls.get_config_by_key(config_key)
        if existing is None:
            raise ValueError(f"配置 key '{config_key}' 不存在")

        async with DatabaseManager.get_session() as session:
            dao = SystemConfigB14DAO(session)
            await dao.logic_delete_by_id(existing.id)
            logger.info("[b14_config] 删除配置 key=%s", config_key)

        # 失效缓存（删除后读取会降级到注册表默认值）
        await B14ConfigUtil.invalidate(config_key)
        return True

    # ════════════════════════════════════════════════════
    # 3. 缓存管理
    # ════════════════════════════════════════════════════

    @classmethod
    async def refresh_cache(cls) -> Dict[str, Any]:
        """手动刷新配置缓存（运维兜底，全量重新加载）

        Returns:
            {success, loaded_count, message}
        """
        try:
            await B14ConfigUtil.refresh()
            loaded_count = len(B14ConfigUtil.get_all_memory())
            logger.info("[b14_config] 缓存刷新成功 loaded_count=%s", loaded_count)
            return {
                "success": True,
                "loaded_count": loaded_count,
                "message": "缓存刷新成功",
            }
        except Exception as e:
            logger.error("[b14_config] 缓存刷新失败: %s", e, exc_info=True)
            return {
                "success": False,
                "loaded_count": 0,
                "message": f"缓存刷新失败: {e}",
            }

    # ════════════════════════════════════════════════════
    # 4. 值校验
    # ════════════════════════════════════════════════════

    @classmethod
    def validate_config_value(
        cls, config_key: str, config_value: str
    ) -> Dict[str, Any]:
        """校验配置值合法性（不写 DB）

        Args:
            config_key: 配置键
            config_value: 待校验值
        Returns:
            {valid, parsed_value, error_message}
        """
        try:
            parsed = cls._validate_value(config_key, config_value)
            return {"valid": True, "parsed_value": parsed, "error_message": None}
        except ValueError as e:
            return {"valid": False, "parsed_value": None, "error_message": str(e)}

    # ════════════════════════════════════════════════════
    # 内部工具方法
    # ════════════════════════════════════════════════════

    @classmethod
    def _validate_value(cls, config_key: str, config_value: str) -> Any:
        """校验配置值类型 + 范围，返回解析后的值

        Args:
            config_key: 配置键
            config_value: 配置值字符串
        Returns:
            解析后的值（int/bool/Decimal/str/dict/list）
        Raises:
            ValueError: 类型不匹配 / 超出 min-max 范围
        """
        registry = B14_CONFIG_REGISTRY.get(config_key)
        if registry is None:
            raise ValueError(f"配置 key '{config_key}' 不在注册表白名单内")

        cfg_type = registry["type"]
        min_val = registry.get("min")
        max_val = registry.get("max")

        if cfg_type == "int":
            try:
                parsed = int(config_value)
            except (ValueError, TypeError):
                raise ValueError(f"配置值 '{config_value}' 不是有效整数")
            if min_val is not None and parsed < min_val:
                raise ValueError(f"配置值 {parsed} 小于最小值 {min_val}")
            if max_val is not None and parsed > max_val:
                raise ValueError(f"配置值 {parsed} 大于最大值 {max_val}")
            return parsed

        if cfg_type == "bool":
            if config_value.lower() not in (
                "true",
                "false",
                "1",
                "0",
                "yes",
                "no",
                "on",
                "off",
            ):
                raise ValueError(
                    f"配置值 '{config_value}' 不是有效布尔值（true/false）"
                )
            return config_value.lower() in ("true", "1", "yes", "on")

        if cfg_type == "decimal":
            try:
                parsed = Decimal(config_value)
            except (InvalidOperation, ValueError):
                raise ValueError(f"配置值 '{config_value}' 不是有效金额")
            if min_val is not None and parsed < Decimal(str(min_val)):
                raise ValueError(f"配置值 {parsed} 小于最小值 {min_val}")
            if max_val is not None and parsed > Decimal(str(max_val)):
                raise ValueError(f"配置值 {parsed} 大于最大值 {max_val}")
            return parsed

        if cfg_type == "json":
            try:
                return json.loads(config_value)
            except (json.JSONDecodeError, TypeError):
                raise ValueError(f"配置值 '{config_value}' 不是有效 JSON")

        # str 类型直接放行
        return config_value

    @staticmethod
    def _serialize_config(config: SystemConfig) -> Dict[str, Any]:
        """序列化 SystemConfig 实例为字典"""
        def _fmt(dt: Any) -> Optional[str]:
            return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None
        return {
            "id": config.id,
            "config_key": config.config_key,
            "config_value": config.config_value,
            "config_name": config.config_name,
            "remark": config.remark,
            "create_time": _fmt(config.create_time),
            "update_time": _fmt(config.update_time),
        }
