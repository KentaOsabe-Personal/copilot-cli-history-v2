from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast

from copilot_history.api.presenters import HistorySyncPresenter
from copilot_history.api.types import (
    HistorySyncCountsPresentationInput,
    HistorySyncPresentationResult,
    HistorySyncRunPresentationInput,
)
from copilot_history.types import ReadFailureResult, ReadSuccessResult
from history_api.sync_rows import (
    assemble_sync_rows,
    build_failed_sync_run_row,
    build_running_sync_run_row,
)
from history_read_model.fake_repository import HistorySyncRunRow
from history_read_model.repository import (
    RepositoryError,
    RepositoryExecutionOptions,
    SessionListCriteria,
    SessionReadModelRepository,
)

SERVICE_UNAVAILABLE_ERROR_KINDS = {"credentials_error", "permission_denied", "schema_mismatch"}
HISTORY_SYNC_FAILED_CODE = "history_sync_failed"
HISTORY_SYNC_FAILED_MESSAGE = "history sync failed"

type ApiServiceResultKind = Literal[
    "success",
    "not_found",
    "repository_error",
    "sync_conflict",
    "sync_error",
]

type Clock = Callable[[], datetime]
type SyncRunIdFactory = Callable[[], str]


class SessionCatalogReaderLike(Protocol):
    def read(self) -> ReadSuccessResult | ReadFailureResult: ...


@dataclass(frozen=True)
class ApiServiceResult:
    kind: ApiServiceResultKind
    status: int
    data: Any = None
    meta: Mapping[str, object] | None = None
    error: Mapping[str, object] | None = None
    repository_error: RepositoryError | None = None

    @classmethod
    def success(
        cls,
        data: object,
        *,
        meta: Mapping[str, object] | None = None,
    ) -> ApiServiceResult:
        return cls(kind="success", status=200, data=data, meta=meta)

    @classmethod
    def session_not_found(cls, session_id: str) -> ApiServiceResult:
        return cls(
            kind="not_found",
            status=404,
            error={
                "code": "session_not_found",
                "message": "session was not found",
                "details": {"session_id": session_id},
            },
        )

    @classmethod
    def repository_failure(cls, error: RepositoryError) -> ApiServiceResult:
        status = 503 if error.kind in SERVICE_UNAVAILABLE_ERROR_KINDS else 500
        return cls(kind="repository_error", status=status, repository_error=error)


