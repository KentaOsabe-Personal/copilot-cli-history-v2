from dataclasses import dataclass
from typing import Literal

SCHEMA_VERSION = "bigquery-read-model-schema-v1"

BigQueryType = Literal["STRING", "INT64", "BOOL", "TIMESTAMP", "DATE", "JSON"]
BigQueryMode = Literal["REQUIRED", "NULLABLE"]

SOURCE_FORMAT_VALUES = ("current", "legacy")
SOURCE_STATE_VALUES = ("complete", "workspace_only", "degraded")
SYNC_STATUS_VALUES = ("running", "succeeded", "failed", "completed_with_issues")

COPILOT_SESSION_COUNT_FIELDS = (
    "event_count",
    "message_snapshot_count",
    "issue_count",
    "message_count",
    "activity_count",
)
HISTORY_SYNC_RUN_COUNT_FIELDS = (
    "processed_count",
    "inserted_count",
    "updated_count",
    "saved_count",
    "skipped_count",
    "failed_count",
    "degraded_count",
)

COPILOT_SESSIONS_BASE_NAME = "copilot_sessions"
HISTORY_SYNC_RUNS_BASE_NAME = "history_sync_runs"


@dataclass(frozen=True)
class BigQueryColumn:
    name: str
    type: BigQueryType
    mode: BigQueryMode
    default_equivalent: object | None
    description: str
    allowed_values: tuple[str, ...] = ()
    non_negative: bool = False
    json_object: bool = False


@dataclass(frozen=True)
class BigQueryTable:
    base_name: str
    name: str
    columns: tuple[BigQueryColumn, ...]
    partition_by: str | None
    partition_source: str | None
    require_partition_filter: bool
    cluster_by: tuple[str, ...]
    lookup_fields: tuple[str, ...]
    read_model_role: str = "regenerable_from_raw_files"
    cost_optimization_scope: str = "initial_layout_only"
    running_status: str | None = None
    terminal_statuses: tuple[str, ...] = ()
    saved_count_equals: tuple[str, str] | None = None

    @property
    def column_map(self) -> dict[str, BigQueryColumn]:
        return {column.name: column for column in self.columns}


def read_model_tables(table_prefix: str = "") -> tuple[BigQueryTable, ...]:
    return (
        _copilot_sessions_table(table_prefix),
        _history_sync_runs_table(table_prefix),
    )


def table_by_base_name(base_name: str, table_prefix: str = "") -> BigQueryTable:
    for table in read_model_tables(table_prefix=table_prefix):
        if table.base_name == base_name:
            return table

    raise KeyError(f"Unknown BigQuery read model table: {base_name}")


def _prefixed_table_name(base_name: str, table_prefix: str) -> str:
    return f"{table_prefix}{base_name}"


def _required_column(
    name: str,
    column_type: BigQueryType,
    description: str,
    *,
    default_equivalent: object | None = None,
    allowed_values: tuple[str, ...] = (),
    non_negative: bool = False,
    json_object: bool = False,
) -> BigQueryColumn:
    return BigQueryColumn(
        name=name,
        type=column_type,
        mode="REQUIRED",
        default_equivalent=default_equivalent,
        description=description,
        allowed_values=allowed_values,
        non_negative=non_negative,
        json_object=json_object,
    )


def _nullable_column(
    name: str,
    column_type: BigQueryType,
    description: str,
    *,
    default_equivalent: object | None = None,
    allowed_values: tuple[str, ...] = (),
    non_negative: bool = False,
    json_object: bool = False,
) -> BigQueryColumn:
    return BigQueryColumn(
        name=name,
        type=column_type,
        mode="NULLABLE",
        default_equivalent=default_equivalent,
        description=description,
        allowed_values=allowed_values,
        non_negative=non_negative,
        json_object=json_object,
    )


def _non_negative_count_column(name: str, description: str) -> BigQueryColumn:
    return _required_column(
        name=name,
        column_type="INT64",
        default_equivalent=0,
        description=description,
        non_negative=True,
    )


