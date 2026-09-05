#!/bin/bash
# 金角大王 - 飞书机器人告警推送脚本 v1.0
# 用法: alert_push.sh "P1" "消息内容"
# 配置: /opt/gaking/deploy/alert_env.sh 中的 WEBHOOK_URL
set -euo pipefail

CONFIG="/opt/gaking/deploy/alert_env.sh"
[ -f "$CONFIG" ] && source "$CONFIG" || { echo "[ERROR] 缺少配置 $CONFIG"; exit 1; }
if [ -z "${WEBHOOK_URL:-}" ]; then echo "[ERROR] WEBHOOK_URL 未配置，请在 $CONFIG 中填写"; exit 1; fi

LEVEL="${1:-P3}"
MSG="${2:-}"
[ -z "$MSG" ] && { echo "[ERROR] 消息内容为空"; exit 1; }

HOST=$(hostname)
NOW=$(date "+%Y-%m-%d %H:%M:%S")
PAYLOAD=$(python3 -c "
import json,sys
text = \"[$LEVEL][$HOST][$NOW] $MSG\"
print(json.dumps({\"msg_type\":\"text\",\"content\":{\"text\":text}}, ensure_ascii=False))
")

CODE=$(curl -s -o /tmp/feishu_alert_resp.txt -w "%{http_code}" -X POST \
  -H "Content-Type: application/json" -d "$PAYLOAD" "$WEBHOOK_URL" --max-time 10 || echo "000")
echo "推送完成 HTTP=$CODE"
exit 0