class HistoryApiService:
    def __init__(
        self,
        *,
        repository: SessionReadModelRepository,
        reader: SessionCatalogReaderLike | None = None,
        clock: Clock | None = None,
        sync_run_id_factory: SyncRunIdFactory | None = None,
        options: RepositoryExecutionOptions | None = None,
    ) -> None:
        self._repository = repository
        self._reader = reader
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sync_run_id_factory = sync_run_id_factory or self._default_sync_run_id
        self._options = options or RepositoryExecutionOptions()

    def list_sessions(self, criteria: SessionListCriteria) -> ApiServiceResult:
        result = self._repository.list_sessions(criteria, self._options)
        if not result.ok:
            return ApiServiceResult.repository_failure(_repository_error(result.error))

        data = [dict(payload) for payload in result.summary_payloads]
        return ApiServiceResult.success(
            data,
            meta={
                "count": len(data),
                "partial_results": any(_is_degraded_summary(payload) for payload in data),
            },
        )

    def get_session_detail(self, session_id: str, *, include_raw: bool) -> ApiServiceResult:
        result = self._repository.get_session_detail(session_id, self._options)
        if not result.ok:
            return ApiServiceResult.repository_failure(_repository_error(result.error))
        if not result.found or result.detail_payload is None:
            return ApiServiceResult.session_not_found(result.session_id or session_id)

        return ApiServiceResult.success(
            detail_payload_for_response(result.detail_payload, include_raw=include_raw)
        )

    def sync_history(self) -> ApiServiceResult:
        if self._reader is None:
            return ApiServiceResult.repository_failure(
                RepositoryError(kind="query_failed", message="history reader is not configured")
            )

        sync_run_id = self._sync_run_id_factory()
        started_at = self._clock()
        running_row = build_running_sync_run_row(
            sync_run_id=sync_run_id,
            started_at=started_at,
            indexed_at=started_at,
        )
        start_result = self._repository.start_sync_run(running_row, self._options)
        if not start_result.ok:
            return ApiServiceResult.repository_failure(_repository_error(start_result.error))
        if not start_result.started and start_result.conflict is not None:
            body = HistorySyncPresenter().present(
                HistorySyncPresentationResult(
                    kind="conflict",
                    sync_run=HistorySyncRunPresentationInput(
                        id=_presented_sync_run_id(start_result.conflict.sync_run_id),
                        status="running",
                        started_at=start_result.conflict.started_at,
                        finished_at=None,
                    ),
                )
            )
            return ApiServiceResult(
                kind="sync_conflict",
                status=409,
                error=_error_from_presented_body(body),
            )

        read_result = self._reader.read()
        if isinstance(read_result, ReadFailureResult):
            return self._finish_root_failure(
                sync_run_id=sync_run_id,
                started_at=started_at,
                failure=read_result,
            )

        session_candidates = assemble_sync_rows(
            read_result,
            sync_run_id=sync_run_id,
            started_at=started_at,
            finished_at=started_at,
            indexed_at=started_at,
            write_processed_count=0,
            write_inserted_count=0,
            write_updated_count=0,
            write_skipped_count=0,
            write_failed_count=0,
        )
        write_result = self._repository.save_sessions(
            session_candidates.session_rows,
            self._options,
        )
        finished_at = self._clock()
        if not write_result.ok:
            return self._finish_persistence_failure(
                sync_run_id=sync_run_id,
                started_at=started_at,
                finished_at=finished_at,
                read_result=read_result,
                write_error=_repository_error(write_result.error),
            )

        assembly = assemble_sync_rows(
            read_result,
            sync_run_id=sync_run_id,
            started_at=started_at,
            finished_at=finished_at,
            indexed_at=finished_at,
            write_processed_count=write_result.processed_count,
            write_inserted_count=write_result.inserted_count,
            write_updated_count=write_result.updated_count,
            write_skipped_count=write_result.skipped_count,
            write_failed_count=write_result.failed_count,
        )
        finish_result = self._repository.finish_sync_run(assembly.sync_run_row, self._options)
        if not finish_result.ok:
            finish_error = _repository_error(finish_result.error)
            failed_row = build_failed_sync_run_row(
                sync_run_id=sync_run_id,
                started_at=started_at,
                finished_at=finished_at,
                indexed_at=finished_at,
                counts=assembly.counts,
                failure_summary=finish_error.message,
            )
            return _sync_persistence_failure_result(
                sync_run_id=sync_run_id,
                run_row=failed_row,
                counts=assembly.counts,
                error=finish_error,
            )
        body = HistorySyncPresenter().present(
            HistorySyncPresentationResult(
                kind=cast(
                    Literal["succeeded", "completed_with_issues"],
                    assembly.sync_run_row.status,
                ),
                sync_run=_presentation_run(
                    assembly.sync_run_row.sync_run_id,
                    assembly.sync_run_row,
                ),
                counts=assembly.counts,
            )
        )
        return ApiServiceResult.success(_data_from_presented_body(body))

    def _finish_root_failure(
        self,
        *,
        sync_run_id: str,
        started_at: datetime,
        failure: ReadFailureResult,
    ) -> ApiServiceResult:
        finished_at = self._clock()
        counts = HistorySyncCountsPresentationInput(
            processed_count=0,
            inserted_count=0,
            updated_count=0,
            saved_count=0,
            skipped_count=0,
            failed_count=1,
            degraded_count=0,
        )
        failed_row = build_failed_sync_run_row(
            sync_run_id=sync_run_id,
            started_at=started_at,
            finished_at=finished_at,
            indexed_at=finished_at,
            counts=counts,
            failure_summary=failure.message,
        )
        self._repository.finish_sync_run(failed_row, self._options)
        body = HistorySyncPresenter().present(
            HistorySyncPresentationResult(
                kind="root_failure",
                sync_run=_presentation_run(sync_run_id, failed_row),
                counts=counts,
                error_code=failure.code,
                error_message=failure.message,
                error_details={"path": failure.root_path},
            )
        )
        return ApiServiceResult(
            kind="sync_error",
            status=503,
            error=_error_from_presented_body(body),
            meta=_meta_from_presented_body(body),
        )

    def _finish_persistence_failure(
        self,
        *,
        sync_run_id: str,
        started_at: datetime,
        finished_at: datetime,
        read_result: ReadSuccessResult,
        write_error: RepositoryError,
    ) -> ApiServiceResult:
        counts = HistorySyncCountsPresentationInput(
            processed_count=len(read_result.sessions),
            inserted_count=0,
            updated_count=0,
            saved_count=0,
            skipped_count=0,
            failed_count=1,
            degraded_count=0,
        )
        failed_row = build_failed_sync_run_row(
            sync_run_id=sync_run_id,
            started_at=started_at,
            finished_at=finished_at,
            indexed_at=finished_at,
            counts=counts,
            failure_summary=write_error.message,
        )
        self._repository.finish_sync_run(failed_row, self._options)
        return _sync_persistence_failure_result(
            sync_run_id=sync_run_id,
            run_row=failed_row,
            counts=counts,
            error=write_error,
        )

    def _default_sync_run_id(self) -> str:
        return str(int(self._clock().timestamp() * 1_000_000))


