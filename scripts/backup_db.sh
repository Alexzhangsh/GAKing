#!/bin/bash
# 金角大王 - MySQL 每日自动备份脚本 v1.1（2026-09-05 增加 OBS 异地副本）
# 凭据从 .env.production 读取，禁止硬编码密钥
# 本地保留 7 天；obsutil 就绪时上传 OBS 并保留 30 天
set -euo pipefail

# cron 环境 PATH 默认不含 /usr/local/bin，obsutil 装在该目录会导致 OBS 上传被跳过（2026-09-07 修复）
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

ENV_FILE="/opt/gaking/backend/.env.production"
BACKUP_DIR="/opt/gaking/backup"
RETENTION_DAYS=7
OBS_RETENTION_DAYS=30
LOG_FILE="/var/log/gaking-backup.log"

log() { echo "[$(date "+%Y-%m-%d %H:%M:%S")] $1"; }

DB_HOST=$(grep "^DB_HOST=" "$ENV_FILE" | cut -d"=" -f2-)
DB_PORT=$(grep "^DB_PORT=" "$ENV_FILE" | cut -d"=" -f2-)
DB_USERNAME=$(grep "^DB_USERNAME=" "$ENV_FILE" | cut -d"=" -f2-)
DB_PASSWORD=$(grep "^DB_PASSWORD=" "$ENV_FILE" | cut -d"=" -f2-)
DB_DATABASE=$(grep "^DB_DATABASE=" "$ENV_FILE" | cut -d"=" -f2-)

for var in DB_HOST DB_PORT DB_USERNAME DB_PASSWORD DB_DATABASE; do
  if [ -z "${!var}" ]; then log "[ERROR] $var 为空"; exit 1; fi
done

mkdir -p "$BACKUP_DIR" && chmod 700 "$BACKUP_DIR"

TS=$(date +%Y%m%d_%H%M%S)
OUT_FILE="$BACKUP_DIR/gak_${TS}.sql.gz"

MYSQL_PWD="$DB_PASSWORD" mysqldump \
  -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USERNAME" \
  --single-transaction --quick --routines --triggers \
  --skip-lock-tables \
  "$DB_DATABASE" 2>>"$LOG_FILE" | gzip > "$OUT_FILE"

if [ ! -s "$OUT_FILE" ]; then
  log "[ERROR] 备份为空: $OUT_FILE"
  rm -f "$OUT_FILE"
  exit 1
fi

find "$BACKUP_DIR" -name "gak_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete

# ── OBS 异地副本（可选，obsutil 就绪时启用） ──
OBS_AK=$(grep "^OBS_ACCESS_KEY_ID=" "$ENV_FILE" | cut -d"=" -f2-)
OBS_SK=$(grep "^OBS_SECRET_ACCESS_KEY=" "$ENV_FILE" | cut -d"=" -f2-)
OBS_EP=$(grep "^OBS_ENDPOINT=" "$ENV_FILE" | cut -d"=" -f2-)
OBS_BUCKET=$(grep "^OBS_BUCKET_NAME=" "$ENV_FILE" | cut -d"=" -f2-)
OBS_PREFIX=$(grep "^OBS_PROJECT_PREFIX=" "$ENV_FILE" | cut -d"=" -f2-)

if command -v obsutil >/dev/null 2>&1 && [ -n "$OBS_AK" ] && [ -n "$OBS_SK" ] && [ -n "$OBS_BUCKET" ]; then
  obsutil config -i="$OBS_AK" -k="$OBS_SK" -e="$OBS_EP" >/dev/null 2>&1 || true
  REMOTE_DIR="obs://$OBS_BUCKET/$OBS_PREFIX/backup/db"
  if obsutil cp "$OUT_FILE" "$REMOTE_DIR/$(basename "$OUT_FILE")" -f -u >/dev/null 2>&1; then
    log "[OK] 已上传 OBS: $REMOTE_DIR/$(basename "$OUT_FILE")"
    # 清理 OBS 上超过保留期的备份（按文件名时间戳 gak_YYYYMMDD_HHMMSS）
    obsutil ls "$REMOTE_DIR/" 2>/dev/null | grep -oE "gak_[0-9]{8}_[0-9]{6}\.sql\.gz" | sort -u | while read -r fn; do
      TS=${fn:4:8}
      if [ "$TS" -lt "$(date -d "-$OBS_RETENTION_DAYS days" +%Y%m%d)" ]; then
        obsutil rm "$REMOTE_DIR/$fn" -f >/dev/null 2>&1 && log "[OK] 已清理 OBS 过期备份: $fn"
      fi
    done
  else
    log "[WARN] OBS 上传失败（本地备份仍保留）"
  fi
else
  log "[WARN] obsutil 未安装或 OBS 配置缺失，跳过异地上传"
fi

SIZE=$(du -h "$OUT_FILE" | cut -f1)
log "[OK] 备份完成: $OUT_FILE ($SIZE)"
exit 0
