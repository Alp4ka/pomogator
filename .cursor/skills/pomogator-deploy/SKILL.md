---
name: pomogator-deploy
description: >-
  Delivers Pomogator code and secrets to production VPS and redeploys Docker
  Compose services. Use when the user asks to deploy, redeploy, ship, push to
  server, update production, sync .env/secrets, or bootstrap/update the
  production host (DESTINATION_ADDRESS) / pomogator.me.
---

# Pomogator production delivery

Read and follow the matching instruction file. Do not improvise alternate
transport (no rsync/scp of app source).

| Task | Instruction |
|------|-------------|
| Ship code from local machine | [01-deliver-code.md](01-deliver-code.md) |
| Update code on the server | [02-update-server.md](02-update-server.md) |
| Redeploy / recreate services | [03-redeploy.md](03-redeploy.md) |
| Deliver secrets / `.env` | [04-deliver-secrets.md](04-deliver-secrets.md) |

## Resolve the production host

Do this from the repo root **before any** `ssh` or `scp`. Never hardcode an IP.

1. Use `DESTINATION_ADDRESS` from the process environment when it is set.
2. Otherwise read the `DESTINATION_ADDRESS=` line from the repo `.env` (gitignored). Do not print other keys.
3. If both are empty, stop and tell the user to set `DESTINATION_ADDRESS`.

```bash
if [ -z "${DESTINATION_ADDRESS:-}" ]; then
  DESTINATION_ADDRESS="$(
    grep -E '^[[:space:]]*DESTINATION_ADDRESS=' .env \
      | head -n 1 \
      | cut -d= -f2- \
      | tr -d '"' \
      | tr -d "'" \
      | tr -d '[:space:]'
  )"
fi
if [ -z "${DESTINATION_ADDRESS:-}" ]; then
  echo "DESTINATION_ADDRESS is missing from the environment and from .env" >&2
  exit 1
fi
```

SSH user is `root`. Commands in the instruction files use `root@${DESTINATION_ADDRESS}`.

## Host constants

| Item | Value |
|------|-------|
| SSH | `root@${DESTINATION_ADDRESS}` |
| App dir | `/root/pomogator` |
| Domain | `https://pomogator.me` |
| Branch | `main` |
| Remote | `origin` → GitHub `Alp4ka/pomogator` |

## Default full ship (code + run)

When the user says «задеплой» / «передеплой» without narrowing scope:

1. [01-deliver-code.md](01-deliver-code.md) (commit only if user asked or deploy implies it — ask if no commit)
2. [02-update-server.md](02-update-server.md)
3. [03-redeploy.md](03-redeploy.md) for affected services (full stack if unsure or after `.env` change)
4. [04-deliver-secrets.md](04-deliver-secrets.md) only if secrets changed

## Hard rules

- App code travels **only** via git push → server git pull.
- Secrets travel **only** via [04-deliver-secrets.md](04-deliver-secrets.md); never commit `.env`, never paste tokens/passwords into chat.
- Do not quote secret values in replies or logs.
- Do not run local `bot` and server `bot` on the same `TELEGRAM_BOT_TOKEN`.
- Prefer SSH key auth; never put root password in chat/commits.
