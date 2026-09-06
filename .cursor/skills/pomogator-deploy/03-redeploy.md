# 03 — Redeploy the server

Use after [02-update-server.md](02-update-server.md) and/or after [04-deliver-secrets.md](04-deliver-secrets.md). Containers only pick up a new `.env` after recreate.

## Choose scope

| Change | Services |
|--------|----------|
| Bot / polling / SOCKS | `bot` |
| API / auth / routes | `api` (+ `worker` if needed) |
| Notion sync / Celery | `worker` `scheduler` |
| Mini App UI | `frontend` (+ `caddy` if proxy changed) |
| `.env` / secrets | `--force-recreate` for services that read those keys (often all app services) |
| Unsure / «передеплой всё» | full stack |

## Commands

Targeted:

```bash
ssh -o BatchMode=yes root@134.209.253.10 \
  'cd /root/pomogator && docker compose up -d --build <services>'
```

Full rebuild + recreate (env refresh):

```bash
ssh -o BatchMode=yes root@134.209.253.10 \
  'cd /root/pomogator && docker compose up -d --build --force-recreate'
```

Migrations (after schema changes or full redeploy):

```bash
ssh -o BatchMode=yes root@134.209.253.10 \
  'cd /root/pomogator && docker compose exec -T api alembic upgrade head'
```

## Verify

```bash
ssh -o BatchMode=yes root@134.209.253.10 \
  'cd /root/pomogator && docker compose ps && docker compose logs --no-color --tail=80 bot api caddy'
curl -fsS https://ggarpomogator.ru/health
curl -fsS https://ggarpomogator.ru/ready
```

Expect bot log: SOCKS disabled / long polling via **direct** on the foreign VPS (unless `SOCKS_ENABLED=true` was intentionally set).

## Done when

- Intended services are Up; `api` healthy when included
- `/health` and `/ready` succeed on the public domain
- No Telegram `Conflict` from a second bot process on the same token
