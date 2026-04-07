"""
src/api/main.py
---------------
Session 15 — Phase 4: FastAPI application entry-point

Start the development server with:
    uvicorn api.main:app --reload --port 8000

Or from the project root:
    python -m uvicorn api.main:app --reload --port 8000

Architecture:
  • One ``RunManager`` instance per process, stored on ``app.state``
  • All routes imported from ``api.routes.runs``
  • API key auth middleware (optional — enable by setting API_KEY env var)
  • CORS open by default for development; tighten in production via ALLOWED_ORIGINS
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from research_pipeline.config.loader import load_pipeline_config
from research_pipeline.config.settings import Settings
from api.routes.runs import router as runs_router, saved_router
from api.routes.market import router as market_router
from api.services.run_manager import RunManager

logger = logging.getLogger(__name__)


def _load_env_file() -> None:
    """Populate process environment from project-root .env if present.

    Existing environment variables win over .env values.
    """
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if not key or key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


_load_env_file()


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise shared resources on startup; clean up on shutdown."""
    # Build settings from environment
    storage_dir = Path(os.getenv("STORAGE_DIR", "storage"))
    prompts_dir = Path(os.getenv("PROMPTS_DIR", "prompts"))
    settings = Settings(
        storage_dir=storage_dir,
        prompts_dir=prompts_dir,
        llm_model=os.getenv("LLM_MODEL", "claude-sonnet-4-6"),
    )
    config = load_pipeline_config(config_path=os.getenv("PIPELINE_CONFIG_PATH") or None)
    app.state.run_manager = RunManager(settings=settings, config=config)
    logger.info("RunManager initialised — storage=%s", storage_dir)

    yield  # application runs

    # Shutdown: cancel any active background runs
    for run in app.state.run_manager.list_runs():
        app.state.run_manager.cancel_run(run["run_id"])
    logger.info("API shutdown — all runs cancelled")


# ── Application factory ───────────────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Infrastructure Research Platform API",
        version="1.0.0",
        description=(
            "FastAPI event-streaming API for the 15-stage financial research pipeline. "
            "Start runs, stream live stage events via SSE, retrieve reports and artifacts."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ────────────────────────────────────────────────────────────
    allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
    allowed_origins = (
        [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
        if allowed_origins_env
        else [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8501",
            "http://127.0.0.1:8501",
        ]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Optional API-key auth middleware ─────────────────────────────────
    api_key = os.getenv("API_KEY", "")
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env in {"prod", "production"} and not api_key:
        logger.warning("APP_ENV=%s but API_KEY is not set; API routes are unauthenticated", app_env)
    if api_key:

        @app.middleware("http")
        async def _check_api_key(request: Request, call_next):
            # Health check is always public
            if request.url.path in ("/health", "/", "/docs", "/redoc", "/openapi.json"):
                return await call_next(request)
            key = request.headers.get("X-API-Key", "")
            if key != api_key:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or missing API key"},
                )
            return await call_next(request)

    # ── Routes ───────────────────────────────────────────────────────────
    app.include_router(runs_router, prefix="/api/v1")
    app.include_router(saved_router, prefix="/api/v1")
    app.include_router(market_router, prefix="/api/v1")

    # ── Health / root ─────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, Any]:
        return {"name": "AI Research Pipeline API", "version": "1.0.0", "docs": "/docs"}

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, Any]:
        return {"status": "ok"}

    return app


# Module-level ``app`` instance used by uvicorn and tests
app = create_app()
