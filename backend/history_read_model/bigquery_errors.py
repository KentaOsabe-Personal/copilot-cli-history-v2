from __future__ import annotations

from history_read_model.repository import RepositoryError

_CREDENTIALS_MARKERS = (
    "DefaultCredentialsError",
    "RefreshError",
    "CredentialsError",
    "credentials",
)
_PERMISSION_MARKERS = ("Forbidden", "PermissionDenied", "permission", "access denied")
_SCHEMA_MARKERS = ("NotFound", "BadRequest", "invalidQuery", "not found", "no such field")
_COST_REASONS = ("billingTierLimitExceeded", "quotaExceeded", "resourcesExceeded")


def classify_bigquery_exception(exc: BaseException) -> RepositoryError:
    text = _exception_text(exc)
    reason_text = " ".join(_error_reasons(exc))
    combined = f"{type(exc).__name__} {text} {reason_text}"

    if _contains_any(combined, _CREDENTIALS_MARKERS):
        return RepositoryError(kind="credentials_error", message=text)
    if _contains_any(combined, _PERMISSION_MARKERS):
        return RepositoryError(kind="permission_denied", message=text)
    if _contains_any(combined, _COST_REASONS):
        return RepositoryError(kind="cost_limit_exceeded", message=text)
    if _contains_any(combined, _SCHEMA_MARKERS):
        return RepositoryError(kind="schema_mismatch", message=text)

    return RepositoryError(kind="query_failed", message=text)


def _exception_text(exc: BaseException) -> str:
    text = str(exc).strip()
    return text or type(exc).__name__


def _error_reasons(exc: BaseException) -> tuple[str, ...]:
    errors = getattr(exc, "errors", None)
    if not isinstance(errors, list):
        return ()

    reasons: list[str] = []
    for error in errors:
        if isinstance(error, dict):
            reason = error.get("reason")
            if isinstance(reason, str):
                reasons.append(reason)
    return tuple(reasons)


def _contains_any(value: str, markers: tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(marker.lower() in lowered for marker in markers)


__all__ = ["classify_bigquery_exception"]
