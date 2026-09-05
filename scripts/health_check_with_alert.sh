#!/bin/bash
# 金角大王 - 健康检查 + 失败告警包装脚本 v1.0
# 每 30 分钟由 crontab 调用；health_check 失败时推送飞书告警
set -uo pipefail

LOG="/var/log/gaking-healthcheck.log"
OUT=$(bash /opt/gaking/scripts/health_check.sh http://localhost:3003 2>&1)
RC=$?

echo "[$(date "+%Y-%m-%d %H:%M:%S")] exit=$RC" >> "$LOG"
echo "$OUT" >> "$LOG"

if [ $RC -ne 0 ]; then
  FAIL_CNT=$(echo "$OUT" | grep -c "❌ FAIL" || true)
  /opt/gaking/scripts/alert_push.sh "P1" "生产健康检查失败（失败项 $FAIL_CNT），详见 /var/log/gaking-healthcheck.log" || true
fi
echo "$OUT"
exit $RC