def _copilot_sessions_table(table_prefix: str) -> BigQueryTable:
    columns = (
        _required_column("session_id", "STRING", "Stable Copilot CLI session identifier."),
        _required_column(
            "source_format",
            "STRING",
            "Raw file format family used to build this row.",
            allowed_values=SOURCE_FORMAT_VALUES,
        ),
        _required_column(
            "source_state",
            "STRING",
            "Completeness state of the raw source material for this session.",
            allowed_values=SOURCE_STATE_VALUES,
        ),
        _nullable_column("created_at_source", "TIMESTAMP", "Created timestamp from raw source."),
        _nullable_column("updated_at_source", "TIMESTAMP", "Updated timestamp from raw source."),
        _required_column(
            "source_partition_date",
            "DATE",
            "Date partition derived from the source timestamp used by list queries.",
        ),
        _nullable_column("cwd", "STRING", "Current working directory from the session source."),
        _nullable_column("git_root", "STRING", "Detected git repository root path."),
        _nullable_column("repository", "STRING", "Repository name or path projection."),
        _nullable_column("branch", "STRING", "Git branch projection."),
        _nullable_column("selected_model", "STRING", "Selected model name when present."),
        _non_negative_count_column("event_count", "Number of normalized source events."),
        _non_negative_count_column(
            "message_snapshot_count",
            "Number of message snapshots in the session.",
        ),
        _non_negative_count_column("issue_count", "Number of extracted issue references."),
        _non_negative_count_column("message_count", "Number of presenter-visible messages."),
        _non_negative_count_column("activity_count", "Number of projected activity items."),
        _required_column(
            "degraded",
            "BOOL",
            "Whether this row was built from partially degraded source data.",
            default_equivalent=False,
        ),
        _nullable_column("conversation_preview", "STRING", "Search and list preview text."),
        _required_column(
            "source_paths",
            "JSON",
            "JSON object with raw source file path metadata.",
            json_object=True,
        ),
        _required_column(
            "source_fingerprint",
            "JSON",
            "JSON object used to detect source changes during explicit sync.",
            json_object=True,
        ),
        _required_column(
            "summary_payload",
            "JSON",
            "Presenter-compatible summary payload stored without reshaping.",
            json_object=True,
        ),
        _required_column(
            "detail_payload",
            "JSON",
            "Presenter-compatible detail payload stored without reshaping.",
            json_object=True,
        ),
        _required_column(
            "search_text",
            "STRING",
            "Search projection generated from conversation, preview, and issue content.",
            default_equivalent="",
        ),
        _required_column(
            "search_text_version",
            "INT64",
            "Version of the search text projection contract.",
            default_equivalent=0,
            non_negative=True,
        ),
        _required_column(
            "indexed_at",
            "TIMESTAMP",
            "Timestamp when the read model row was generated.",
        ),
    )
    return BigQueryTable(
        base_name=COPILOT_SESSIONS_BASE_NAME,
        name=_prefixed_table_name(COPILOT_SESSIONS_BASE_NAME, table_prefix),
        columns=columns,
        partition_by="source_partition_date",
        partition_source="updated_at_source",
        require_partition_filter=True,
        cluster_by=("session_id", "repository", "branch", "source_format"),
        lookup_fields=(
            "source_partition_date",
            "session_id",
            "repository",
            "branch",
            "source_format",
            "source_state",
            "search_text",
        ),
    )


def _history_sync_runs_table(table_prefix: str) -> BigQueryTable:
    columns = (
        _required_column(
            "status",
            "STRING",
            "Sync lifecycle status for the explicit read model refresh.",
            allowed_values=SYNC_STATUS_VALUES,
        ),
        _required_column("started_at", "TIMESTAMP", "Timestamp when this sync run started."),
        _nullable_column("finished_at", "TIMESTAMP", "Timestamp when this sync run finished."),
        _required_column(
            "started_partition_date",
            "DATE",
            "Date partition derived from started_at for recent sync run lookup.",
        ),
        _non_negative_count_column("processed_count", "Number of source records processed."),
        _non_negative_count_column("inserted_count", "Number of session rows inserted."),
        _non_negative_count_column("updated_count", "Number of session rows updated."),
        _non_negative_count_column("saved_count", "Inserted plus updated session row count."),
        _non_negative_count_column("skipped_count", "Number of unchanged sessions skipped."),
        _non_negative_count_column("failed_count", "Number of failed session records."),
        _non_negative_count_column("degraded_count", "Number of degraded session records."),
        _nullable_column("failure_summary", "STRING", "Human-readable failure summary."),
        _nullable_column(
            "degradation_summary",
            "STRING",
            "Human-readable partial degradation summary.",
        ),
        _nullable_column(
            "running_lock_key",
            "STRING",
            "Lock identity present only while a sync run is running.",
        ),
    )
    return BigQueryTable(
        base_name=HISTORY_SYNC_RUNS_BASE_NAME,
        name=_prefixed_table_name(HISTORY_SYNC_RUNS_BASE_NAME, table_prefix),
        columns=columns,
        partition_by="started_partition_date",
        partition_source="started_at",
        require_partition_filter=False,
        cluster_by=("status", "started_at", "running_lock_key"),
        lookup_fields=("started_at", "status", "running_lock_key"),
        running_status="running",
        terminal_statuses=("succeeded", "failed", "completed_with_issues"),
        saved_count_equals=("inserted_count", "updated_count"),
    )
