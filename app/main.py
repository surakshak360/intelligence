"""
FastAPI app factory for surakshak360-intelligence.

Wires together: structured logging + request-ID middleware (GROUND_RULES
15.1), the standard error envelope (core/exceptions.py), CORS, static
serving of generated evidence files, and the API router.
"""
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger, request_id_ctx

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "service_startup",
        extra={"extra_fields": {"model_version": settings.MODEL_VERSION, "env": settings.ENV}},
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="surakshak360-intelligence",
        description="Intelligence Fusion service — graph analytics, hotspots, case linking, evidence generation, recommendations.",
        version=settings.MODEL_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        token = request_id_ctx.set(incoming)
        request.state.request_id = incoming
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = incoming
        return response

    register_exception_handlers(app)
    app.include_router(api_router)

    os.makedirs(settings.EVIDENCE_STORAGE_DIR, exist_ok=True)
    app.mount(
        "/evidence-files",
        StaticFiles(directory=settings.EVIDENCE_STORAGE_DIR),
        name="evidence-files",
    )

    return app


app = create_app()
