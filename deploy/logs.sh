#!/usr/bin/env bash
# Логи контейнеров на сервере.
#   deploy/logs.sh            # последние 200 строк app
#   deploy/logs.sh -f         # следить
#   deploy/logs.sh db 50      # сервис и число строк
set -euo pipefail
source "$(dirname "$0")/common.sh"

FOLLOW=""
if [ "${1:-}" = "-f" ]; then FOLLOW="-f"; shift; fi
SERVICE="${1:-app}"
LINES="${2:-200}"

remote "cd $APP_DIR/current && docker compose -p $COMPOSE_PROJECT logs --tail $LINES $FOLLOW $SERVICE"
