# Общие настройки для скриптов деплоя. Подключается через source, сам не запускается.

# Хост: локально — алиас LCT из ~/.ssh/config, в CI — user1@176.123.165.194.
DEPLOY_HOST="${DEPLOY_HOST:-LCT}"
APP_DIR="/opt/seller-assistant"
COMPOSE_PROJECT="seller-assistant"
KEEP_RELEASES="${KEEP_RELEASES:-5}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

remote() {
  ssh -o BatchMode=yes "$DEPLOY_HOST" "$@"
}
