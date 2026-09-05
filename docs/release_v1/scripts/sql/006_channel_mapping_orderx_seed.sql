-- @ai-generated
-- =====================================================================
-- B16-1 订单侠渠道配置种子数据
-- 用途：为 gaking_channel_mapping 表预置订单侠(orderx)渠道配置项，
--       使后台「渠道配置」页面可直接看到并编辑订单侠渠道
-- 执行环境：dev 库 gak_dev / prod 库（按实际库名替换）
-- 可重入：ON DUPLICATE KEY UPDATE 幂等，可重复执行
-- 说明：
--   1. api_token / api_secret 为占位空值，需在后台配置页或通过
--      POST /api/v1/admin/channel 接口填入真实订单侠 API Key；
--   2. 表结构以 src/models/system/channel_config.py 的 ChannelMapping
--      模型为准（channel_code/channel_name/api_token/api_secret/pid/
--      settle_rate/status/remark/is_delete/create_time/update_time）；
--   3. settle_rate 为结算比例(0~1)，订单侠默认 0.80（渠道结算 80%）。
-- =====================================================================

-- 1. 订单侠渠道配置（不存在则插入，存在则刷新名称/结算比例/启用状态）
INSERT INTO gaking_channel_mapping
    (channel_code, channel_name, api_token, api_secret, pid, settle_rate, status, remark, is_delete, create_time, update_time)
VALUES
    ('orderx', '订单侠', '', '', '', 0.8000, 1, '订单侠淘宝CPS渠道（B16-1对接）', 0, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    channel_name = VALUES(channel_name),
    settle_rate = VALUES(settle_rate),
    status = VALUES(status),
    is_delete = 0,
    update_time = NOW();

-- 2. 参照：喵有券渠道配置（若未初始化可一并执行）
INSERT INTO gaking_channel_mapping
    (channel_code, channel_name, api_token, api_secret, pid, settle_rate, status, remark, is_delete, create_time, update_time)
VALUES
    ('myq', '喵有券', '', '', '', 0.8500, 1, '喵有券淘宝CPS渠道', 0, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    channel_name = VALUES(channel_name),
    settle_rate = VALUES(settle_rate),
    status = VALUES(status),
    is_delete = 0,
    update_time = NOW();
