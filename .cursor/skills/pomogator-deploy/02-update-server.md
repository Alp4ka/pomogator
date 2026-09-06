# 02 — Update code on the server

Use after code was pushed (see [01-deliver-code.md](01-deliver-code.md)).

## Steps

```bash
ssh root@134.209.253.10
cd /root/pomogator
git fetch origin
git pull --ff-only origin main
git log -1 --oneline
```

Non-interactive agent form:

```bash
ssh -o BatchMode=yes root@134.209.253.10 \
  'cd /root/pomogator && git fetch origin && git pull --ff-only origin main && git log -1 --oneline'
```

## Rules

- Fast-forward only (`--ff-only`). If pull fails, stop and report; do not force-reset unless the user explicitly asks.
- Do not edit application files on the server by hand.
- Do not “also” rsync local sources “just in case”.

## Done when

- Server `HEAD` matches the intended commit from `origin/main`
