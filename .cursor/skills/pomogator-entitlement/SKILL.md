---
name: pomogator-entitlement
description: >-
  Enables, disables, or checks Pomogator country subscription (entitlement) for
  a specific Telegram user. Use when the user asks to grant/revoke paid country
  access, toggle subscription, entitle/disentitle by telegram id + country slug,
  or manage entitlements on production/local.
---

# Pomogator country entitlement

Grant or revoke **active country access** (`entitlements.active`) for one
Telegram user and one country slug.

## Required inputs

Ask if missing:

| Input | Example |
|-------|---------|
| Telegram user id | `123456789` |
| Country slug | `brazil` |
| Action | `enable` / `disable` / `status` |
| Target | `production` (default) or `local` |

Do **not** invent telegram ids or slugs.

## Production (preferred)

SSH + Docker API container. App dir `/root/pomogator`, host `root@134.209.253.10`.

```bash
ssh -o BatchMode=yes root@134.209.253.10 'cd /root/pomogator && docker compose exec -T api pomogator-entitlement --telegram-id <TG_ID> --country <slug> --enable'
```

Other actions: `--disable` or `--status`.

If `pomogator-entitlement` is missing (image not rebuilt yet), run the module:

```bash
ssh -o BatchMode=yes root@134.209.253.10 'cd /root/pomogator && docker compose exec -T api python -m pomogator.cli.entitlement --telegram-id <TG_ID> --country <slug> --enable'
```

If the module is also missing on the server, use the **fallback inline script** below (works with current models without a new deploy).

## Local

```bash
cd /Users/alp4ka/pomogator
uv run pomogator-entitlement --telegram-id <TG_ID> --country <slug> --status
```

Requires local DB/`DATABASE_URL` matching `.env`.

## Fallback inline script (no new image)

Pipe into the running `api` container (production example):

```bash
ssh -o BatchMode=yes root@134.209.253.10 'cd /root/pomogator && docker compose exec -T api python -' <<'PY'
import asyncio, sys
from sqlalchemy import select
from pomogator.infrastructure.db.base import SessionFactory
from pomogator.infrastructure.db.models import CountryModel, EntitlementModel, UserModel

TG_ID = int(sys.argv[1])
SLUG = sys.argv[2].strip().lower()
ACTION = sys.argv[3]  # enable|disable|status

async def main() -> int:
    async with SessionFactory() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == TG_ID))
        if user is None:
            print(f"error: user telegram_id={TG_ID} not found", file=sys.stderr)
            return 2
        country = await session.scalar(select(CountryModel).where(CountryModel.slug == SLUG))
        if country is None:
            print(f"error: country slug={SLUG!r} not found", file=sys.stderr)
            return 3
        row = await session.scalar(
            select(EntitlementModel).where(
                EntitlementModel.user_id == user.id,
                EntitlementModel.country_id == country.id,
            )
        )
        if ACTION == "status":
            print(f"telegram_id={TG_ID} country={country.slug} active={bool(row and row.active)}")
            return 0
        want = ACTION == "enable"
        if row is None:
            if not want:
                print(f"ok: telegram_id={TG_ID} country={country.slug} active=false")
                return 0
            session.add(EntitlementModel(user_id=user.id, country_id=country.id, active=True))
        else:
            row.active = want
        await session.commit()
        print(f"ok: telegram_id={TG_ID} country={country.slug} active={want}")
        return 0

raise SystemExit(asyncio.run(main()))
PY
```

Pass args after `-` does not work with heredoc stdin. Prefer env vars:

```bash
ssh -o BatchMode=yes root@134.209.253.10 "cd /root/pomogator && docker compose exec -T \
  -e TG_ID=<TG_ID> -e SLUG=<slug> -e ACTION=enable api python -" <<'PY'
import asyncio, os, sys
from sqlalchemy import select
from pomogator.infrastructure.db.base import SessionFactory
from pomogator.infrastructure.db.models import CountryModel, EntitlementModel, UserModel

TG_ID = int(os.environ["TG_ID"])
SLUG = os.environ["SLUG"].strip().lower()
ACTION = os.environ["ACTION"]

async def main() -> int:
    async with SessionFactory() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == TG_ID))
        if user is None:
            print(f"error: user telegram_id={TG_ID} not found", file=sys.stderr)
            return 2
        country = await session.scalar(select(CountryModel).where(CountryModel.slug == SLUG))
        if country is None:
            print(f"error: country slug={SLUG!r} not found", file=sys.stderr)
            return 3
        row = await session.scalar(
            select(EntitlementModel).where(
                EntitlementModel.user_id == user.id,
                EntitlementModel.country_id == country.id,
            )
        )
        if ACTION == "status":
            print(f"telegram_id={TG_ID} country={country.slug} active={bool(row and row.active)}")
            return 0
        want = ACTION == "enable"
        if row is None:
            if not want:
                print(f"ok: telegram_id={TG_ID} country={country.slug} active=false")
                return 0
            session.add(EntitlementModel(user_id=user.id, country_id=country.id, active=True))
        else:
            row.active = want
        await session.commit()
        print(f"ok: telegram_id={TG_ID} country={country.slug} active={want}")
        return 0

raise SystemExit(asyncio.run(main()))
PY
```

Canonical implementation in the repo: `backend/src/pomogator/cli/entitlement.py`.

## Rules

- Only change `entitlements` for the given user+country. Do not delete payment rows.
- User must already exist (`users.telegram_id`). If missing, tell the user to open the bot once.
- Confirm result with `--status` after enable/disable.
- Do not print DB passwords or `.env` secrets.
- Default target is **production** unless the user says local.

## Reply format

Short confirmation only, e.g.:

`ok: telegram_id=123 country=brazil active=true`
