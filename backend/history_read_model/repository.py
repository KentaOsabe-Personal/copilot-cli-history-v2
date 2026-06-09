from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

type JsonObject = Mapping[str, object]

type RepositoryErrorKind = Literal[
    "validation_error",
    "missing_date_range",
    "credentials_error",
    "permission_denied",
    "schema_mismatch",
    "cost_limit_exceeded",
    "query_failed",
]


@dataclass(frozen=True)
class RepositoryError:
    kind: RepositoryErrorKind
    message: str
    details: JsonObject | None = None


@dataclass(frozen=True)
class SessionListCriteria:
    from_datetime: datetime | None
    to_datetime: datetime | None
    search_term: str | None = None
    limit: int | None = None


@dataclass(frozen=True)
class RepositoryExecutionOptions:
    dry_run: bool = False
    maximum_bytes_billed: int | None = None
    location: str | None = None


@dataclass(frozen=True)
class SessionListResult:
    ok: bool
    summary_payloads: tuple[JsonObject, ...]
    error: RepositoryError | None = None
    dry_run: bool = False
    planned_operations: tuple[str, ...] = ()

    @classmethod
    def success(
        cls,
        summary_payloads: Iterable[JsonObject],
        *,
        dry_run: bool = False,
        planned_operations: Iterable[str] = (),
    ) -> SessionListResult:
        return cls(
            ok=True,
            summary_payloads=tuple(summary_payloads),
            dry_run=dry_run,
            planned_operations=tuple(planned_operations),
        )

    @classmethod
    def failure(cls, error: RepositoryError) -> SessionListResult:
        return cls(ok=False, summary_payloads=(), error=error)


@dataclass(frozen=True)
class SessionDetailResult:
    ok: bool
    found: bool
    detail_payload: JsonObject | None = None
    session_id: str | None = None
    error: RepositoryError | None = None
    dry_run: bool = False
    planned_operations: tuple[str, ...] = ()

    @classmethod
    def success(
        cls,
        detail_payload: JsonObject,
        *,
        session_id: str | None = None,
        dry_run: bool = False,
        planned_operations: Iterable[str] = (),
    ) -> SessionDetailResult:
        return cls(
            ok=True,
            found=True,
            detail_payload=detail_payload,
            session_id=session_id,
            dry_run=dry_run,
            planned_operations=tuple(planned_operations),
        )

    @classmethod
    def not_found(cls, session_id: str) -> SessionDetailResult:
        return cls(ok=True, found=False, session_id=session_id)

    @classmethod
    def failure(cls, error: RepositoryError) -> SessionDetailResult:
        return cls(ok=False, found=False, error=error)


@dataclass(frozen=True)
class SyncWriteResult:
    ok: bool
    processed_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    saved_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    degraded_count: int = 0
    error: RepositoryError | None = None
    dry_run: bool = False
    planned_operations: tuple[str, ...] = ()

    @classmethod
    def success(
        cls,
        *,
        processed_count: int,
        inserted_count: int,
        updated_count: int,
        skipped_count: int,
        failed_count: int,
        degraded_count: int,
        dry_run: bool = False,
        planned_operations: Iterable[str] = (),
    ) -> SyncWriteResult:
        return cls(
            ok=True,
            processed_count=processed_count,
            inserted_count=inserted_count,
            updated_count=updated_count,
            saved_count=inserted_count + updated_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            degraded_count=degraded_count,
            dry_run=dry_run,
            planned_operations=tuple(planned_operations),
        )

    @classmethod
    def failure(cls, error: RepositoryError) -> SyncWriteResult:
        return cls(ok=False, error=error)


@dataclass(frozen=True)
class SyncRunResult:
    ok: bool
    sync_run_id: str | None = None
    error: RepositoryError | None = None
    dry_run: bool = False
    planned_operations: tuple[str, ...] = ()

    @classmethod
    def success(
        cls,
        sync_run_id: str,
        *,
        dry_run: bool = False,
        planned_operations: Iterable[str] = (),
    ) -> SyncRunResult:
        return cls(
            ok=True,
            sync_run_id=sync_run_id,
            dry_run=dry_run,
            planned_operations=tuple(planned_operations),
        )

    @classmethod
    def failure(cls, error: RepositoryError) -> SyncRunResult:
        return cls(ok=False, error=error)


@dataclass(frozen=True)
class SyncRunLookupResult:
    ok: bool
    found: bool
    sync_run_id: str | None = None
    error: RepositoryError | None = None
    dry_run: bool = False
    planned_operations: tuple[str, ...] = ()

    @classmethod
    def success(
        cls,
        sync_run_id: str,
        *,
        dry_run: bool = False,
        planned_operations: Iterable[str] = (),
    ) -> SyncRunLookupResult:
        return cls(
            ok=True,
            found=True,
            sync_run_id=sync_run_id,
            dry_run=dry_run,
            planned_operations=tuple(planned_operations),
        )

    @classmethod
    def not_found(cls) -> SyncRunLookupResult:
        return cls(ok=True, found=False)

    @classmethod
    def failure(cls, error: RepositoryError) -> SyncRunLookupResult:
        return cls(ok=False, found=False, error=error)


class CopilotSessionWriteInput(Protocol):
    session_id: str


class HistorySyncRunWriteInput(Protocol):
    sync_run_id: str


class SessionReadModelRepository(Protocol):
    def list_sessions(
        self,
        criteria: SessionListCriteria,
        options: RepositoryExecutionOptions,
    ) -> SessionListResult: ...

    def get_session_detail(
        self,
        session_id: str,
        options: RepositoryExecutionOptions,
    ) -> SessionDetailResult: ...

    def save_sessions(
        self,
        rows: Sequence[CopilotSessionWriteInput],
        options: RepositoryExecutionOptions,
    ) -> SyncWriteResult: ...

    def save_sync_run(
        self,
        row: HistorySyncRunWriteInput,
        options: RepositoryExecutionOptions,
    ) -> SyncRunResult: ...

    def find_running_sync_run(
        self,
        options: RepositoryExecutionOptions,
    ) -> SyncRunLookupResult: ...


def validate_session_list_criteria(criteria: SessionListCriteria) -> RepositoryError | None:
    if criteria.from_datetime is None or criteria.to_datetime is None:
        return RepositoryError(
            kind="missing_date_range",
            message="session list requires from_datetime and to_datetime",
        )

    fields: list[str] = []
    reasons: list[str] = []
    if criteria.from_datetime > criteria.to_datetime:
        fields.append("from_datetime")
        reasons.append("from_datetime must be earlier than or equal to to_datetime")
    if criteria.limit is not None and criteria.limit <= 0:
        fields.append("limit")
        reasons.append("limit must be a positive integer when provided")

    if reasons:
        return RepositoryError(
            kind="validation_error",
            message="invalid session list criteria",
            details={"fields": tuple(fields), "reasons": tuple(reasons)},
        )

    return None


def validate_session_id(session_id: str) -> RepositoryError | None:
    if session_id.strip() == "":
        return RepositoryError(
            kind="validation_error",
            message="session_id must not be blank",
            details={"fields": ("session_id",)},
        )

    return None


def validate_repository_options(options: RepositoryExecutionOptions) -> RepositoryError | None:
    if options.maximum_bytes_billed is not None and options.maximum_bytes_billed <= 0:
        return RepositoryError(
            kind="validation_error",
            message="maximum_bytes_billed must be a positive integer when provided",
            details={"fields": ("maximum_bytes_billed",)},
        )

    return None
