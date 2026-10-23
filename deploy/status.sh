#!/usr/bin/env bash
# Что сейчас запущено на сервере.
set -euo pipefail
source "$(dirname "$0")/common.sh"

remote "echo \"Текущий релиз: \$(basename \$(readlink -f $APP_DIR/current 2>/dev/null) 2>/dev/null)\"
echo 'Релизы:'; ls -1t $APP_DIR/releases 2>/dev/null | sed 's/^/  /'
echo; docker compose -p $COMPOSE_PROJECT ps
echo; echo -n 'readyz: '; curl -fsS http://127.0.0.1:8000/readyz || echo 'НЕ ОТВЕЧАЕТ'
echo; df -h / | tail -1"
