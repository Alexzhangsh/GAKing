#!/bin/bash
# 金角大王 - release_check.sh 批次硬闸门（小脉养车模式迁移 v1.0）
# 职责：发布/上传前核对批次交接单，防止"构建漏带晚改文件 / 登记后又改未重新登记"
# 用法：bash scripts/release_check.sh <批次交接单.md>
# 退出码：0=通过  1=阻断（有文件晚于登记时间 / 构建产物缺失或早于源码）  2=用法错/交接单缺段
set -uo pipefail

if [ $# -ne 1 ]; then
  echo "[用法] bash scripts/release_check.sh <批次交接单.md>" >&2
  exit 2
fi
DOC="$1"
[ -f "$DOC" ] || { echo "[阻断] 交接单不存在: $DOC" >&2; exit 2; }

# 平台兼容时间戳
ts() { # ts <文件> → 秒
  if [ "$(uname)" = "Darwin" ]; then stat -f %m "$1"; else stat -c %Y "$1"; fi
}

# ── 解析交接单字段 ──
STAMP=$(grep -m1 "^落盘时间:" "$DOC" | sed 's/^落盘时间:[[:space:]]*//')
[ -n "$STAMP" ] || { echo "[阻断] 交接单缺少「落盘时间」字段" >&2; exit 2; }
STAMP_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$STAMP" +%s 2>/dev/null || date -d "$STAMP" +%s 2>/dev/null)
[ -n "$STAMP_EPOCH" ] || { echo "[阻断] 落盘时间格式错误: $STAMP（应为 YYYY-MM-DD HH:MM:SS）" >&2; exit 2; }

# 涉及源码清单（交接单内「涉及源码清单:」后到下一个段落标记前的缩进行）
SRC_LIST=$(awk '/^涉及源码清单:/{f=1;next} /^构建产物:/{f=0} f && /^[[:space:]]+[^[:space:]]/{gsub(/^[[:space:]]+/,""); print}' "$DOC")
[ -n "$SRC_LIST" ] || { echo "[阻断] 交接单「涉及源码清单」为空" >&2; exit 2; }

ART=$(awk '/^构建产物:/{f=1;next} /^— —/{f=0} f && /^[[:space:]]+[^[:space:]]/{gsub(/^[[:space:]]+/,""); print; exit}' "$DOC")
ART_PATH="${ART%%|*}"; ART_PATH="${ART_PATH%% *}"
ART_STAMP=$(echo "$ART" | grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" | head -1)

# ── 核对 1：源码文件存在 + 未晚于落盘时间 ──
RC=0
LATEST_SRC=0
IFS=$'\n' read -d '' -ra SRC_FILES <<< "$SRC_LIST" 2>/dev/null || true
for f in "${SRC_FILES[@]:-}"; do
  [ -n "$f" ] || continue
  if [ ! -f "$f" ]; then
    echo "❌ FAIL | 源码文件不存在: $f" >&2
    RC=1
    continue
  fi
  MT=$(ts "$f")
  [ "$MT" -gt "$LATEST_SRC" ] && LATEST_SRC=$MT
  if [ "$MT" -gt "$STAMP_EPOCH" ]; then
    echo "❌ FAIL | 文件晚于交接单登记时间（登记 $STAMP 后又被修改）: $f" >&2
    RC=1
  else
    echo "✅ PASS | ${f}（mtime ≤ 登记时间）"
  fi
done <<< "$SRC_LIST"

# ── 核对 2：构建产物 ──
if [ -n "$ART_PATH" ]; then
  if [ ! -f "$ART_PATH" ]; then
    echo "❌ FAIL | 构建产物不存在: $ART_PATH" >&2
    RC=1
  else
    ART_MT=$(ts "$ART_PATH")
    if [ "$ART_MT" -lt "$LATEST_SRC" ]; then
      echo "❌ FAIL | 构建产物早于源码最后修改（可能漏带晚改文件）: $ART_PATH" >&2
      RC=1
    else
      echo "✅ PASS | 构建产物 ${ART_PATH}（mtime ≥ 全部源码）"
    fi
    if [ -n "$ART_STAMP" ]; then
      ART_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$ART_STAMP" +%s 2>/dev/null || date -d "$ART_STAMP" +%s 2>/dev/null)
      [ "$ART_MT" -eq "$ART_EPOCH" ] 2>/dev/null && echo "✅ PASS | 构建产物时间戳与交接单一致" || echo "⚠️ WARN | 构建产物时间戳与交接单声明不一致（声明 $ART_STAMP）"
    fi
  fi
else
  echo "⚠️ WARN | 交接单未声明构建产物（跳过产物核对）"
fi

if [ "$RC" -eq 0 ]; then
  echo "✅ 硬闸门通过（exit 0）：可进入发布流程"
else
  echo "❌ 硬闸门阻断（exit 1）：请修复后重新登记交接单"
fi
exit $RC
