# Pomogator — engineering guide

## Назначение

Pomogator — Telegram-бот и Mini App для защищённой публикации материалов о переезде.

- **Notion** — редакторский источник контента.
- **PostgreSQL** — единственный runtime-источник контента и прав доступа.
- Клиент (Mini App) **никогда** не обращается к Notion напрямую.
- Telegram-бот работает **long polling** отдельным процессом; публичный webhook не используется.

## Стек

| Часть | Технологии |
|-------|------------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2 async, Alembic, Celery, Redis |
| Bot | aiogram 3, отдельный сервис `pomogator-bot` |
| Frontend | React + TypeScript + Vite (Telegram Mini App) |
| Deploy | Docker Compose + Caddy (TLS), VPS |
| Tooling | `uv` (Python), npm (frontend), Ruff, mypy strict, pytest |

## Слои backend

```
presentation / infrastructure → application → domain
```

- `domain` — бизнес-типы и инварианты. Не импортирует FastAPI, aiogram, SQLAlchemy, внешние SDK.
- `application` — сценарии и порты (Protocol). Оркестрирует домен, транзакции и внешние интерфейсы.
- `infrastructure` — SQLAlchemy, Notion, платежи, очереди, SOCKS5-пул для Telegram. Реализует порты.
- `presentation` — HTTP API; Telegram handlers живут здесь, но запускаются отдельным long polling процессом. Только ввод → сценарий → ответ.
- `frontend` — Mini App. Сервер — единственный источник прав доступа.

Бизнес-правила не размещать в handlers, ORM-моделях или React-компонентах.

## Сервисы Docker Compose

| Сервис | Роль |
|--------|------|
| `api` | FastAPI (контент, auth, платежи, images) |
| `bot` | Telegram long polling (`pomogator-bot`) |
| `worker` / `scheduler` | Celery sync из Notion |
| `frontend` | собранный Mini App (nginx) |
| `postgres` / `redis` | данные и очередь |
| `caddy` | HTTPS, маршрутизация `/api` → api, `/` → frontend |

Caddy нужен для Mini App (публичный HTTPS), не для получения апдейтов ботом.

## Правила безопасности

- Платный контент блокируется в API; скрытие кнопки на клиенте не защита.
- Telegram `initData` всегда проверяется через HMAC и срок жизни. Telegram ID из тела запроса недоверенный.
- Секреты не коммитятся. `.env` только на машинах/сервере; в репозитории — `.env.example` с пустыми/демо значениями.
- Внешние URL из Notion остаются внешними. Только распознанные Notion page URL → внутренние маршруты.
- Изображения скачиваются при sync, валидируются по MIME/размеру, отдаются авторизованным endpoint.
- HTML из Notion не хранится и не рендерится. Новые блоки — через JSON-схему и явный React renderer.

## SOCKS5 transport (Telegram + Notion)

По умолчанию **выключено** (`SOCKS_ENABLED=false`) — для зарубежного VPS прямого доступа достаточно.

На VPS в РФ, где `api.telegram.org` / `api.notion.com` недоступны (часто HTML 403 от Cloudflare), включите `SOCKS_ENABLED=true`:

1. При старте `bot` / sync проверяется прямой доступ к API.
2. Если недоступен — скачивается SOCKS5-список из `TELEGRAM_SOCKS_PROXY_LIST_URL`.
3. Выбирается случайный рабочий прокси; на каждый запрос не меняется — только при init/сбоях.
4. MTProto (`t.me/proxy?...`) не подходит — только SOCKS5/HTTP.

Код: `infrastructure/telegram/socks_pool.py`; оркестрация в `polling.py` и `worker.py`.

## Стиль и дополнение кода

- Python: зависимости и команды только через `uv`; type hints, async I/O, Ruff, mypy strict; функции с одним уровнем ответственности. Публичные контракты тестируются.
- TypeScript: strict mode, без `any`, доступ к API через типизированный слой. UI: loading / error / empty / locked + тема Telegram.
- Новая интеграция: Protocol в application/domain + адаптер в infrastructure.
- Новая таблица / изменение столбца → новая Alembic-миграция; уже применённые миграции не редактировать.
- Sync и платёжные callbacks — идемпотентные. Любое изменение доступа — серверный тест.
- Тесты: unit (домен), integration (БД/API), contract fixtures (Notion), E2E (ключевой путь).

Локально:

```bash
uv sync --frozen
make lint && make test
```

## Деплой на VPS (обязательный способ)

**Единственный способ доставки кода на сервер: git push локально → git pull на сервере.**

Не использовать `rsync`, `scp` дерева исходников или ручное копирование файлов приложения. Исключение — одноразовые операции вне репозитория (например, правка серверного `.env`), и то осознанно.

