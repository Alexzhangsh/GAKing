CREATE TABLE IF NOT EXISTS `gaking_system_config` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `config_key` varchar(64) NOT NULL COMMENT '配置唯一键名',
  `config_value` varchar(2000) DEFAULT '' COMMENT '配置值，支持文本、数字、JSON',
  `config_name` varchar(128) NOT NULL COMMENT '配置中文名称',
  `config_desc` varchar(512) DEFAULT '' COMMENT '配置说明备注',
  `sort_num` int(11) NOT NULL DEFAULT 0 COMMENT '排序权重',
  `is_delete` tinyint(1) NOT NULL DEFAULT 0 COMMENT '软删除：0-未删除 1-已删除',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_config_key` (`config_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统全局配置表';

CREATE TABLE IF NOT EXISTS `gaking_pay_config` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `pay_type` tinyint(1) NOT NULL DEFAULT 1 COMMENT '支付类型：1-微信支付',
  `mch_id` varchar(64) NOT NULL DEFAULT '' COMMENT '微信商户号',
  `api_key` varchar(128) NOT NULL DEFAULT '' COMMENT '微信支付API密钥',
  `cert_path` varchar(256) DEFAULT '' COMMENT '支付证书路径',
  `notify_url` varchar(256) NOT NULL DEFAULT '' COMMENT '支付回调地址',
  `withdraw_rate` decimal(10,2) NOT NULL DEFAULT 0.00 COMMENT '提现手续费比例',
  `withdraw_min` decimal(10,2) NOT NULL DEFAULT 0.00 COMMENT '最低提现金额',
  `withdraw_fixed_fee` decimal(10,2) NOT NULL DEFAULT 0.00 COMMENT '固定提现手续费',
  `status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '状态：0-禁用 1-启用',
  `remark` varchar(512) DEFAULT '' COMMENT '备注说明',
  `is_delete` tinyint(1) NOT NULL DEFAULT 0 COMMENT '软删除：0-未删除 1-已删除',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_pay_type` (`pay_type`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付渠道配置表';

CREATE TABLE IF NOT EXISTS `gaking_cloud_config` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `config_name` varchar(128) NOT NULL DEFAULT '' COMMENT '配置名称',
  `cdn_domain` varchar(256) DEFAULT '' COMMENT 'CDN根域名',
  `obs_bucket` varchar(128) DEFAULT '' COMMENT '华为OBS桶名',
  `obs_endpoint` varchar(256) DEFAULT '' COMMENT 'OBS终端地址',
  `access_key` varchar(256) DEFAULT '' COMMENT '云存储AK密钥',
  `secret_key` varchar(256) DEFAULT '' COMMENT '云存储SK密钥',
  `status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '状态：0-禁用 1-启用',
  `remark` varchar(512) DEFAULT '' COMMENT '备注说明',
  `is_delete` tinyint(1) NOT NULL DEFAULT 0 COMMENT '软删除：0-未删除 1-已删除',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='云资源CDN配置表';

CREATE TABLE IF NOT EXISTS `gaking_channel_mapping` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `channel_code` varchar(32) NOT NULL DEFAULT '' COMMENT '渠道标识：myq/dta/orderx',
  `third_field` varchar(64) NOT NULL DEFAULT '' COMMENT '第三方字段名',
  `system_field` varchar(64) NOT NULL DEFAULT '' COMMENT '系统标准字段名',
  `field_desc` varchar(128) DEFAULT '' COMMENT '字段用途说明',
  `status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '状态：0-失效 1-生效',
  `sort_num` int(11) NOT NULL DEFAULT 0 COMMENT '排序权重',
  `remark` varchar(512) DEFAULT '' COMMENT '规则备注',
  `is_delete` tinyint(1) NOT NULL DEFAULT 0 COMMENT '软删除：0-未删除 1-已删除',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_channel_code` (`channel_code`),
  KEY `idx_status` (`status`),
  UNIQUE KEY `uk_channel_field` (`channel_code`,`third_field`,`system_field`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='渠道字段映射配置表';

CREATE TABLE IF NOT EXISTS `admin_role` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `role_name` varchar(64) NOT NULL COMMENT '角色名称',
  `role_desc` varchar(512) DEFAULT '' COMMENT '角色描述',
  `permissions` text DEFAULT '' COMMENT '权限列表JSON',
  `status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '状态：0-禁用 1-启用',
  `is_delete` tinyint(1) NOT NULL DEFAULT 0 COMMENT '软删除：0-未删除 1-已删除',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_role_name` (`role_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='后台角色表';

CREATE TABLE IF NOT EXISTS `admin_user` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `username` varchar(64) NOT NULL COMMENT '用户名',
  `password` varchar(256) NOT NULL COMMENT '密码（bcrypt加密）',
  `real_name` varchar(64) DEFAULT '' COMMENT '真实姓名',
  `phone` varchar(32) DEFAULT '' COMMENT '手机号',
  `email` varchar(128) DEFAULT '' COMMENT '邮箱',
  `role_id` bigint(20) NOT NULL COMMENT '角色ID',
  `status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '状态：0-禁用 1-启用',
  `is_delete` tinyint(1) NOT NULL DEFAULT 0 COMMENT '软删除：0-未删除 1-已删除',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  KEY `idx_role_id` (`role_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_admin_user_role` FOREIGN KEY (`role_id`) REFERENCES `admin_role` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='后台管理员表';

CREATE TABLE IF NOT EXISTS `audit_logs` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `user_id` bigint(20) NOT NULL COMMENT '操作人ID',
  `user_name` varchar(64) DEFAULT '' COMMENT '操作人姓名',
  `action` varchar(128) NOT NULL COMMENT '操作描述',
  `target_type` varchar(64) DEFAULT '' COMMENT '目标类型',
  `target_id` bigint(20) DEFAULT 0 COMMENT '目标ID',
  `details` text DEFAULT '' COMMENT '脱敏操作内容',
  `ip_address` varchar(64) DEFAULT '' COMMENT 'IP地址',
  `user_agent` varchar(512) DEFAULT '' COMMENT 'User Agent',
  `is_delete` tinyint(1) NOT NULL DEFAULT 0 COMMENT '软删除：0-未删除 1-已删除',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_action` (`action`),
  KEY `idx_target_type` (`target_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审计日志表';

CREATE TABLE IF NOT EXISTS `gaking_task_status` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `task_name` varchar(128) NOT NULL COMMENT '任务名称',
  `status` varchar(32) NOT NULL COMMENT '执行状态：running/success/failed/skipped',
  `message` varchar(512) DEFAULT '' COMMENT '执行结果消息',
  `retry_count` int(11) NOT NULL DEFAULT 0 COMMENT '重试次数',
  `error_stack` text DEFAULT '' COMMENT '异常堆栈信息',
  `is_delete` tinyint(1) NOT NULL DEFAULT 0 COMMENT '软删除：0-未删除 1-已删除',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_task_name` (`task_name`),
  KEY `idx_status` (`status`),
  KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定时任务执行状态表';