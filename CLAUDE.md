# CLAUDE.md

Инструкции для ИИ-ассистентов (Claude Code и др.) и для людей в команде. Держите файл актуальным: поменяли соглашение — поправьте здесь в том же коммите.

## Проект

**marketPilot AI** — ИИ-система поддержки управленческих решений продавца на маркетплейсах (Wildberries, Ozon). Учебный проект курса «Практика создания продуктов ИИ», МГИМО, 2026.

- Требования и что уже реализовано в прототипе: [docs/requirements.md](docs/requirements.md).
- Ключевой принцип: **цифры считают правила** (`services/analytics.py`, чистые функции), **LLM только объясняет** (`services/ai.py`) и не придумывает чисел. Решение принимает человек (журнал решений).
- Данные — демо-магазин `services/demo_data.py` (загружается автоматически в пустую БД). Новые правила проверяйте тестами в `tests/test_analytics.py`.
- Что нужно сдать по курсу: [docs/course-requirements.md](docs/course-requirements.md). Предзащита 24.10, защита 30.10.
- Решения по архитектуре и стеку с причинами: [docs/decisions.md](docs/decisions.md).
- Экономика, чувствительность и план пилота: [docs/economics.md](docs/economics.md).
- `raw_docs/` — лекции и шаблоны курса. Лежат только локально (в `.gitignore`), **репозиторий публичный**.

## Стек

| Слой | Что |
|---|---|
| Язык | Python 3.12, зависимости через **uv** (`pyproject.toml` + `uv.lock`) |
| Веб | FastAPI, HTML-страницы: Jinja2 + HTMX + Tailwind 4 + DaisyUI 5 + Chart.js (всё с CDN, без сборки) |
| БД | PostgreSQL 16, SQLAlchemy 2 (sync), миграции Alembic |
| LLM | **DeepSeek** через SDK `openai` (OpenAI-совместимый API), модель `deepseek-chat` |
| Качество | ruff (lint + format), pytest, pre-commit |
| Запуск | Docker Compose (app + db) за nginx на хосте, HTTPS от Let's Encrypt |
| CI/CD | GitHub Actions: проверки на каждый push и PR, автодеплой из `main` |

## Окружение разработчика (Windows)

- ОС Windows 11. Есть **Git Bash** и PowerShell. Все `.sh`-скрипты запускаются из Git Bash.
- **uv** 0.9 стоит глобально. Python не нужно ставить отдельно: uv сам берёт 3.12 (`.python-version`). Команды `python` в PATH **нет**, только `uv run python`.
- Docker Desktop, Node 24, GitHub CLI `gh` (авторизован).
- SSH: алиас сервера `LCT` в `~/.ssh/config`, GitHub по ключу.
- Путь проекта содержит кириллицу и пробелы — всегда берите пути в кавычки. Из-за этого в `compose.yaml` явно задано `name: seller-assistant`.
- Локальная БД — `127.0.0.1`, не `localhost` (на Windows `localhost` уходит в IPv6 и подключение виснет).

## Команды

```bash
uv sync                                   # установить зависимости (создаёт .venv)
cp .env.example .env                      # и вписать DEEPSEEK_API_KEY
docker compose up -d db                   # локальный Postgres на localhost:5432
uv run alembic upgrade head               # применить миграции
uv run uvicorn seller_assistant.main:app --reload   # http://127.0.0.1:8000, API-доки: /api/docs

uv run ruff check --fix . && uv run ruff format .   # линт + формат
uv run pytest                             # тесты
uv run pre-commit install                 # один раз: проверки перед каждым коммитом

uv add <пакет>          # зависимость (uv add --dev <пакет> — для разработки)
uv run alembic revision --autogenerate -m "что изменилось"   # новая миграция
```

## Структура

```
src/seller_assistant/
  main.py          приложение FastAPI, подключение роутеров и шаблонов
  config.py        настройки из .env (pydantic-settings). Новые переменные — сюда и в .env.example
  db.py            engine, сессии, Base для моделей
  models/          ORM-модели. Каждую новую импортировать в models/__init__.py
  api/             health.py, pages.py (HTML-страницы и HTMX-фрагменты)
  services/        analytics.py (KPI, правила, причины), shop.py (работа с БД), ai.py (LLM), demo_data.py
  llm/client.py    единственная точка обращения к DeepSeek
  web/templates/   Jinja2-шаблоны (base.html + страницы)
  web/static/      CSS/JS/картинки
migrations/        Alembic
tests/             pytest
deploy/            скрипты деплоя (см. ниже)
docs/              требования, решения, материалы курса
```

