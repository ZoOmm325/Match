import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Support `cd backend && uvicorn main:app --reload` while preserving package imports.
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.core.config import Settings, get_settings
from backend.core.exceptions import install_exception_handlers
from backend.core.middleware import RequestLoggingMiddleware
from backend.routers.jd import router as jd_router
from backend.routers.major import router as major_router
from backend.routers.match import router as match_router
from backend.routers.skill import router as skill_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from backend.core.deepseek_client import close_deepseek_client

    await close_deepseek_client()


def create_app(settings: Settings | None = None) -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("backend.core.middleware").setLevel(logging.INFO)
    app_settings = settings or get_settings()
    app = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        description="Extract structured skills from recruitment JD text.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    install_exception_handlers(app)

    app.include_router(jd_router, prefix=app_settings.api_prefix)
    app.include_router(major_router, prefix=app_settings.api_prefix)
    app.include_router(match_router, prefix=app_settings.api_prefix)
    app.include_router(skill_router, prefix=app_settings.api_prefix)

    @app.get(f"{app_settings.api_prefix}/health", tags=["Health"])
    async def health_check() -> dict[str, object]:
        return {"code": 0, "data": {"status": "ok"}, "message": "OK"}

    return app


app = create_app()
