#!/bin/bash
# 把 ~/.agents/skills/lottery-exclusion-v2 的最新内容同步进仓库内的插件目录。
# 用法: ./sync.sh   （同步后 git add/commit/push 发布）
set -euo pipefail
SRC="$HOME/.agents/skills/lottery-exclusion-v2"
DST="$(cd "$(dirname "$0")" && pwd)/plugins/lottery-exclusion/skills/lottery-exclusion-v2"
[ -d "$SRC" ] || { echo "源目录不存在: $SRC"; exit 1; }
rm -rf "$DST"
mkdir -p "$DST"
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' "$SRC"/ "$DST"/
find "$DST" -name '__pycache__' -type d -prune -exec rm -rf {} +
echo "✅ 已同步 $SRC -> $DST"
