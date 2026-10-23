#!/usr/bin/env bash
# Выкатывает текущее состояние репозитория на сервер.
# Берутся все файлы, которые не в .gitignore, в том числе незакоммиченные
# (такой релиз помечается -dirty). Сервер не ходит в GitHub — код приезжает архивом.
#
#   deploy/deploy.sh                 # на LCT из ~/.ssh/config
#   DEPLOY_HOST=user@host deploy/deploy.sh
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$REPO_ROOT"

SHA="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
RELEASE="$(date +%Y%m%d-%H%M%S)-$SHA"
[ -z "$(git status --porcelain 2>/dev/null)" ] || RELEASE="$RELEASE-dirty"

echo "→ Релиз $RELEASE → $DEPLOY_HOST"

git ls-files -z --cached --others --exclude-standard \
  | while IFS= read -r -d '' f; do [ -e "$f" ] && printf '%s\0' "$f"; done \
  | tar --null -czf - -T - \
  | remote "mkdir -p $APP_DIR/releases/$RELEASE && tar -xzf - -C $APP_DIR/releases/$RELEASE"

remote "bash -s -- '$RELEASE' '$KEEP_RELEASES'" < deploy/remote/activate.sh

echo "✓ Готово: https://utility-monitor.ru"
