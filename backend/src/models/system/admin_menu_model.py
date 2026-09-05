# @ai-generated
"""
后台菜单元数据表 ORM 模型（B14 新建，不修改 B01-B13 基线）
表名：admin_menu
业务说明：后台管理菜单树元数据，菜单-角色绑定通过 AdminRole.permissions JSON 数组
         存放 menu_code 实现（无需独立关联表），与 RbacUtil.has_permission 完全兼容
字段说明：
  - menu_code：菜单唯一编码，同时作为权限码（如 menu:order / menu:withdraw）
  - menu_type：directory(目录) / menu(菜单) / button(按钮)
  - parent_id：父菜单ID，0 表示顶级
统一基础字段：id / create_time / update_time / is_delete（由 Base 基类提供）
"""
from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, String, UniqueConstraint

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class AdminMenu(Base, SerializableMixin, SoftDeleteMixin):
    """后台菜单元数据表"""

    __tablename__ = "admin_menu"
    __table_args__ = (
        UniqueConstraint("menu_code", name="uk_menu_code"),
        Index("idx_parent_id", "parent_id"),
        Index("idx_status", "status"),
        Index("idx_menu_type", "menu_type"),
        {
            "comment": "后台菜单元数据表（B14）",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 父菜单ID，0 表示顶级菜单
    parent_id = Column(BigInteger, default=0, nullable=False, comment="父菜单ID，0表示顶级")
    # 菜单名称
    menu_name = Column(String(128), nullable=False, comment="菜单名称")
    # 菜单唯一编码（同时作为权限码，存入 AdminRole.permissions 实现菜单-角色绑定）
    menu_code = Column(String(64), nullable=False, comment="菜单唯一编码（权限码）")
    # 前端路由路径
    menu_path = Column(String(256), default="", nullable=False, comment="前端路由路径")
    # 菜单图标
    menu_icon = Column(String(64), default="", nullable=False, comment="菜单图标")
    # 菜单类型：directory-目录 / menu-菜单 / button-按钮
    menu_type = Column(String(16), default="menu", nullable=False, comment="菜单类型：directory/menu/button")
    # 排序权重
    sort_num = Column(Integer, default=0, nullable=False, comment="排序权重")
    # 状态：True-启用 False-禁用
    status = Column(Boolean, default=True, nullable=False, comment="状态：True-启用 False-禁用")
    # 备注
    remark = Column(String(512), default="", nullable=False, comment="备注说明")
