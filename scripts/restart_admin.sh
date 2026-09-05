#!/bin/bash
# ============================================================
# 金角大王 - 管理后台（安全重启版）
# 自动杀掉占用 8080 端口的旧进程，再启动新的
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="/Users/alexzhang/Documents/Work/Projects/Products/金角大王/GAKing-Coding"
ADMIN_DIR="$PROJECT_DIR/admin"
PORT=8080

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE} 金角大王 - 管理后台（安全重启版）${NC}"
echo -e "${BLUE}==============================================${NC}"
echo ""

# 切换 Node 版本
echo -e "${YELLOW}▶ 切换 Node.js 版本...${NC}"
unset NPM_CONFIG_PREFIX && source ~/.nvm/nvm.sh && nvm use v18.20.8 > /dev/null 2>&1
echo -e "${GREEN}  ✓ $(node -v)${NC}"

# 检查并杀掉占用端口的旧进程
echo ""
echo -e "${YELLOW}▶ 检查端口 $PORT 占用...${NC}"
OLD_PIDS=$(lsof -ti :$PORT 2>/dev/null)
if [ -n "$OLD_PIDS" ]; then
    echo -e "${YELLOW}  发现旧进程，正在杀掉：$OLD_PIDS${NC}"
    kill -9 $OLD_PIDS 2>/dev/null
    sleep 1
    REMAINING=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$REMAINING" ]; then
        kill -9 $REMAINING 2>/dev/null
        sleep 1
    fi
    echo -e "${GREEN}  ✓ 旧进程已清理${NC}"
else
    echo -e "${GREEN}  ✓ 端口 $PORT 空闲${NC}"
fi

echo ""
echo -e "${YELLOW}▶ 启动管理后台...${NC}"
echo -e "${GREEN}  访问地址：http://localhost:$PORT${NC}"
echo ""
cd "$ADMIN_DIR"

npm run dev
