"""HTTP handlers for user domain exceptions."""

from fastapi import Request
from fastapi.responses import JSONResponse

from .types import CannotDeleteSelfError, UserError, UserNotFoundError
from app.exceptions import error_detail


def _json_response(status_code: int, detail: dict) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


async def user_error_handler(_request: Request, exc: UserError) -> JSONResponse:
    """Generic handler for all UserError subclasses. Metadata lives on the exception."""
    detail = error_detail(exc.error_code, exc.get_http_message(), **exc.get_extra_detail())
    return _json_response(exc.status_code, detail)


def register_user_exception_handlers(app) -> None:
    """Register all user domain exception handlers on the FastAPI app."""
    for exc_cls in (CannotDeleteSelfError, UserNotFoundError):
        app.add_exception_handler(exc_cls, user_error_handler)
