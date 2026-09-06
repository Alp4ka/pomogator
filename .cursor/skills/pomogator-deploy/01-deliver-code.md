# 01 — Deliver updated code from the local machine

Use when shipping application source to production.

## Steps

1. Ensure working tree is what the user wants to ship.
2. Run checks appropriate to the change:
   - Python: `uv run ruff check`, `uv run mypy backend/src`, `uv run pytest`
   - Frontend: lint/typecheck if UI changed
3. **Commit only if the user asked** (or explicitly asked to deploy and there is no commit yet — then ask before committing).
4. Push to GitHub:

```bash
git push origin HEAD
```

Prefer pushing `main` for production. Do not force-push `main`.

## Forbidden

- `rsync` / `scp` / manual copy of the app tree to the server
- Pushing secrets, `.env`, or credential files
- `--no-verify` / skipping hooks unless the user explicitly requests it

## Done when

- Remote `origin/main` (or the agreed branch) contains the commit to run on the server
- Local branch is not secretly ahead with unpushed deploy commits the user did not request
