"""Reweave API entry point: wires every domain's router into one FastAPI app."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .admin.router import router as admin_router
from .assistant.router import router as assistant_router
from .auth.router import router as auth_router
from .core.config import get_settings, load_env_files
from .core.database import database
from .core.frontend import mount_frontend
from .destinations.router import router as destinations_router
from .marketplace.router import router as marketplace_router
from .scanning.router import router as scanning_router
from .seed import seed_data

load_env_files()
logger = logging.getLogger("reweave")

ROUTERS = [
    scanning_router,  # 1. photo -> sorted bins (and listed lots, for the station)
    destinations_router,  # 2. where each bin should go
    marketplace_router,  # 3. lots are listed, browsed and claimed
    admin_router,  # 4. operations dashboard
    auth_router,
    assistant_router,
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.uses_default_secret:
        logger.warning("SECRET_KEY is not set; using the built-in development key. Set it before deploying.")
    # Importing the routers above registered every domain's models on Base.
    database.create_schema()
    if settings.seed_demo_data:
        with database.session() as db:
            seed_data(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Reweave API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in ROUTERS:
        app.include_router(router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    # Registered last so its catch-all route never shadows an API route.
    if settings.frontend_dist_dir:
        mount_frontend(app, settings.frontend_dist_dir)

    return app


app = create_app()
