-- @ai-generated
-- ============================================================
-- E01 回滚遗留数据清理：scheduled_task_run_log 表
-- 清理目标：删除成长体系（E01-1）运行的全部历史日志
-- 清理条件：task_name 以 growth_ 前缀开头
-- 影响行数：约 5 行（growth_expire_reset 2 行 + daily_growth_grant 3 行）
-- 验证方式：清理前/后分别 SELECT COUNT(*)
-- ============================================================

-- 第一步：清理前确认（安全兜底）
SELECT '=== 清理前 ===' AS step;
SELECT task_name, COUNT(*) AS cnt
FROM scheduled_task_run_log
WHERE task_name IN ('growth_expire_reset', 'daily_growth_grant')
GROUP BY task_name;

-- 第二步：执行清理
DELETE FROM scheduled_task_run_log
WHERE task_name IN ('growth_expire_reset', 'daily_growth_grant');

-- 第三步：清理后确认
SELECT '=== 清理后 ===' AS step;
SELECT task_name, COUNT(*) AS cnt
FROM scheduled_task_run_log
WHERE task_name IN ('growth_expire_reset', 'daily_growth_grant')
GROUP BY task_name;

-- 第四步：确认其他任务日志不受影响
SELECT '=== 其他任务日志不受影响 ===' AS step;
SELECT task_name, COUNT(*) AS cnt
FROM scheduled_task_run_log
WHERE task_name NOT IN ('growth_expire_reset', 'daily_growth_grant')
GROUP BY task_name
ORDER BY task_name;