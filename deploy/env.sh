#!/usr/bin/env bash
# Переменные окружения на сервере (файл /opt/seller-assistant/shared/.env).
#   deploy/env.sh list                    # ключи, значения скрыты
#   deploy/env.sh push DEEPSEEK_API_KEY   # взять значение из локального .env
#   deploy/env.sh set LOG_LEVEL=DEBUG     # задать явно
# После изменения приложение перезапускается.
set -euo pipefail
source "$(dirname "$0")/common.sh"

ENV_FILE="$APP_DIR/shared/.env"

set_remote() {
  local key="$1" value="$2"
  [[ "$key" =~ ^[A-Z_][A-Z0-9_]*$ ]] || { echo "Плохое имя ключа: $key" >&2; exit 1; }
  printf '%s' "$value" | remote "v=\$(cat); f=$ENV_FILE; grep -v '^$key=' \$f > \$f.tmp || true; printf '%s=%s\n' '$key' \"\$v\" >> \$f.tmp; mv \$f.tmp \$f; chmod 600 \$f"
  echo "✓ $key обновлён"
}

restart() {
  remote "cd $APP_DIR/current && docker compose -p $COMPOSE_PROJECT up -d --force-recreate app" >/dev/null
  echo "✓ app перезапущен"
}

case "${1:-}" in
  list)
    remote "sed -E 's/=.+/=***/' $ENV_FILE"
    ;;
  push)
    key="${2:?укажите ключ}"
    line="$(grep -E "^$key=" "$REPO_ROOT/.env" | tail -1)" || { echo "$key нет в локальном .env" >&2; exit 1; }
    set_remote "$key" "${line#*=}"
    restart
    ;;
  set)
    pair="${2:?укажите KEY=VALUE}"
    set_remote "${pair%%=*}" "${pair#*=}"
    restart
    ;;
  *)
    sed -n '2,6p' "$0"; exit 1
    ;;
esac
