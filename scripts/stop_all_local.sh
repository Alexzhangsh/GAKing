#!/bin/bash
# ============================================================
# 金角大王 - 一键停止所有服务
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}==============================================${NC}"
echo -e "${RED} 金角大王 - 停止所有服务${NC}"
echo -e "${RED}==============================================${NC}"
echo ""

PORTS=(3001 8080 5173)
NAMES=("后端" "管理后台" "小程序H5")

for i in "${!PORTS[@]}"; do
    PORT=${PORTS[$i]}
    NAME=${NAMES[$i]}
    PIDS=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}▶ 停止 $NAME（端口 $PORT）：$PIDS${NC}"
        kill -9 $PIDS 2>/dev/null
        sleep 1
        REMAINING=$(lsof -ti :$PORT 2>/dev/null)
        if [ -n "$REMAINING" ]; then
            kill -9 $REMAINING 2>/dev/null
        fi
        echo -e "${GREEN}  ✓ 已停止${NC}"
    else
        echo -e "${GREEN}▶ $NAME（端口 $PORT）未运行${NC}"
    fi
    echo ""
done

echo -e "${GREEN}所有服务已停止。${NC}"