### Production host

| Параметр | Значение |
|----------|----------|
| SSH | `root@134.209.253.10` |
| Каталог приложения | `/root/pomogator` (или `~/pomogator` под root) |
| Домен Mini App | `ggarpomogator.ru` (DNS A → этот IP) |
| Auth | предпочтительно SSH-ключ; пароль root — только вне git/чата (см. ниже) |

Старый хост `user1@45.151.30.135` больше не используется.

### Как передавать секреты агенту (не в чат)

Секреты **нельзя** писать в сообщение чата: они попадают в историю диалога / transcript и потом снова доступны модели.

Правильный порядок:

1. **SSH:** настроить ключ (`ssh-copy-id root@134.209.253.10`) или `~/.ssh/config` + `IdentityFile`. Агент ходит по ключу без пароля в промпте.
2. **`.env`:** держать локально и на сервере в gitignored файлах. Агент читает с диска по необходимости и **не** цитирует значения в ответах.
3. **Одноразово:** положить секрет в локальный файл вне репо, например `~/.config/pomogator/secrets.env` (права `600`), сказать агенту путь. После использования файл можно удалить.
4. **Не делать:** пароль/токен в чате, в `AGENTS.md`, в коммитах, в issue/PR.

Идеал: агент вообще не видит root-пароль — только key-based SSH.

### Репозиторий

- Remote: `origin` → GitHub (`Alp4ka/pomogator`).
- Рабочая ветка для продакшена: `main` (пока нет release-ветки).
- На сервере: клон в `/root/pomogator`, доступ `root@134.209.253.10`.

### Локально (агент / разработчик)

1. Внести изменения в рабочей копии.
2. Прогнать проверки: `uv run ruff check`, `mypy`, `pytest` (и frontend lint при изменениях UI).
3. Закоммитить **только по явной просьбе пользователя**.
4. Запушить:

```bash
git push origin HEAD
```

5. На сервере обновить и пересобрать затронутые сервисы (см. ниже). Не «дозаливать» код параллельно rsync.

### На сервере

```bash
ssh root@134.209.253.10
cd /root/pomogator
git fetch origin
git pull --ff-only origin main
docker compose up -d --build <сервисы>
```

Типичные наборы:

- правки бота / polling / SOCKS → `bot`
- API / auth / routes → `api` (+ при необходимости `worker`)
- frontend Mini App → `frontend` (и при смене проксирования — `caddy`)
- миграции схемы → после `pull`:  
  `docker compose exec api alembic upgrade head`
- полная пересборка при сомнениях →  
  `docker compose up -d --build`

Проверки после деплоя:

```bash
docker compose ps
docker compose logs --tail=80 bot api caddy
curl -fsS https://ggarpomogator.ru/health
curl -fsS https://ggarpomogator.ru/ready
```

### Правила для агента Cursor

- Обновления на VPS делать **только** через git push + ssh `git pull` (+ `docker compose`), не через rsync/scp кода.
- Перед push убедиться, что коммит существует и пользователь его запросил (или явно попросил «задеплоить», подразумевая commit+push — тогда уточнить, если коммита ещё нет).
- Секреты (`.env`, токены, root-пароль) через git и чат **не** тащить; править `.env` на сервере отдельно; SSH — ключом.
- Одновременно не держать локальный `bot` и серверный `bot` на одном `TELEGRAM_BOT_TOKEN` — будет `Conflict`.
- Если SSH не отвечает (banner timeout) — не долбить rsync; сообщить пользователю про reboot VPS / OOM.

### Первичный bootstrap сервера (редко)

Один раз: Docker, клон репо в `/root/pomogator`, `.env` из `.env.example`, DNS `ggarpomogator.ru` → `134.209.253.10`, `docker compose up --build -d`, миграции, URL Mini App в BotFather. Дальнейшие обновления — только git pull.

## Конфигурация

См. `.env.example`. Важное для production:

- `APP_ENV=production`
- `APP_DOMAIN` / `TELEGRAM_WEBAPP_URL=https://…` (реальный домен, не example.com)
- `TELEGRAM_BOT_TOKEN`, `NOTION_TOKEN`, `NOTION_COUNTRIES`
- `ALLOW_STUB_PAYMENTS_IN_PRODUCTION=true` пока платежи — stub
- `TELEGRAM_SOCKS_PROXY_LIST_URL` — список SOCKS5 для failover бота

## Observability

- `/health` — процесс жив; `/ready` — PostgreSQL + Redis.
- Ответы API несут `X-Request-ID`; rate limit через Redis.
- Логи контейнеров: `sudo docker compose logs -f <service>`.
