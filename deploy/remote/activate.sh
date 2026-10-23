#!/usr/bin/env bash
# Выполняется НА СЕРВЕРЕ (deploy.sh и rollback.sh передают его через ssh).
# Поднимает указанный релиз, ждёт /readyz, при неудаче возвращает предыдущий.
# Аргументы: <имя релиза> <сколько релизов хранить>
set -euo pipefail

RELEASE="$1"
KEEP="${2:-5}"
APP_DIR="/opt/seller-assistant"
PROJECT="seller-assistant"
TARGET="$APP_DIR/releases/$RELEASE"

[ -d "$TARGET" ] || { echo "Нет релиза $TARGET" >&2; exit 1; }
[ -f "$APP_DIR/shared/.env" ] || { echo "Нет $APP_DIR/shared/.env — запустите deploy/server-setup.sh" >&2; exit 1; }

ln -sfn "$APP_DIR/shared/.env" "$TARGET/.env"
PREV="$(readlink -f "$APP_DIR/current" 2>/dev/null || true)"

up() {
  (cd "$1" && docker compose -p "$PROJECT" up -d --build --remove-orphans)
}

wait_ready() {
  for _ in $(seq 1 45); do
    if curl -fsS http://127.0.0.1:8000/readyz >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}

echo "→ Сборка и запуск $RELEASE"
up "$TARGET"

if wait_ready; then
  ln -sfn "$TARGET" "$APP_DIR/current"
  echo "✓ $RELEASE работает"
else
  echo "✗ $RELEASE не ответил на /readyz. Последние логи:" >&2
  (cd "$TARGET" && docker compose -p "$PROJECT" logs --tail 60 app) >&2 || true
  if [ -n "$PREV" ] && [ -d "$PREV" ] && [ "$PREV" != "$TARGET" ]; then
    echo "↩ Откат на $(basename "$PREV")" >&2
    up "$PREV"
    wait_ready && echo "✓ Откат выполнен" >&2
  fi
  exit 1
fi

# Чистка: оставляем KEEP последних релизов (текущий не трогаем) и висячие образы.
cd "$APP_DIR/releases"
ls -1t | tail -n +"$((KEEP + 1))" | while read -r old; do
  [ "$APP_DIR/releases/$old" = "$(readlink -f "$APP_DIR/current")" ] || rm -rf "$old"
done
docker image prune -f >/dev/null
