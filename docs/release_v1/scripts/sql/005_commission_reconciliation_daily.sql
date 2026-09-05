-- @ai-generated
-- =====================================================================
-- 每日佣金对账快照表 —— 建表结构（待确认，确认后再落地 + 建模型 + 接入任务2）
-- =====================================================================
-- 背景：
--   任务2「每日佣金对账统计」当前实现为「只读聚合 + 日志输出 + 缓存失效」，
--   不依赖任何对账表即可运行。若需保留每日对账快照以便历史审计 / 申诉回溯 /
--   运营报表，则建议落地本表（每日 00:10 任务执行后写入一行快照）。
--
-- 设计说明：
--   1. 采用「单表 + JSON 明细」方案：每日一行汇总，按推广员明细存 details_json，
--      满足审计存档需求且结构简单；如需按推广员维度高频检索历史，可改用
--      「header + detail」两张表的归一化方案（见文末备选）。
--   2. 字段命名与既有表对齐：id / is_delete / create_time / update_time
--      （源自 src/db/base.py 的 Base 基类约定）。
--   3. 金额字段使用 DECIMAL(10,2) 存元（与 orders / commission_flow 一致）。
--   4. 字符集 utf8mb4 / utf8mb4_unicode_ci（项目统一）。
--   5. reconcile_date 唯一索引：每日仅一条快照，任务重复执行以最新结果覆盖。
--
-- 状态：待用户确认。确认后我会：
--   - 在 src/models/business/ 新增 CommissionReconciliationDaily 模型；
--   - 新增 reconciliation_dao.py（继承 BaseDAO）；
--   - 在 scheduler_jobs.daily_commission_reconciliation 末尾追加快照写入（upsert）。
-- =====================================================================

CREATE TABLE `commission_reconciliation_daily` (
    `id`              BIGINT        NOT NULL AUTO_INCREMENT       COMMENT '主键ID',
    `reconcile_date`  DATE          NOT NULL                       COMMENT '对账日期（统计目标日，前一日）',
    `promoter_count`  INT           NOT NULL DEFAULT 0             COMMENT '涉及推广员数量',
    `total_amount`    DECIMAL(10,2) NOT NULL DEFAULT 0.00          COMMENT '已结算佣金总额(元)',
    `total_orders`    INT           NOT NULL DEFAULT 0             COMMENT '涉及订单数（去重 order_id）',
    `status`          VARCHAR(32)   NOT NULL DEFAULT 'success'     COMMENT '对账状态：success/failed',
    `details_json`    TEXT                                       COMMENT '按推广员明细JSON：[{"user_id":..,"total_amount":"..","order_count":..}]',
    `remark`          VARCHAR(512)  NOT NULL DEFAULT ''            COMMENT '备注（失败原因等）',
    `is_delete`       TINYINT(1)    NOT NULL DEFAULT 0             COMMENT '软删除：0-未删除 1-已删除',
    `create_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP                              COMMENT '创建时间',
    `update_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_reconcile_date` (`reconcile_date`),
    KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日佣金对账快照表';

-- =====================================================================
-- 备选方案：归一化（header + detail），适用于需按推广员维度检索历史对账
-- =====================================================================
-- CREATE TABLE `commission_reconciliation_detail` (
--     `id`              BIGINT        NOT NULL AUTO_INCREMENT,
--     `reconcile_date`  DATE          NOT NULL                   COMMENT '对账日期',
--     `user_id`         BIGINT        NOT NULL                   COMMENT '推广员用户ID',
--     `total_amount`    DECIMAL(10,2) NOT NULL DEFAULT 0.00      COMMENT '该推广员已结算佣金总额(元)',
--     `order_count`     INT           NOT NULL DEFAULT 0         COMMENT '该推广员涉及订单数',
--     `is_delete`       TINYINT(1)    NOT NULL DEFAULT 0,
--     `create_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
--     `update_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
--     PRIMARY KEY (`id`),
--     UNIQUE KEY `uk_date_user` (`reconcile_date`, `user_id`),
--     KEY `idx_user_id` (`user_id`),
--     KEY `idx_create_time` (`create_time`)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日佣金对账推广员明细表';
