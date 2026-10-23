#!/usr/bin/env bash
# Разовая подготовка сервера. Повторный запуск безопасен (секреты не перезаписываются).
# Создаёт /opt/seller-assistant, shared/.env со случайным паролем БД и ставит конфиг nginx.
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$REPO_ROOT"

echo "→ Каталоги и .env"
remote "sudo mkdir -p $APP_DIR/releases $APP_DIR/shared && sudo chown -R \$(id -un):\$(id -gn) $APP_DIR
if [ ! -f $APP_DIR/shared/.env ]; then
  pw=\$(openssl rand -hex 24)
  cat > $APP_DIR/shared/.env <<EOF
APP_ENV=production
LOG_LEVEL=INFO
POSTGRES_USER=app
POSTGRES_PASSWORD=\$pw
POSTGRES_DB=app
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
EOF
  chmod 600 $APP_DIR/shared/.env
  echo '  создан shared/.env'
else
  echo '  shared/.env уже есть — не трогаю'
fi"

echo "→ nginx"
remote "sudo tee /etc/nginx/sites-available/seller-assistant.conf >/dev/null" < deploy/nginx/seller-assistant.conf
remote "sudo ln -sfn /etc/nginx/sites-available/seller-assistant.conf /etc/nginx/sites-enabled/seller-assistant.conf && sudo nginx -t && sudo systemctl reload nginx"

echo "✓ Сервер готов. Дальше: deploy/env.sh push DEEPSEEK_API_KEY и deploy/deploy.sh"
