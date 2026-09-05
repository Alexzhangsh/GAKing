-- @ai-generated
-- =====================================================================
-- 清理 gak_dev 库 user_id=10001 测试用户的提现测试数据
-- 用途：提现功能联调产生的脏数据（账户充值 1000 + 3 条提现申请），
--       执行后恢复干净环境，便于后续回归测试。
-- 执行环境：dev 库 gak_dev（请勿在生产执行）
-- 注意：执行前请再次确认 user_id=10001 确为测试用户！
-- =====================================================================

-- 1. 物理删除测试提现申请（id=1 SUCCESS / id=2 REJECTED / id=3 PENDING）
DELETE FROM user_withdraw_apply WHERE user_id = 10001;

-- 2. 物理删除测试佣金账户（充值 1000 元的脏账户）
DELETE FROM user_commission_account WHERE user_id = 10001;

-- 3. 失效该用户账户 Redis 缓存（避免读穿缓存回填已删除的脏数据）
--    Redis CLI 执行：
--    DEL gaking:prod:user_account:10001
--    DEL gaking:prod:config:withdraw   -- 可选：同时清理提现配置缓存

-- =====================================================================
-- 备选：如需保留审计痕迹改用软删除（is_delete=1），但回归测试会因
--       get_or_create 命中 is_delete=False 而新建账户，故推荐上方物理删除。
-- =====================================================================
-- UPDATE user_withdraw_apply     SET is_delete = 1, update_time = NOW() WHERE user_id = 10001;
-- UPDATE user_commission_account SET is_delete = 1, update_time = NOW() WHERE user_id = 10001;
