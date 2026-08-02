#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王CPS返利小程序 - 环境配置模板生成脚本
# 使用说明：运行此脚本生成完整的.env.development填空模板
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

OUTPUT_FILE="../.env.development"

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}金角大王CPS返利小程序 - 环境配置模板生成${NC}"
echo -e "${BLUE}==============================================${NC}"
echo ""

cat > "$OUTPUT_FILE" << 'EOF'
# ============================================
# 金角大王CPS返利小程序 - 开发环境配置文件
# 请按说明填写各项参数，填写前请仔细阅读注释
# ============================================

# ========== 基础配置 ==========
# 环境标识：development / test / production
ENVIRONMENT=development

# 服务端口（默认3001，如被占用可修改）
PORT=3001

# ========== MySQL数据库配置 ==========
# 获取来源：MySQL安装时设置的用户名和密码
# 默认端口：3306
DB_HOST=localhost
DB_PORT=3306
DB_USERNAME=root
DB_PASSWORD=123456
DB_DATABASE=gaking_dev
TIMEZONE=+08:00

# ========== Redis缓存配置 ==========
# 获取来源：Redis安装时设置（默认无密码）
# 默认端口：6379
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# ========== JWT鉴权配置 ==========
# 获取来源：自行生成随机字符串
# 开发环境要求：至少32位字符
# 生产环境要求：至少64位字符
JWT_SECRET=dev_jwt_secret_key_for_gaking_cps_mini_program_2026
JWT_EXPIRES_IN=86400

# ========== 跨域配置 ==========
# 开发环境可使用 * 允许所有来源
# 生产环境必须指定具体域名，多个用逗号分隔
CORS_ORIGINS=*

# ========== 本地文件存储配置 ==========
# 文件上传保存目录，无需修改
LOCAL_UPLOAD_BASE_DIR=./static/uploads
LOCAL_STATIC_PREFIX=/static/uploads
UPLOAD_TEMP_DIR=./tmp

# ========== OBS对象存储配置（可选） ==========
# 获取来源：华为云OBS控制台创建Access Key
# 开发环境可使用测试AK或留空（系统自动降级为本地存储）
CDN_IMG_BASE_URL=http://localhost:3001/static/uploads
OBS_PROJECT_PREFIX=prod
OBS_ACCESS_KEY_ID=dev_obs_access_key
OBS_SECRET_ACCESS_KEY=dev_obs_secret_key
OBS_ENDPOINT=https://obs.cn-east-3.myhuaweicloud.com
OBS_BUCKET_NAME=gaking-dev

# ========== 第三方CPS渠道密钥（可选） ==========
# 获取来源：各CPS渠道平台申请
# 开发环境可留空，渠道对接时填写
MIAO_QUAN_TOKEN=dev_miao_quan_token
DATAOK_APPID=dev_dataok_appid
DATAOK_APPKEY=dev_dataok_appkey
ORDERX_TOKEN=dev_orderx_token

# ========== 风控业务参数 ==========
# RISK_HOLD_RATIO: 风控扣留比例（开发环境建议0.15）
# SETTLE_COOL_DAY: 结算冷却天数（开发环境建议7）
# SETTLE_DELAY_DAY: 结算延迟天数（开发环境建议3）
RISK_HOLD_RATIO=0.15
SETTLE_COOL_DAY=7
SETTLE_DELAY_DAY=3

# ========== 接口限流配置 ==========
# RATE_LIMIT_NORMAL: 普通接口每秒请求数限制
# RATE_LIMIT_SEARCH: 搜索接口每秒请求数限制
# RATE_LIMIT_TRANSFORM: 转换接口每秒请求数限制
# RATE_LIMIT_PAY: 支付接口每秒请求数限制
RATE_LIMIT_NORMAL=60
RATE_LIMIT_SEARCH=20
RATE_LIMIT_TRANSFORM=100
RATE_LIMIT_PAY=10
DATAOK_SEARCH_LIMIT=100
DATAOK_TRANSFORM_LIMIT=300

# ========== 定时任务配置 ==========
# SCHEDULER_ENABLE: 是否启用定时任务（true/false）
# CRON表达式格式：分 时 日 月 周
SCHEDULER_ENABLE=true
SHARD_TOTAL=1
SHARD_INDEX=0

# 系统配置缓存刷新（默认每小时）
SCHEDULER_CRON_SYNC_CONFIG=0 * * * *

# 订单状态同步（默认每5分钟）
SCHEDULER_CRON_SYNC_ORDER_STATUS=*/5 * * * *

# 过期数据清理（默认每天凌晨3点）
SCHEDULER_CRON_CLEAN_EXPIRED_DATA=0 3 * * *

# 渠道映射更新（默认每天凌晨2点）
SCHEDULER_CRON_UPDATE_CHANNEL_MAPPING=0 2 * * *

# 失败重试最大次数
SCHEDULER_RETRY_MAX=3
EOF

echo -e "${GREEN}✓ 环境配置模板已生成：$OUTPUT_FILE${NC}"
echo ""
echo -e "${YELLOW}填写说明：${NC}"
echo -e "${YELLOW}1. 数据库配置（必须填写）${NC}"
echo -e "${YELLOW}   - DB_USERNAME/DB_PASSWORD：你的MySQL用户名密码${NC}"
echo -e "${YELLOW}2. JWT_SECRET（必须填写）${NC}"
echo -e "${YELLOW}   - 开发环境至少32位字符${NC}"
echo -e "${YELLOW}3. OBS配置（可选）${NC}"
echo -e "${YELLOW}   - 开发环境可使用默认测试值，不影响运行${NC}"
echo -e "${YELLOW}4. CPS渠道密钥（可选）${NC}"
echo -e "${YELLOW}   - 开发环境可留空，渠道对接时填写${NC}"
echo ""
echo -e "${BLUE}填写完成后运行：../start_dev.sh 启动后端服务${NC}"