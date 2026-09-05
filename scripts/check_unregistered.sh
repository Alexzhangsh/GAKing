#!/bin/bash
# 金角大王 - check_unregistered.sh 未登记改动探测（M07-5 硬约束②的机器兜底）
# 职责：发布前扫描"git 提交/工作区改动 vs 批次清单登记"，发现未登记改动即阻断，防漏发
# 用法：bash scripts/check_unregistered.sh [提交条数]
# 退出码：0=无未登记改动  1=存在未登记提交/未编号提交/工作区改动（发布前必须处理）
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LIST="$REPO/docs/发布协作/发布步骤清单.md"
COUNT="${1:-20}"

[ -f "$LIST" ] || { echo "[阻断] 未找到批次清单: $LIST" >&2; exit 2; }
cd "$REPO"

# 已登记批次号（清单表格第一列，形如 S15-1 / M07-5）
REGISTERED=$(grep -oE '^\| *[A-Z]+[0-9]+(-[0-9]+)* *\|' "$LIST" | sed -E 's/^\| *//; s/ *\|$//' | sort -u)
# 交接单中引用的 git commit（经交接单关联视为已登记，如"完整变更范围 = git commit 0e2c18c"）
KNOWN_COMMITS=$(grep -rhoE "git commit [0-9a-f]{7,40}" "$REPO/docs/发布协作/交接单/" 2>/dev/null | grep -oE "[0-9a-f]{7,40}" | sort -u)
# 已确认豁免的提交（人工确认过无需登记：如项目初始化）
EXEMPT_PATTERNS="初始化金角大王|chore: 初始化"

echo "=== 已登记批次 ==="
echo "${REGISTERED:-（清单为空）}" | sed 's/^/  /'
echo ""
echo "=== 扫描最近 $COUNT 个 git 提交 ==="

RC=0
TMP=$(mktemp)
git log --oneline -"$COUNT" > "$TMP" 2>/dev/null || { echo "git log 失败" >&2; rm -f "$TMP"; exit 2; }

while IFS= read -r line; do
  [ -n "$line" ] || continue
  HASH=$(echo "$line" | awk '{print $1}')
  MSG=$(echo "$line" | cut -d' ' -f2-)
  TID=$(echo "$MSG" | grep -oE '^[A-Z]+[0-9]+-[0-9]+' | head -1)
  if echo "$KNOWN_COMMITS" | grep -qx "$HASH"; then
    echo "  ✅ 已登记（经交接单关联）: $HASH $MSG"
  elif echo "$MSG" | grep -qE "$EXEMPT_PATTERNS"; then
    echo "  ✅ 已确认豁免（人工确认无需登记）: $HASH $MSG"
  elif [ -z "$TID" ]; then
    echo "  ❌ 提交无任务编号且无交接单关联（无法追踪）: $HASH $MSG"
    RC=1
  elif ! grep -qE "^\| *$TID *\|" "$LIST"; then
    echo "  ❌ 提交未在批次清单登记: $HASH $MSG"
    RC=1
  else
    echo "  ✅ $TID 已登记: $HASH $MSG"
  fi

done < "$TMP"
rm -f "$TMP"

echo ""
echo "=== 工作区未提交改动 ==="
UNSTAGED=$(git status --short)
if [ -n "$UNSTAGED" ]; then
  echo "$UNSTAGED" | head -20 | sed 's/^/  /'
  echo "  ⚠️ 有未提交改动：属开发内容先补登记批次；临时文件确认无需登记"
  RC=$((RC==0?1:RC))
else
  echo "  ✅ 工作区干净"
fi

echo ""
if [ "$RC" -eq 0 ]; then
  echo "✅ 探测通过：无未登记改动，可进入发布流程"
else
  echo "❌ 探测发现未登记改动（exit 1）：先补登记批次+交接单再发布"
fi
exit $RC
