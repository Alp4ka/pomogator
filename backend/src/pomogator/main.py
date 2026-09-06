import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from celery import Celery
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from pomogator.config import get_settings
from pomogator.infrastructure.db.base import engine
from pomogator.presentation.api.routes import router

settings = get_settings()
redis = Redis.from_url(settings.redis_url, decode_responses=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.redis = redis
    if settings.app_env == "production" and settings.notion_token:
        Celery(broker=settings.redis_url).send_task("pomogator.sync_all")
    yield
    await redis.aclose()


app = FastAPI(
    title="Pomogator",
    lifespan=lifespan,
    docs_url=None if settings.app_env == "production" else "/docs",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.telegram_webapp_url.rstrip("/"),
        "https://web.telegram.org",
        "https://webk.telegram.org",
        "https://webz.telegram.org",
    ],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
app.include_router(router)


@app.middleware("http")
async def operational_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid4()))[:100]
    if request.url.path.startswith("/api/"):
        identity = request.headers.get(
            "Authorization", request.client.host if request.client else "-"
        )
        key = f"rate:{request.url.path}:{hash(identity)}:{int(time.time() // 60)}"
        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 70)
            if count > 120:
                return JSONResponse(
                    {"detail": "Too many requests"}, 429, headers={"X-Request-ID": request_id}
                )
        except Exception:
            pass
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/api/"):
        # Authenticated Mini App payloads must not linger in shared browser caches.
        response.headers["Cache-Control"] = "private, no-store"
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
        await redis.ping()
    except Exception as exc:
        raise HTTPException(503, "Dependencies are unavailable") from exc
    return {"status": "ready"}
