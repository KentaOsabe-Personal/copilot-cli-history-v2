from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse

ALLOWED_METHODS = "GET, POST, OPTIONS"
ALLOWED_HEADERS = "Content-Type, Authorization"


def apply_cors_headers(response: HttpResponse, *, origin: str | None) -> HttpResponse:
    if origin is None or origin not in _allowed_origins():
        return response

    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = _vary_header(response.headers.get("Vary"))
    return response


def preflight_response(*, origin: str | None) -> HttpResponse:
    response = HttpResponse(status=204)
    apply_cors_headers(response, origin=origin)
    if origin is not None and origin in _allowed_origins():
        response.headers["Access-Control-Allow-Methods"] = ALLOWED_METHODS
        response.headers["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
        response.headers["Access-Control-Max-Age"] = "600"
    return response


def _allowed_origins() -> tuple[str, ...]:
    return tuple(getattr(settings, "HISTORY_API_ALLOWED_ORIGINS", ()))


def _vary_header(current: str | None) -> str:
    if current is None or current == "":
        return "Origin"
    values = [value.strip() for value in current.split(",")]
    if "Origin" in values:
        return current
    return f"{current}, Origin"


__all__ = ["apply_cors_headers", "preflight_response"]
