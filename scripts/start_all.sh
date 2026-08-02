#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王CPS返利小程序 - 三端一键启动脚本
# 使用说明：直接运行此脚本启动所有服务
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
BACKEND_DIR="$PROJECT_DIR/backend"
ADMIN_DIR="$PROJECT_DIR/admin"
MINIPROGRAM_DIR="$PROJECT_DIR/miniprogram"

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}金角大王CPS返利小程序 - 三端一键启动${NC}"
echo -e "${BLUE}==============================================${NC}"
echo ""

# ================ 步骤1：检查MySQL（远程数据库） ================
echo -e "${YELLOW}步骤1/5：检查远程MySQL连接...${NC}"
DB_HOST="121.37.173.132"
DB_PORT="3306"
DB_USER="gaking-dev"
DB_PASS="GAKing_dev"
if mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -e "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 远程MySQL连接成功${NC}"
else
    echo -e "${RED}✗ 远程MySQL连接失败，请检查：${NC}"
    echo -e "${RED}  1. 网络是否可访问 ${DB_HOST}:${DB_PORT}${NC}"
    echo -e "${RED}  2. 用户名密码是否正确${NC}"
    exit 1
fi

# ================ 步骤2：检查Redis ================
echo -e ""
echo -e "${YELLOW}步骤2/5：检查Redis服务...${NC}"
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis服务运行正常${NC}"
else
    echo -e "${YELLOW}⚠️ Redis服务未启动，尝试启动...${NC}"
    if command -v brew &> /dev/null; then
        brew services start redis
        sleep 2
        if redis-cli ping > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Redis服务启动成功${NC}"
        else
            echo -e "${RED}✗ Redis启动失败，请手动启动${NC}"
            exit 1
        fi
    else
        echo -e "${RED}✗ Redis服务未启动，请手动启动Redis${NC}"
        exit 1
    fi
fi

# ================ 步骤3：启动后端服务 ================
echo -e ""
echo -e "${YELLOW}步骤3/5：启动后端服务...${NC}"
cd "$BACKEND_DIR"
if ! python -c "import uvicorn" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️ 后端依赖未安装，正在安装...${NC}"
    pip install -r requirements.txt
fi

# 创建日志目录
mkdir -p logs

# 后台启动后端服务
nohup bash start_dev.sh > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > logs/backend.pid
echo -e "${GREEN}✓ 后端服务已启动（PID: $BACKEND_PID）${NC}"
echo -e "${GREEN}  访问地址：http://localhost:3001${NC}"

# 等待后端启动
sleep 3

# ================ 步骤4：启动Admin后台 ================
echo -e ""
echo -e "${YELLOW}步骤4/5：启动Admin管理后台...${NC}"
cd "$ADMIN_DIR"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠️ 前端依赖未安装，正在安装...${NC}"
    npm install
fi

nohup npm run dev > ../logs/admin.log 2>&1 &
ADMIN_PID=$!
echo "$ADMIN_PID" > ../logs/admin.pid
echo -e "${GREEN}✓ Admin后台已启动（PID: $ADMIN_PID）${NC}"
echo -e "${GREEN}  访问地址：http://localhost:5173${NC}"

# ================ 步骤5：启动小程序H5预览 ================
echo -e ""
echo -e "${YELLOW}步骤5/5：启动小程序H5预览...${NC}"
cd "$MINIPROGRAM_DIR"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠️ 小程序依赖未安装，正在安装...${NC}"
    npm install
fi

nohup npm run dev:h5 > ../logs/miniprogram.log 2>&1 &
MINIPROGRAM_PID=$!
echo "$MINIPROGRAM_PID" > ../logs/miniprogram.pid
echo -e "${GREEN}✓ 小程序H5预览已启动（PID: $MINIPROGRAM_PID）${NC}"
echo -e "${GREEN}  访问地址：http://localhost:5173${NC}"

# ================ 完成 ================
echo -e ""
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}所有服务启动完成！${NC}"
echo -e "${GREEN}==============================================${NC}"
echo ""
echo -e "${BLUE}服务列表：${NC}"
echo -e "${BLUE}  后端服务：http://localhost:3001${NC}"
echo -e "${BLUE}  Admin后台：http://localhost:5173${NC}"
echo -e "${BLUE}  小程序H5：http://localhost:5173${NC}"
echo ""
echo -e "${YELLOW}日志文件位置：${PROJECT_DIR}/logs/${NC}"
echo ""
echo -e "${YELLOW}下一步：执行 test_infra_all.py 运行自动化测试${NC}"
echo -e "${YELLOW}停止服务：执行 stop_all.sh${NC}"