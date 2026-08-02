#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王CPS返利小程序 - 数据库一键初始化脚本
# 使用说明：直接运行此脚本即可完成数据库初始化
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置信息 - 使用远程开发数据库
DB_HOST="121.37.173.132"
DB_PORT="3306"
DB_USER="gaking-dev"
DB_PASS="GAKing_dev"
DB_NAME="gak_dev"
SCHEMA_FILE="./src/db/schema.sql"

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}金角大王CPS返利小程序 - 数据库一键初始化${NC}"
echo -e "${BLUE}==============================================${NC}"
echo ""

# ================ 步骤1：检查MySQL连接 ================
echo -e "${YELLOW}步骤1/4：检查MySQL连接...${NC}"
if mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASS" -e "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ MySQL连接成功${NC}"
else
    echo -e "${RED}✗ MySQL连接失败，请检查：${NC}"
    echo -e "${RED}  1. MySQL服务是否已启动${NC}"
    echo -e "${RED}  2. 用户名密码是否正确（当前：root/123456）${NC}"
    echo -e "${RED}  3. 端口是否正确（当前：3306）${NC}"
    exit 1
fi

# ================ 步骤2：创建数据库 ================
echo -e ""
echo -e "${YELLOW}步骤2/4：创建数据库 ${DB_NAME}...${NC}"
if mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASS" -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"; then
    echo -e "${GREEN}✓ 数据库创建成功${NC}"
else
    echo -e "${RED}✗ 数据库创建失败${NC}"
    exit 1
fi

# ================ 步骤3：执行建表SQL ================
echo -e ""
echo -e "${YELLOW}步骤3/4：执行建表SQL...${NC}"
if [ -f "$SCHEMA_FILE" ]; then
    if mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" < "$SCHEMA_FILE"; then
        echo -e "${GREEN}✓ 建表SQL执行成功（共8张表）${NC}"
    else
        echo -e "${RED}✗ 建表SQL执行失败${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ 建表文件不存在：$SCHEMA_FILE${NC}"
    exit 1
fi

# ================ 步骤4：执行Alembic迁移 ================
echo -e ""
echo -e "${YELLOW}步骤4/4：执行Alembic迁移...${NC}"
if command -v alembic &> /dev/null; then
    if alembic revision --autogenerate -m "init tables" 2>&1 | grep -q "No changes"; then
        echo -e "${GREEN}✓ 数据库已最新，无需迁移${NC}"
    else
        if alembic upgrade head; then
            echo -e "${GREEN}✓ Alembic迁移执行成功${NC}"
        else
            echo -e "${RED}✗ Alembic迁移执行失败${NC}"
            exit 1
        fi
    fi
else
    echo -e "${YELLOW}⚠️ Alembic命令未找到，跳过迁移步骤${NC}"
    echo -e "${YELLOW}   请手动执行：pip install alembic && alembic upgrade head${NC}"
fi

# ================ 完成 ================
echo -e ""
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}数据库初始化完成！${NC}"
echo -e "${GREEN}==============================================${NC}"
echo -e ""
echo -e "${BLUE}数据库信息：${NC}"
echo -e "${BLUE}  主机：${DB_HOST}:${DB_PORT}${NC}"
echo -e "${BLUE}  数据库：${DB_NAME}${NC}"
echo -e "${BLUE}  用户：${DB_USER}${NC}"
echo -e ""
echo -e "${YELLOW}下一步：执行 start_all.sh 启动所有服务${NC}"