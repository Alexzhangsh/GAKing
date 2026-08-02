-- @ai-generated
-- =====================================================================
-- 用户提现申请表 —— 建表 DDL
-- =====================================================================
-- 表名：user_withdraw_apply
-- 业务说明：平台用户提现申请全生命周期记录，5 态状态机
--   PENDING(待审核) → APPROVED(审核通过) → PROCESSING(转账处理中) → SUCCESS(打款完成)
--   任一审核中/通过状态可 → REJECTED(驳回/打款失败，退回余额)
-- 设计约定：
--   1. 字段命名与既有表对齐：id / is_delete / create_time / update_time。
--   2. 金额字段使用 DECIMAL(10,2) 存元。
--   3. 字符集 utf8mb4 / utf8mb4_unicode_ci。
--   4. apply_no 唯一索引：提现单号全局唯一（GAKW前缀+时间+随机）。
--   5. 联合索引 idx_user_status 支持用户+状态高频联查。
--
-- 状态：已确认。对应 ORM 模型 src/models/business/user_withdraw_apply_model.py，
--       Alembic 迁移 0002_add_user_commission_and_withdraw.py。
-- =====================================================================

CREATE TABLE `user_withdraw_apply` (
    `id`                  BIGINT        NOT NULL AUTO_INCREMENT       COMMENT '主键ID',
    `apply_no`            VARCHAR(64)   NOT NULL                       COMMENT '提现单号（GAKW前缀+时间+随机，全局唯一）',
    `user_id`             BIGINT        NOT NULL                       COMMENT '平台用户ID',
    `apply_amount`        DECIMAL(10,2) NOT NULL                       COMMENT '申请提现金额(元)',
    `fee`                 DECIMAL(10,2) NOT NULL DEFAULT 0.00          COMMENT '手续费(元)',
    `actual_amount`       DECIMAL(10,2) NOT NULL DEFAULT 0.00          COMMENT '实际到账金额(元)=apply_amount-fee',
    `status`              VARCHAR(32)   NOT NULL DEFAULT 'PENDING'     COMMENT '状态：PENDING/APPROVED/PROCESSING/SUCCESS/REJECTED',
    `review_user_id`      BIGINT                                       COMMENT '审核人ID（后台管理员）',
    `review_remark`       VARCHAR(512)  NOT NULL DEFAULT ''            COMMENT '审核备注',
    `review_time`         DATETIME                                     COMMENT '审核时间',
    `transfer_batch_id`   VARCHAR(64)   NOT NULL DEFAULT ''            COMMENT '微信转账批次ID',
    `transfer_time`       DATETIME                                     COMMENT '打款完成时间',
    `reject_reason`       VARCHAR(512)  NOT NULL DEFAULT ''            COMMENT '驳回原因（含打款失败原因）',
    `remark`              VARCHAR(512)  NOT NULL DEFAULT ''            COMMENT '备注',
    `is_delete`           TINYINT(1)    NOT NULL DEFAULT 0             COMMENT '软删除：0-未删除 1-已删除',
    `create_time`         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP                              COMMENT '创建时间',
    `update_time`         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_apply_no` (`apply_no`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_status` (`status`),
    KEY `idx_create_time` (`create_time`),
    KEY `idx_user_status` (`user_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户提现申请表';