## Правила для кода

- **Слои:** роутер (`api/`) только принимает запрос и отдаёт ответ → логика в `services/` → БД через модели, LLM через `llm/client.py`. Не вызывать DeepSeek напрямую из роутеров.
- **Промпты** держать рядом с сервисом, который их использует, константами или `.md`-файлами, не размазывать по коду.
- **Секреты** только в `.env`. Никогда не коммитить ключи, не печатать их в логи. `DEEPSEEK_API_KEY` — `SecretStr`.
- **Схема БД** меняется только миграцией Alembic. Не править старые миграции, которые уже на сервере.
- **Тесты не ходят в DeepSeek** и в API маркетплейсов: подменяйте клиент (пример в `tests/test_llm.py`).
- Тексты интерфейса и комментарии на русском, идентификаторы на английском.
- Небольшие изменения, после каждого: `ruff` + `pytest`. Новая фича — хотя бы один тест на основной сценарий.
- Не добавлять зависимости и фреймворки без нужды. Фронт без сборщиков, пока хватает HTMX.

## Git и CI/CD

- Репозиторий: `git@github.com:IIshikiII/AI-assistant-for-marketplace-sellers.git` (публичный).
- **Каждый push в `main` автоматически выкатывается на прод** после зелёных проверок. Крупное делайте в ветке и через PR.
- Workflow: `.github/workflows/ci.yml` (job `check`: ruff + pytest; job `deploy`: `deploy/deploy.sh`).
- Секреты GitHub: `DEPLOY_SSH_KEY` (отдельный ключ CI, его публичная часть в `~/.ssh/authorized_keys` на сервере, комментарий `github-actions-deploy seller-assistant`), `DEPLOY_KNOWN_HOSTS`.

## Сервер и деплой

- **Прод:** https://utility-monitor.ru (IP 176.123.165.194), SSH: `ssh LCT` (пользователь `user1`, sudo без пароля, в группе docker).
- Ubuntu 22.04, 2 CPU, 4 ГБ RAM, 30 ГБ диска. Docker + Compose v2, nginx 1.18, certbot (сертификат продлевается сам через `certbot.timer`).
- На сервере **только наше приложение**, прежнее (arm-ods) удалено.

Схема:

```
Интернет → nginx :443 (TLS, /etc/nginx/sites-available/seller-assistant.conf)
         → 127.0.0.1:8000 контейнер app → контейнер db (Postgres, том seller-assistant_db-data)

/opt/seller-assistant/
  releases/<дата>-<sha>/   код каждого релиза (хранятся 5 последних)
  current -> releases/…    активный релиз
  shared/.env              секреты прода (chmod 600), подключается в каждый релиз
```

Скрипты (запускать из корня репозитория в Git Bash):

| Скрипт | Что делает |
|---|---|
| `deploy/deploy.sh` | Выкатить текущее состояние репозитория (включая незакоммиченное — релиз помечается `-dirty`). Архив по SSH → `docker compose up --build` → ждёт `/readyz` → при неудаче **сам откатывается** на предыдущий релиз |
| `deploy/rollback.sh [релиз]` | Откат на предыдущий или указанный релиз |
| `deploy/status.sh` | Текущий релиз, список релизов, контейнеры, `/readyz`, место на диске |
| `deploy/logs.sh [-f] [app\|db] [N]` | Логи контейнеров |
| `deploy/env.sh list\|push KEY\|set KEY=VAL` | Переменные прода. `push DEEPSEEK_API_KEY` берёт значение из локального `.env`. После изменения app перезапускается |
| `deploy/server-setup.sh` | Разовая подготовка сервера: каталоги, `shared/.env` со случайным паролем БД, конфиг nginx. Повторный запуск безопасен |

Важно:
- Миграции применяются **автоматически** при старте контейнера (`alembic upgrade head` в `CMD` Dockerfile).
- Health-checks: `/healthz` — процесс жив; `/readyz` — есть связь с БД (по нему ориентируется деплой).
- Конфиг nginx меняется в `deploy/nginx/seller-assistant.conf`, затем `deploy/server-setup.sh`. На сервере руками не править.
- Новая переменная окружения: добавить в `config.py`, `.env.example`, на прод — `deploy/env.sh set ...`.
- Хост для скриптов задаётся `DEPLOY_HOST` (по умолчанию `LCT`; в CI `user1@176.123.165.194`).