def detail_payload_for_response(
    payload: Mapping[str, object],
    *,
    include_raw: bool,
) -> dict[str, object]:
    filtered = _copy_json_object(payload)
    filtered["raw_included"] = include_raw
    if include_raw:
        return filtered

    return cast(dict[str, object], _suppress_raw_payloads(filtered))


def _suppress_raw_payloads(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: None if key == "raw_payload" else _suppress_raw_payloads(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_suppress_raw_payloads(item) for item in value]
    if isinstance(value, tuple):
        return [_suppress_raw_payloads(item) for item in value]
    return value


def _copy_json_object(payload: Mapping[str, object]) -> dict[str, object]:
    return deepcopy(dict(payload))


def _is_degraded_summary(payload: Mapping[str, object]) -> bool:
    return payload.get("degraded") is True


def _repository_error(error: RepositoryError | None) -> RepositoryError:
    if error is not None:
        return error
    return RepositoryError(kind="query_failed", message="repository operation failed")


def _presentation_run(sync_run_id: str, row: HistorySyncRunRow) -> HistorySyncRunPresentationInput:
    return HistorySyncRunPresentationInput(
        id=_presented_sync_run_id(sync_run_id),
        status=row.status,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _presented_sync_run_id(sync_run_id: str) -> int | str:
    return int(sync_run_id) if sync_run_id.isdecimal() else sync_run_id


def _sync_persistence_failure_result(
    *,
    sync_run_id: str,
    run_row: HistorySyncRunRow,
    counts: HistorySyncCountsPresentationInput,
    error: RepositoryError,
) -> ApiServiceResult:
    details: dict[str, object] = {}
    if error.details is not None:
        details.update(dict(error.details))
    details["sync_run_id"] = _presented_sync_run_id(sync_run_id)
    body = HistorySyncPresenter().present(
        HistorySyncPresentationResult(
            kind="persistence_failure",
            sync_run=_presentation_run(sync_run_id, run_row),
            counts=counts,
            error_code=HISTORY_SYNC_FAILED_CODE,
            error_message=HISTORY_SYNC_FAILED_MESSAGE,
            error_details=details,
        )
    )
    return ApiServiceResult(
        kind="sync_error",
        status=503 if error.kind in SERVICE_UNAVAILABLE_ERROR_KINDS else 500,
        error=_error_from_presented_body(body),
        meta=_meta_from_presented_body(body),
    )


def _data_from_presented_body(body: Mapping[str, object]) -> object:
    return body["data"]


def _error_from_presented_body(body: Mapping[str, object]) -> Mapping[str, object]:
    return cast(Mapping[str, object], body["error"])


def _meta_from_presented_body(body: Mapping[str, object]) -> Mapping[str, object]:
    return cast(Mapping[str, object], body["meta"])


__all__ = [
    "ApiServiceResult",
    "HistoryApiService",
    "detail_payload_for_response",
]
