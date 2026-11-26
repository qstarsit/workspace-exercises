from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from fare_watch.domain import (
    NoFaresObservedError,
    RouteNotFoundError,
    UpstreamError,
    UpstreamTimeoutError,
)

STATUS_CODE_BY_ERROR: dict[type[Exception], int] = {
    RouteNotFoundError: status.HTTP_404_NOT_FOUND,
    NoFaresObservedError: status.HTTP_404_NOT_FOUND,
    UpstreamError: status.HTTP_502_BAD_GATEWAY,
    UpstreamTimeoutError: status.HTTP_504_GATEWAY_TIMEOUT,
}


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Translate a domain exception into a JSON error response.

    Args:
        request: The request that raised the exception.
        exc: The domain exception; its type must be in ``STATUS_CODE_BY_ERROR``.

    Returns:
        A response with the mapped status code and ``{"detail": <message>}``.
    """
    return JSONResponse(
        status_code=STATUS_CODE_BY_ERROR[type(exc)], content={"detail": str(exc)}
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register ``domain_error_handler`` for every mapped domain exception.

    Args:
        app: The application to configure.
    """
    for error_type in STATUS_CODE_BY_ERROR:
        app.add_exception_handler(error_type, domain_error_handler)
