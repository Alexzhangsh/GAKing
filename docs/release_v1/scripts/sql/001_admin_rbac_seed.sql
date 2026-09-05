-- @ai-generated
-- =====================================================================
-- 后台 RBAC 种子数据：超级管理员角色 + 默认管理员账号
-- 用途：提现审核接口 require_any_permission(["withdraw:review"]) 的权限验证基础
--       （admin_role / admin_user 表初始为空，需先种子化才能放行后台审核）
-- 执行环境：dev 库 gak_dev
-- 账号：admin / admin123（仅供开发联调，生产环境请另行创建并改密）
-- 可重入：ON DUPLICATE KEY UPDATE 刷新 permissions / password
-- =====================================================================

-- 1. 超级管理员角色（permissions 含通配符 "*"，RbacUtil 命中 "*" 直接放行所有权限校验）
INSERT INTO admin_role (role_name, role_desc, permissions, status, is_delete, create_time, update_time)
VALUES (
    'superadmin',
    '超级管理员（通配权限，仅开发联调）',
    '["*"]',
    1, 0, NOW(), NOW()
)
ON DUPLICATE KEY UPDATE
    permissions = VALUES(permissions),
    status = 1,
    is_delete = 0,
    update_time = NOW();

-- 2. 默认管理员账号（id=999，与测试 JWT user_id=999 对齐；password = bcrypt('admin123')）
INSERT INTO admin_user (id, username, password, real_name, role_id, status, is_delete, create_time, update_time)
VALUES (
    999,
    'admin',
    '$2b$10$ndT9UUSMtbPv7DO1P2t2euc0fX7ScHSWWDBzWUM7Rid4PzpUldiG6',
    '超级管理员',
    (SELECT id FROM admin_role WHERE role_name = 'superadmin' AND is_delete = 0 LIMIT 1),
    1, 0, NOW(), NOW()
)
ON DUPLICATE KEY UPDATE
    password = VALUES(password),
    role_id = VALUES(role_id),
    status = 1,
    is_delete = 0,
    update_time = NOW();
