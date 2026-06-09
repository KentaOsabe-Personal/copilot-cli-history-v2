from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from history_read_model.fake_repository import (
    CopilotSessionRow,
    FakeBigQueryReadModelRepository,
    ReadModelContractError,
)
from history_read_model.repository import SyncWriteResult
from history_read_model.repository_rows import SessionRowBuildCandidate


@dataclass(frozen=True)
class ExistingSessionMetadata:
    session_id: str
    source_fingerprint: Mapping[str, object]
    search_text_version: int


@dataclass(frozen=True)
class WorkspaceOnlySessionWriteInput:
    session_id: str


@dataclass(frozen=True)
class InvalidSessionWriteInput:
    session_id: str
    error_reasons: tuple[str, ...]
    row: CopilotSessionRow | None = None


type SessionWriteInput = (
    CopilotSessionRow
    | WorkspaceOnlySessionWriteInput
    | InvalidSessionWriteInput
    | SessionRowBuildCandidate
)


@dataclass(frozen=True)
class SyncWritePlan:
    insert_rows: tuple[CopilotSessionRow, ...]
    update_rows: tuple[CopilotSessionRow, ...]
    skipped_session_ids: tuple[str, ...]
    workspace_only_session_ids: tuple[str, ...]
    invalid_rows: tuple[InvalidSessionWriteInput, ...]
    processed_count: int
    degraded_count: int

    @property
    def rows_for_merge(self) -> tuple[CopilotSessionRow, ...]:
        return (*self.insert_rows, *self.update_rows)

    def to_result(self, *, dry_run: bool = False) -> SyncWriteResult:
        return SyncWriteResult.success(
            processed_count=self.processed_count,
            inserted_count=len(self.insert_rows),
            updated_count=len(self.update_rows),
            skipped_count=len(self.skipped_session_ids) + len(self.workspace_only_session_ids),
            failed_count=len(self.invalid_rows),
            degraded_count=self.degraded_count,
            dry_run=dry_run,
            planned_operations=("metadata_lookup", "classify", "merge"),
        )


def plan_sync_write(
    rows: Sequence[SessionWriteInput],
    *,
    existing_metadata: Mapping[str, ExistingSessionMetadata],
) -> SyncWritePlan:
    insert_rows: list[CopilotSessionRow] = []
    update_rows: list[CopilotSessionRow] = []
    skipped_session_ids: list[str] = []
    workspace_only_session_ids: list[str] = []
    invalid_rows: list[InvalidSessionWriteInput] = []
    degraded_count = 0

    for input_row in rows:
        candidate = _normalize_input(input_row)
        if isinstance(candidate, WorkspaceOnlySessionWriteInput):
            workspace_only_session_ids.append(candidate.session_id)
            continue
        if isinstance(candidate, InvalidSessionWriteInput):
            invalid_rows.append(candidate)
            continue

        row = candidate
        validation_error = _validation_error_for(row)
        if validation_error is not None:
            invalid_rows.append(
                InvalidSessionWriteInput(
                    session_id=row.session_id,
                    row=row,
                    error_reasons=(validation_error,),
                )
            )
            continue

        if row.degraded:
            degraded_count += 1

        existing = existing_metadata.get(row.session_id)
        if existing is None:
            insert_rows.append(row)
        elif _should_update(row, existing):
            update_rows.append(row)
        else:
            skipped_session_ids.append(row.session_id)

    return SyncWritePlan(
        insert_rows=tuple(insert_rows),
        update_rows=tuple(update_rows),
        skipped_session_ids=tuple(skipped_session_ids),
        workspace_only_session_ids=tuple(workspace_only_session_ids),
        invalid_rows=tuple(invalid_rows),
        processed_count=len(rows),
        degraded_count=degraded_count,
    )


def _normalize_input(
    input_row: SessionWriteInput,
) -> CopilotSessionRow | WorkspaceOnlySessionWriteInput | InvalidSessionWriteInput:
    if isinstance(input_row, SessionRowBuildCandidate):
        if input_row.status == "workspace_only":
            return WorkspaceOnlySessionWriteInput(session_id=input_row.session_id)
        if input_row.status == "invalid" or input_row.row is None:
            return InvalidSessionWriteInput(
                session_id=input_row.session_id,
                error_reasons=input_row.error_reasons,
                row=input_row.row,
            )
        return input_row.row
    return input_row


def _validation_error_for(row: CopilotSessionRow) -> str | None:
    if row.session_id.strip() == "":
        return "session_id is required"

    repository = FakeBigQueryReadModelRepository()
    try:
        repository.save_session(row)
    except ReadModelContractError as exc:
        return str(exc)
    return None


def _should_update(row: CopilotSessionRow, existing: ExistingSessionMetadata) -> bool:
    return (
        row.source_fingerprint != existing.source_fingerprint
        or row.search_text_version != existing.search_text_version
    )


__all__ = [
    "ExistingSessionMetadata",
    "InvalidSessionWriteInput",
    "SessionWriteInput",
    "SyncWritePlan",
    "WorkspaceOnlySessionWriteInput",
    "plan_sync_write",
]
