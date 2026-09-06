# 04 — Deliver secrets from the local machine to the server

Use when updating production `.env` or individual secrets (tokens, passwords, Notion, Telegram). **Never** put secrets in chat, commits, `AGENTS.md`, PRs, or agent replies.

## Sources (prefer in order)

1. Local gitignored repo `.env` (agent reads from disk; does not print values)
2. One-shot file outside the repo, e.g. `~/.config/pomogator/secrets.env` (mode `600`); delete after use if the user wants
3. User says a path to a secret file — use that path

Do **not** ask the user to paste tokens into the chat.

## Transport

- Allowed: `scp` / `sftp` of **only** `.env` or a small patch file of keys (not the app tree)
- Forbidden: committing `.env`, echoing secret values, logging full env dumps

## Patch flow (preferred)

1. Build a temporary patch on the local machine from local `.env` (or the provided secrets file), containing only the keys to update.
2. `scp` the patch to the server (e.g. `/tmp/pomogator.env.patch`), mode `600`.
3. On the server, merge into `/root/pomogator/.env` by key (replace existing keys; append missing). Keep `chmod 600`.
4. Verify without printing secrets: key presence, lengths, non-secret flags like `SOCKS_ENABLED=false`, `APP_DOMAIN=…`.
5. Delete local and remote temp patch files (`rm` / `shred` when available).

## Full `.env` replace (bootstrap / rare)

```bash
scp -o BatchMode=yes /path/to/local.env root@134.209.253.10:/root/pomogator/.env
ssh -o BatchMode=yes root@134.209.253.10 'chmod 600 /root/pomogator/.env'
```

Ensure production overrides are set when building from local: `APP_ENV=production`, `APP_DOMAIN=ggarpomogator.ru`, `TELEGRAM_WEBAPP_URL=https://ggarpomogator.ru`, `REDIS_URL=redis://redis:6379/0`, `SOCKS_ENABLED=false` (foreign VPS), stub payments flag as required.

## After secrets change

Always continue with [03-redeploy.md](03-redeploy.md) `--force-recreate` for services that load the changed keys. Editing `.env` alone does not reload running containers.

## Done when

- Server `.env` has the intended keys (verified without dumping values)
- Temp secret files removed
- Redeploy scheduled or completed so processes see the new env
