#!/bin/bash
# @ai-generated
# ============================================================
# 金角大王 - 日志查看脚本
# 支持实时跟踪、查看最近N行、关键词搜索
#
# 用法：
#   ./view_logs.sh              # 实时跟踪后端日志（默认）
#   ./view_logs.sh 100          # 查看最近100行
#   ./view_logs.sh search ERROR # 搜索包含ERROR的日志
#   ./view_logs.sh admin        # 查看admin前端日志
#   ./view_logs.sh miniapp      # 查看小程序日志
# ============================================================

set -euo pipefail

BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
LOG_DIR="$PROJECT_DIR/logs"

# 确定日志文件
TARGET="${2:-backend}"
if [[ "${1:-}" =~ ^[0-9]+$ ]]; then
    # 第一个参数是数字 → 查看最近N行后端日志
    TAIL_LINES="$1"
    LOG_FILE="$LOG_DIR/backend.log"
elif [[ "${1:-}" == "search" ]]; then
    # 搜索模式
    KEYWORD="${2:-ERROR}"
    LOG_FILE="$LOG_DIR/backend.log"
    echo -e "${GREEN}搜索关键词: $KEYWORD${NC}"
    echo -e "${GREEN}日志文件: $LOG_FILE${NC}"
    echo "----------------------------------------"
    grep -n "$KEYWORD" "$LOG_FILE" 2>/dev/null | tail -50 || echo "无匹配结果"
    exit 0
elif [[ "${1:-}" == "admin" ]]; then
    LOG_FILE="$LOG_DIR/admin.log"
    TAIL_LINES="${2:-50}"
elif [[ "${1:-}" == "miniapp" ]]; then
    LOG_FILE="$LOG_DIR/miniprogram.log"
    TAIL_LINES="${2:-50}"
else
    # 默认实时跟踪后端日志
    LOG_FILE="$LOG_DIR/backend.log"
    TAIL_LINES="${1:-0}"
fi

if [ ! -f "$LOG_FILE" ]; then
    echo "日志文件不存在: $LOG_FILE"
    echo "可用日志:"
    ls -la "$LOG_DIR"/*.log 2>/dev/null || echo "  无日志文件"
    exit 1
fi

echo -e "${BLUE}日志文件: $LOG_FILE${NC}"
echo -e "${BLUE}文件大小: $(du -h "$LOG_FILE" | cut -f1)${NC}"
echo "----------------------------------------"

if [ "$TAIL_LINES" == "0" ]; then
    # 实时跟踪模式
    echo -e "${GREEN}实时跟踪中（Ctrl+C 退出）...${NC}"
    echo ""
    tail -f "$LOG_FILE"
else
    # 查看最近N行
    tail -n "$TAIL_LINES" "$LOG_FILE"
fi
