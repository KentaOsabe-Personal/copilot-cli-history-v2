from __future__ import annotations

from collections.abc import Mapping

from django.http import JsonResponse

from history_api.query_validation import QueryValidationError
from history_api.services import ApiServiceResult
from history_read_model.repository import RepositoryError

SERVICE_UNAVAILABLE_ERROR_KINDS = {"credentials_error", "permission_denied", "schema_mismatch"}


def success_response(
    data: object,
    *,
    meta: Mapping[str, object] | None = None,
    status: int = 200,
) -> JsonResponse:
    body: dict[str, object] = {"data": data}
    if meta is not None:
        body["meta"] = dict(meta)
    return JsonResponse(body, status=status)


def error_response(
    code: str,
    message: str,
    *,
    status: int,
    details: Mapping[str, object] | QueryValidationError | None = None,
) -> JsonResponse:
    return JsonResponse(
        {
            "error": {
                "code": code,
                "message": message,
                "details": _details_payload(details),
            }
        },
        status=status,
    )


def invalid_session_list_query_response(error: QueryValidationError) -> JsonResponse:
    return error_response(
        "invalid_session_list_query",
        "session list query is invalid",
        status=400,
        details=error,
    )


def method_not_allowed_response(*, allowed: tuple[str, ...]) -> JsonResponse:
    response = error_response(
        "method_not_allowed",
        "Method not allowed.",
        status=405,
        details={"allowed_methods": allowed},
    )
    response.headers["Allow"] = ", ".join(allowed)
    return response


def not_implemented_response() -> JsonResponse:
    return error_response(
        "history_api_not_implemented",
        "History API service behavior is not implemented yet.",
        status=501,
        details={},
    )


def repository_error_response(error: RepositoryError) -> JsonResponse:
    status = 503 if error.kind in SERVICE_UNAVAILABLE_ERROR_KINDS else 500
    details: dict[str, object] = {"kind": error.kind}
    if error.details is not None:
        details.update(dict(error.details))
    return error_response(
        "history_api_failed",
        "History API request failed.",
        status=status,
        details=details,
    )


def service_result_response(result: ApiServiceResult) -> JsonResponse:
    if result.kind == "success":
        return success_response(result.data, meta=result.meta, status=result.status)
    if result.kind == "repository_error" and result.repository_error is not None:
        return repository_error_response(result.repository_error)
    if result.error is not None:
        body: dict[str, object] = {"error": _json_mapping(result.error)}
        if result.meta is not None:
            body["meta"] = _json_mapping(result.meta)
        return JsonResponse(body, status=result.status)
    return error_response(
        "history_api_failed",
        "History API request failed.",
        status=result.status,
        details={},
    )


def _details_payload(
    details: Mapping[str, object] | QueryValidationError | None,
) -> dict[str, object]:
    if details is None:
        return {}
    if isinstance(details, QueryValidationError):
        payload: dict[str, object] = {
            "field": details.field,
            "reason": details.reason,
        }
        if details.value is not None:
            payload["value"] = details.value
        return payload
    return _json_mapping(details)


def _json_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {str(key): _json_value(item) for key, item in value.items()}


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _json_mapping(value)
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


__all__ = [
    "error_response",
    "invalid_session_list_query_response",
    "method_not_allowed_response",
    "not_implemented_response",
    "repository_error_response",
    "service_result_response",
    "success_response",
]
