#!/usr/bin/env bash
# Откат на предыдущий релиз (или на указанный).
#   deploy/rollback.sh                       # на релиз перед текущим
#   deploy/rollback.sh 20261023-2010-ab12cd  # на конкретный (список: deploy/status.sh)
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$REPO_ROOT"

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  TARGET="$(remote "cd $APP_DIR/releases && cur=\$(basename \$(readlink -f $APP_DIR/current)) && ls -1t | grep -vx \"\$cur\" | head -1")"
fi
[ -n "$TARGET" ] || { echo "Нет релиза для отката" >&2; exit 1; }

echo "↩ Откат на $TARGET"
remote "bash -s -- '$TARGET' '$KEEP_RELEASES'" < deploy/remote/activate.sh
