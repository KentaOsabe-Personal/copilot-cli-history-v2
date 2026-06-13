from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from history_api.cors import apply_cors_headers, preflight_response
from history_api.dependencies import get_clock, get_reader, get_repository
from history_api.query_validation import parse_include_raw, validate_session_list_query
from history_api.responses import (
    invalid_session_list_query_response,
    method_not_allowed_response,
    service_result_response,
)
from history_api.services import HistoryApiService


def session_list(request: HttpRequest) -> HttpResponse:
    if request.method == "OPTIONS":
        return preflight_response(origin=request.headers.get("Origin"))
    if request.method != "GET":
        return _with_cors(
            method_not_allowed_response(allowed=("GET", "OPTIONS")),
            request=request,
        )

    validation = validate_session_list_query(request.GET)
    if isinstance(validation, Exception):
        return _with_cors(invalid_session_list_query_response(validation), request=request)
    service = _service()
    return _with_cors(
        service_result_response(service.list_sessions(validation.criteria)),
        request=request,
    )


def session_detail(request: HttpRequest, session_id: str) -> HttpResponse:
    if request.method == "OPTIONS":
        return preflight_response(origin=request.headers.get("Origin"))
    if request.method != "GET":
        return _with_cors(
            method_not_allowed_response(allowed=("GET", "OPTIONS")),
            request=request,
        )

    service = _service()
    return _with_cors(
        service_result_response(
            service.get_session_detail(
                session_id,
                include_raw=parse_include_raw(request.GET),
            )
        ),
        request=request,
    )


def history_sync(request: HttpRequest) -> HttpResponse:
    if request.method == "OPTIONS":
        return preflight_response(origin=request.headers.get("Origin"))
    if request.method != "POST":
        return _with_cors(
            method_not_allowed_response(allowed=("POST", "OPTIONS")),
            request=request,
        )

    service = _service(include_reader=True)
    return _with_cors(service_result_response(service.sync_history()), request=request)


def _with_cors(response: HttpResponse, *, request: HttpRequest) -> HttpResponse:
    return apply_cors_headers(response, origin=request.headers.get("Origin"))


def _service(*, include_reader: bool = False) -> HistoryApiService:
    return HistoryApiService(
        repository=get_repository(),
        reader=get_reader() if include_reader else None,
        clock=get_clock(),
    )


__all__ = ["history_sync", "session_detail", "session_list"]
