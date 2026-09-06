FROM ghcr.io/astral-sh/uv:0.8.22 AS uv
FROM python:3.13-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock alembic.ini ./
COPY backend ./backend
RUN uv sync --frozen --no-dev

RUN useradd -r -u 10001 app && chown -R app:app /app
USER app

CMD ["uvicorn", "pomogator.main:app", "--host", "0.0.0.0", "--port", "8000"]
