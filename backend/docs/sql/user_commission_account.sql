-- @ai-generated
-- =====================================================================
-- 用户佣金账户表 —— 建表 DDL
-- =====================================================================
-- 表名：user_commission_account
-- 业务说明：平台用户佣金资产聚合账户，记录可用/冻结/累计佣金/累计提现/累计手续费
-- 设计约定：
--   1. 字段命名与既有表对齐：id / is_delete / create_time / update_time
--      （源自 src/db/base.py 的 Base 基类约定）。
--   2. 金额字段使用 DECIMAL(10,2) 存元（与 orders / commission_flow 一致）。
--   3. 字符集 utf8mb4 / utf8mb4_unicode_ci（项目统一）。
--   4. user_id 唯一索引：每用户仅一个账户。
--   5. last_settle_date：对账任务幂等防重复入账（同日重跑跳过）。
--
-- 状态：已确认。对应 ORM 模型 src/models/business/user_commission_account_model.py，
--       Alembic 迁移 0002_add_user_commission_and_withdraw.py。
-- =====================================================================

CREATE TABLE `user_commission_account` (
    `id`                   BIGINT        NOT NULL AUTO_INCREMENT       COMMENT '主键ID',
    `user_id`              BIGINT        NOT NULL                       COMMENT '平台用户ID',
    `total_balance`        DECIMAL(10,2) NOT NULL DEFAULT 0.00          COMMENT '累计已结算佣金(元)',
    `available_balance`    DECIMAL(10,2) NOT NULL DEFAULT 0.00          COMMENT '可用余额(元)，可提现',
    `frozen_balance`       DECIMAL(10,2) NOT NULL DEFAULT 0.00          COMMENT '冻结余额(元)，待审核提现锁定',
    `cumulative_withdrawn` DECIMAL(10,2) NOT NULL DEFAULT 0.00          COMMENT '累计成功提现金额(元，实际到账)',
    `cumulative_fee`       DECIMAL(10,2) NOT NULL DEFAULT 0.00          COMMENT '累计手续费(元)',
    `last_settle_date`     DATE                                       COMMENT '最近一次对账入账日期（幂等防重复入账）',
    `version`              INT           NOT NULL DEFAULT 0             COMMENT '乐观锁版本号（余额变更递增）',
    `is_delete`            TINYINT(1)    NOT NULL DEFAULT 0             COMMENT '软删除：0-未删除 1-已删除',
    `create_time`          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP                              COMMENT '创建时间',
    `update_time`          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_id` (`user_id`),
    KEY `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户佣金账户表';
