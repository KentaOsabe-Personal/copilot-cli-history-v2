from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from django.http import QueryDict

from history_read_model.repository import SessionListCriteria

MAX_SESSION_LIST_LIMIT = 500
MAX_SEARCH_LENGTH = 200


@dataclass(frozen=True)
class ValidatedSessionListQuery:
    criteria: SessionListCriteria


@dataclass(frozen=True)
class QueryValidationError(Exception):
    field: str
    reason: str
    value: object | None = None


def validate_session_list_query(
    params: QueryDict,
) -> ValidatedSessionListQuery | QueryValidationError:
    from_value = params.get("from")
    to_value = params.get("to")

    from_datetime: datetime | None = None
    if from_value is not None:
        parsed_from = _parse_datetime_query_value("from", from_value)
        if isinstance(parsed_from, QueryValidationError):
            return parsed_from
        from_datetime = parsed_from

    to_datetime: datetime | None = None
    if to_value is not None:
        parsed_to = _parse_datetime_query_value("to", to_value)
        if isinstance(parsed_to, QueryValidationError):
            return parsed_to
        to_datetime = parsed_to
    if from_datetime is not None and to_datetime is not None and from_datetime > to_datetime:
        return QueryValidationError(field="range", reason="from_after_to")

    limit = _parse_limit(params.get("limit"))
    if isinstance(limit, QueryValidationError):
        return limit

    search = _parse_search(params.get("search"))
    if isinstance(search, QueryValidationError):
        return search

    return ValidatedSessionListQuery(
        criteria=SessionListCriteria(
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            search_term=search,
            limit=limit,
        )
    )


def parse_include_raw(params: QueryDict) -> bool:
    return params.get("include_raw") == "true"


def _parse_datetime_query_value(field: str, value: str) -> datetime | QueryValidationError:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return QueryValidationError(field=field, reason="invalid_datetime", value=value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_limit(value: str | None) -> int | None | QueryValidationError:
    if value is None or value.strip() == "":
        return None
    try:
        limit = int(value)
    except ValueError:
        return QueryValidationError(field="limit", reason="not_integer", value=value)
    if limit < 1 or limit > MAX_SESSION_LIST_LIMIT:
        return QueryValidationError(field="limit", reason="positive_integer_required", value=value)
    return limit


def _parse_search(value: str | None) -> str | None | QueryValidationError:
    if value is None:
        return None
    search = value.strip()
    if search == "":
        return None
    if len(search) > MAX_SEARCH_LENGTH:
        return QueryValidationError(field="search", reason="too_long", value=value)
    if any(_is_disallowed_control_character(character) for character in search):
        return QueryValidationError(field="search", reason="control_character", value=value)
    return search


def _is_disallowed_control_character(character: str) -> bool:
    return ord(character) < 32 and character not in {"\t", "\n", "\r"}


__all__ = [
    "MAX_SEARCH_LENGTH",
    "MAX_SESSION_LIST_LIMIT",
    "QueryValidationError",
    "ValidatedSessionListQuery",
    "parse_include_raw",
    "validate_session_list_query",
]
