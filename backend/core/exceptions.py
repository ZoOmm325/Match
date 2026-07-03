from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise exc
    detail = exc.detail
    message = detail if isinstance(detail, str) else "Request failed"
    data: Any = None if isinstance(detail, str) else detail
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={"code": exc.status_code, "data": jsonable_encoder(data), "message": message},
    )


async def request_validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    return _validation_response(exc.errors())


async def pydantic_validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, ValidationError):
        raise exc
    return _validation_response(exc.errors())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception method=%s path=%s request_id=%s",
        request.method,
        request.url.path,
        getattr(request.state, "request_id", None),
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"code": 500, "data": None, "message": "Internal server error"},
    )


def _validation_response(errors: Sequence[Any]) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "data": {"errors": jsonable_encoder(errors)},
            "message": "Validation failed",
        },
    )
