#!/bin/bash
# 金角大王 - 每日自动巡检脚本 v1.0（2026-09-05）
# 自动检查：服务健康 / 备份完整性 / 磁盘 / 内存 / 证书 / 容器 / 定时任务 / 日志错误
# 输出报告 /opt/gaking/inspect/report-YYYYMMDD.md（保留 7 天）
# 退出码：0=全部通过 1=有警告 2=有失败（可接提醒通道）
set -uo pipefail
# crontab 默认 PATH 不含 /usr/local/bin（obsutil 所在），显式补齐
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

REPORT_DIR="/opt/gaking/inspect"
REPORT="$REPORT_DIR/report-$(date +%Y%m%d).md"
RETENTION_DAYS=7
NOW="$(date '+%Y-%m-%d %H:%M:%S')"

PASS=0; WARN=0; FAIL=0
LINES=()

log_line() { LINES+=("$1"); }

check() { # check <结果> <说明>  结果: PASS/WARN/FAIL
  case "$1" in
    PASS) PASS=$((PASS+1)); LINES+=("✅ PASS | $2");;
    WARN) WARN=$((WARN+1)); LINES+=("⚠️ WARN | $2");;
    FAIL) FAIL=$((FAIL+1)); LINES+=("❌ FAIL | $2");;
  esac
}

# ── 1. 服务健康（复用 health_check.sh） ──
if bash /opt/gaking/scripts/health_check.sh http://localhost:3003 >/tmp/hc_ins.log 2>&1; then
  check PASS "服务健康检查全部通过（health_check.sh）"
else
  HC_FAIL=$(grep -c "❌ FAIL" /tmp/hc_ins.log || true)
  check FAIL "服务健康检查失败 ${HC_FAIL} 项（详见 /tmp/hc_ins.log）"
fi

# ── 2. 备份完整性（本地 + OBS 远端） ──
LATEST=$(ls -t /opt/gaking/backup/gak_*.sql.gz 2>/dev/null | head -1)
if [ -n "$LATEST" ] && [ "$(stat -c %Y "$LATEST")" -ge $(( $(date +%s) - 86400 )) ] && [ -s "$LATEST" ]; then
  SIZE=$(du -h "$LATEST" | cut -f1)
  check PASS "今日本地备份存在: $(basename "$LATEST") ($SIZE)"
else
  check FAIL "最近 24h 无有效本地备份"
fi
if command -v obsutil >/dev/null 2>&1; then
  OBS_CNT=$(obsutil ls "obs://goldalicorn/prod/backup/db/" 2>/dev/null | grep -c "$(date +%Y%m%d)" || true)
  if [ "$OBS_CNT" -ge 1 ]; then
    check PASS "OBS 异地备份今日存在（${OBS_CNT} 份）"
  else
    check FAIL "OBS 异地备份今日缺失"
  fi
else
  check WARN "obsutil 未安装，跳过 OBS 校验"
fi

# ── 3. 磁盘空间 ──
DISK_USED=$(df / | awk 'NR==2{gsub(/%/,"",$5); print $5}')
if [ "$DISK_USED" -ge 92 ]; then
  check FAIL "根分区使用率 ${DISK_USED}%（>92%）"
elif [ "$DISK_USED" -ge 85 ]; then
  check WARN "根分区使用率 ${DISK_USED}%（>85%）"
else
  check PASS "根分区使用率 ${DISK_USED}%（<85%）"
fi

# ── 4. 内存（available，含可回收 cache） ──
MEM_AVAIL=$(free -m | awk 'NR==2{print $7}')
if [ "$MEM_AVAIL" -lt 500 ]; then
  check FAIL "可用内存 ${MEM_AVAIL}MB（<500MB）"
elif [ "$MEM_AVAIL" -lt 800 ]; then
  check WARN "可用内存 ${MEM_AVAIL}MB（<800MB）"
else
  check PASS "可用内存 ${MEM_AVAIL}MB"
fi

