#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王CPS返利小程序 - 批量关闭服务脚本
# 使用说明：直接运行此脚本关闭所有服务
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
LOG_DIR="$PROJECT_DIR/logs"

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}金角大王CPS返利小程序 - 批量关闭服务${NC}"
echo -e "${BLUE}==============================================${NC}"
echo ""

# ================ 步骤1：关闭后端服务 ================
echo -e "${YELLOW}步骤1/3：关闭后端服务...${NC}"
if [ -f "$LOG_DIR/backend.pid" ]; then
    PID=$(cat "$LOG_DIR/backend.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null
        echo -e "${GREEN}✓ 后端服务已关闭（PID: $PID）${NC}"
    else
        echo -e "${YELLOW}⚠️ 后端服务未运行${NC}"
    fi
    rm -f "$LOG_DIR/backend.pid"
else
    echo -e "${YELLOW}⚠️ 后端服务PID文件不存在${NC}"
fi

# ================ 步骤2：关闭Admin后台 ================
echo -e ""
echo -e "${YELLOW}步骤2/3：关闭Admin管理后台...${NC}"
if [ -f "$LOG_DIR/admin.pid" ]; then
    PID=$(cat "$LOG_DIR/admin.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null
        echo -e "${GREEN}✓ Admin后台已关闭（PID: $PID）${NC}"
    else
        echo -e "${YELLOW}⚠️ Admin后台未运行${NC}"
    fi
    rm -f "$LOG_DIR/admin.pid"
else
    echo -e "${YELLOW}⚠️ Admin后台PID文件不存在${NC}"
fi

# ================ 步骤3：关闭小程序H5 ================
echo -e ""
echo -e "${YELLOW}步骤3/3：关闭小程序H5预览...${NC}"
if [ -f "$LOG_DIR/miniprogram.pid" ]; then
    PID=$(cat "$LOG_DIR/miniprogram.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null
        echo -e "${GREEN}✓ 小程序H5已关闭（PID: $PID）${NC}"
    else
        echo -e "${YELLOW}⚠️ 小程序H5未运行${NC}"
    fi
    rm -f "$LOG_DIR/miniprogram.pid"
else
    echo -e "${YELLOW}⚠️ 小程序H5 PID文件不存在${NC}"
fi

# ================ 额外清理：关闭Python/Node进程 ================
echo -e ""
echo -e "${YELLOW}额外清理：关闭残留的Python/Node进程...${NC}"
pkill -f "uvicorn src.main:app" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
echo -e "${GREEN}✓ 残留进程清理完成${NC}"

# ================ 完成 ================
echo -e ""
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}所有服务关闭完成！${NC}"
echo -e "${GREEN}==============================================${NC}"
echo ""
echo -e "${BLUE}日志文件保留在：$LOG_DIR/${NC}"
echo -e "${YELLOW}下次启动：执行 start_all.sh${NC}"