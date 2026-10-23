# Ассистент продавца

ИИ-ассистент для продавцов на маркетплейсах. Учебный проект курса «Практика создания продуктов ИИ», МГИМО, 2026.

**Прод:** https://utility-monitor.ru

## Быстрый старт

Нужны [uv](https://docs.astral.sh/uv/) и Docker.

```bash
uv sync
cp .env.example .env          # вписать DEEPSEEK_API_KEY
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn seller_assistant.main:app --reload
```

Откройте http://127.0.0.1:8000.

## Документы

- [CLAUDE.md](CLAUDE.md) — стек, команды, правила кода, деплой. Главный документ для разработчиков и ИИ-ассистентов.
- [docs/requirements.md](docs/requirements.md) — требования к продукту.
- [docs/decisions.md](docs/decisions.md) — принятые решения и причины.
- [docs/economics.md](docs/economics.md) — экономика, чувствительность и план пилота.
- [docs/course-requirements.md](docs/course-requirements.md) — что нужно сдать по курсу.
