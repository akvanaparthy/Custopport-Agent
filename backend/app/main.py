"""FastAPI app factory. On startup it initializes the domain + trace/settings
schema and idempotently seeds the demo data, so the app runs out of the box.
The chat/session routes are added in a later step; this wires health + the
admin/observability router."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db.database import connect, init_db
from .db.seed import ensure_seeded
from .observability.admin_router import router as admin_router
from .observability.db import init_observability


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    conn = connect(settings.db_path)
    try:
        init_db(conn)             # domain tables (customers/orders/refunds)
        init_observability(conn)  # runs/steps/settings
        ensure_seeded(conn, datetime.now(timezone.utc))
    finally:
        conn.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AI Refund Support Agent", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(admin_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
