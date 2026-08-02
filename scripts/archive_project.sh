#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王CPS返利小程序 - 版本归档打包脚本
# 使用说明：直接运行此脚本打包全部文档+代码
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)/..
DOCS_DIR="/Users/alexzhang/Documents/Work/Projects/Products/金角大王/Documents"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
VERSION="v1.0.0"
ARCHIVE_NAME="GAKing-Coding-${VERSION}-${TIMESTAMP}"
ARCHIVE_DIR="/tmp/${ARCHIVE_NAME}"

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}金角大王CPS返利小程序 - 版本归档打包${NC}"
echo -e "${BLUE}==============================================${NC}"
echo ""

# ================ 步骤1：创建归档目录结构 ================
echo -e "${YELLOW}步骤1/5：创建归档目录结构...${NC}"
mkdir -p "${ARCHIVE_DIR}/设计文档归档"
mkdir -p "${ARCHIVE_DIR}/完整工程代码"
mkdir -p "${ARCHIVE_DIR}/测试脚本"
echo -e "${GREEN}✓ 归档目录结构创建完成${NC}"

# ================ 步骤2：复制设计文档 ================
echo -e ""
echo -e "${YELLOW}步骤2/5：复制设计文档...${NC}"
if [ -d "${DOCS_DIR}" ]; then
    cp -r "${DOCS_DIR}"/* "${ARCHIVE_DIR}/设计文档归档/" 2>/dev/null || true
    echo -e "${GREEN}✓ 设计文档复制完成${NC}"
else
    echo -e "${YELLOW}⚠️ 设计文档目录不存在，跳过${NC}"
fi

# ================ 步骤3：复制工程代码 ================
echo -e ""
echo -e "${YELLOW}步骤3/5：复制工程代码...${NC}"

echo -e "  复制后端代码..."
cp -r "${PROJECT_DIR}/backend" "${ARCHIVE_DIR}/完整工程代码/"
echo -e "${GREEN}✓ 后端代码复制完成${NC}"

echo -e "  复制Admin后台代码..."
cp -r "${PROJECT_DIR}/admin" "${ARCHIVE_DIR}/完整工程代码/"
echo -e "${GREEN}✓ Admin后台代码复制完成${NC}"

echo -e "  复制小程序代码..."
cp -r "${PROJECT_DIR}/miniprogram" "${ARCHIVE_DIR}/完整工程代码/"
echo -e "${GREEN}✓ 小程序代码复制完成${NC}"

echo -e "  复制交付文档..."
cp "${PROJECT_DIR}/GAKing-一期基建交付文档.md" "${ARCHIVE_DIR}/设计文档归档/"
echo -e "${GREEN}✓ 交付文档复制完成${NC}"

# ================ 步骤4：复制测试脚本 ================
echo -e ""
echo -e "${YELLOW}步骤4/5：复制测试脚本...${NC}"

echo -e "  复制数据库初始化脚本..."
cp "${PROJECT_DIR}/backend/scripts/init_db_auto.sh" "${ARCHIVE_DIR}/测试脚本/"
echo -e "${GREEN}✓ 数据库初始化脚本复制完成${NC}"

echo -e "  复制环境配置模板脚本..."
cp "${PROJECT_DIR}/backend/scripts/env_fill_template.sh" "${ARCHIVE_DIR}/测试脚本/"
echo -e "${GREEN}✓ 环境配置模板脚本复制完成${NC}"

echo -e "  复制一键启动脚本..."
cp "${PROJECT_DIR}/scripts/start_all.sh" "${ARCHIVE_DIR}/测试脚本/"
echo -e "${GREEN}✓ 一键启动脚本复制完成${NC}"

echo -e "  复制一键停止脚本..."
cp "${PROJECT_DIR}/scripts/stop_all.sh" "${ARCHIVE_DIR}/测试脚本/"
echo -e "${GREEN}✓ 一键停止脚本复制完成${NC}"

echo -e "  复制自动化测试脚本..."
cp "${PROJECT_DIR}/backend/tests/test_infra_all.py" "${ARCHIVE_DIR}/测试脚本/"
echo -e "${GREEN}✓ 自动化测试脚本复制完成${NC}"

echo -e "  复制操作步骤指南..."
cp "${PROJECT_DIR}/scripts/操作步骤指南.txt" "${ARCHIVE_DIR}/测试脚本/"
echo -e "${GREEN}✓ 操作步骤指南复制完成${NC}"

echo -e "  复制版本归档说明..."
cp "${PROJECT_DIR}/金角大王一期基建版本归档说明.md" "${ARCHIVE_DIR}/"
echo -e "${GREEN}✓ 版本归档说明复制完成${NC}"

# ================ 步骤5：打包成ZIP ================
echo -e ""
echo -e "${YELLOW}步骤5/5：打包成ZIP归档包...${NC}"

cd "/tmp"
zip -r "${ARCHIVE_NAME}.zip" "${ARCHIVE_NAME}" > /dev/null 2>&1

ARCHIVE_PATH="/tmp/${ARCHIVE_NAME}.zip"
ARCHIVE_SIZE=$(du -sh "${ARCHIVE_PATH}" | cut -f1)

echo -e "${GREEN}✓ ZIP归档包生成完成${NC}"
echo -e "${GREEN}  文件大小：${ARCHIVE_SIZE}${NC}"

# ================ 完成 ================
echo -e ""
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}版本归档打包完成！${NC}"
echo -e "${GREEN}==============================================${NC}"
echo ""
echo -e "${BLUE}归档包信息：${NC}"
echo -e "${BLUE}  文件路径：${ARCHIVE_PATH}${NC}"
echo -e "${BLUE}  文件名称：${ARCHIVE_NAME}.zip${NC}"
echo -e "${BLUE}  文件大小：${ARCHIVE_SIZE}${NC}"
echo ""
echo -e "${BLUE}归档内容：${NC}"
echo -e "${BLUE}  ├── 设计文档归档/      全部设计文档${NC}"
echo -e "${BLUE}  ├── 完整工程代码/      backend/admin/miniprogram${NC}"
echo -e "${BLUE}  ├── 测试脚本/          自动化测试脚本+操作指南${NC}"
echo -e "${BLUE}  └── 版本归档说明.md    归档说明文档${NC}"
echo ""
echo -e "${YELLOW}使用方式：${NC}"
echo -e "${YELLOW}  1. 解压归档包${NC}"
echo -e "${YELLOW}  2. 按照操作步骤指南启动服务${NC}"
echo -e "${YELLOW}  3. 运行自动化测试脚本验证${NC}"