# ── 5. SSL 证书剩余天数（wild_dftsh） ──
CERT_FILE="/etc/letsencrypt/live/wild_dftsh/fullchain.pem"
if [ -f "$CERT_FILE" ]; then
  CERT_END=$(openssl x509 -enddate -noout -in "$CERT_FILE" | cut -d= -f2)
  CERT_DAYS=$(( ( $(date -d "$CERT_END" +%s) - $(date +%s) ) / 86400 ))
  if [ "$CERT_DAYS" -lt 7 ]; then
    check FAIL "证书 ${CERT_DAYS} 天后到期（$CERT_END）"
  elif [ "$CERT_DAYS" -lt 30 ]; then
    check WARN "证书仅剩 ${CERT_DAYS} 天（$CERT_END）"
  else
    check PASS "证书剩余 ${CERT_DAYS} 天（$CERT_END）"
  fi
else
  check WARN "未找到证书文件 $CERT_FILE"
fi

# ── 6. 金角大王容器状态 ──
for C in gaking-backend gaking-admin gaking-redis; do
  if docker inspect -f '{{.State.Running}}' "$C" 2>/dev/null | grep -q true; then
    HEALTH=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$C" 2>/dev/null)
    check PASS "容器 $C 运行中（$HEALTH）"
  else
    check FAIL "容器 $C 未运行"
  fi
done

# ── 7. 定时任务执行核对 ──
HC_LOG="/var/log/gaking-healthcheck.log"
if [ -f "$HC_LOG" ]; then
  HC_AGE=$(( $(date +%s) - $(stat -c %Y "$HC_LOG") ))
  if [ "$HC_AGE" -le 5400 ]; then
    check PASS "健康检查定时任务正常（${HC_AGE}s 前执行）"
  else
    check FAIL "健康检查定时任务 ${HC_AGE}s 未执行"
  fi
else
  check WARN "健康检查日志不存在（crontab 可能未生效）"
fi

# ── 8. 后端容器日志错误扫描（近 24h，仅统计） ──
ERR_CNT=$(docker logs --since 24h gaking-backend 2>&1 | grep -cE "ERROR|Traceback" || true)
if [ "$ERR_CNT" -gt 50 ]; then
  check WARN "后端近 24h 日志错误 ${ERR_CNT} 条（>50）"
elif [ "$ERR_CNT" -gt 0 ]; then
  check PASS "后端近 24h 日志错误 ${ERR_CNT} 条（≤50，需抽查）"
else
  check PASS "后端近 24h 无 ERROR/Traceback"
fi

# ── 生成报告 ──
mkdir -p "$REPORT_DIR" && chmod 700 "$REPORT_DIR"
{
  echo "# 金角大王每日巡检报告 - $(date +%Y-%m-%d)"
  echo ""
  echo "- 生成时间: $NOW"
  echo "- 汇总: ✅通过 $PASS / ⚠️警告 $WARN / ❌失败 $FAIL"
  echo ""
  echo "## 检查明细"
  echo ""
  for L in "${LINES[@]}"; do echo "- $L"; done
  echo ""
  if [ "$FAIL" -gt 0 ]; then
    echo "## 结论: ❌ 存在失败项，需人工确认处置"
  elif [ "$WARN" -gt 0 ]; then
    echo "## 结论: ⚠️ 存在警告项，建议关注"
  else
    echo "## 结论: ✅ 全部通过"
  fi
} > "$REPORT"

find "$REPORT_DIR" -name "report-*.md" -mtime +"$RETENTION_DAYS" -delete

# ── 提醒通道（可选：未配置时仅落报告） ──
if [ "$FAIL" -gt 0 ] || [ "$WARN" -gt 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 巡检发现异常（PASS=$PASS WARN=$WARN FAIL=$FAIL），报告: $REPORT" >> /var/log/gaking-inspect.log
  # 提醒通道占位：配置 REMINDER_CMD 后自动执行（如 mailx/Server酱/curl 均可）
  REMINDER_CMD="${REMINDER_CMD:-}"
  if [ -n "$REMINDER_CMD" ]; then
    eval "$REMINDER_CMD" >> /var/log/gaking-inspect.log 2>&1
  fi
fi

echo "巡检完成: PASS=$PASS WARN=$WARN FAIL=$FAIL 报告=$REPORT"
exit $(( FAIL>0 ? 2 : (WARN>0 ? 1 : 0) ))
