import logging
from pathlib import Path
import sys

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Allow the task acceptance command `cd backend && uvicorn main:app --reload`
# while keeping package imports stable for tests run from the repository root.
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.core.config import get_settings
from backend.routers.jd import router as jd_router


logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Extract structured skills from recruitment JD text.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jd_router, prefix=settings.api_prefix)


@app.get("/api/health", tags=["Health"])
async def health_check() -> dict[str, object]:
    return {"code": 0, "data": {"status": "ok"}, "message": "OK"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"code": 422, "data": {"errors": exc.errors()}, "message": "Validation failed"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"code": 500, "data": None, "message": "Internal server error"},
    )
