from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from django.core.management.base import BaseCommand, CommandError, CommandParser

from history_read_model.bigquery_schema import BigQueryTable, read_model_tables
from history_read_model.bigquery_settings import (
    BigQueryReadModelSettings,
    BigQuerySettingsError,
    load_bigquery_settings,
)
from history_read_model.ddl import (
    build_create_dataset_sql,
    build_create_table_sql,
    build_schema_metadata_sql,
)
from history_read_model.metadata_comparator import SchemaDiff, compare_metadata

BigQueryClientFactory = Callable[[BigQueryReadModelSettings], object]


class Command(BaseCommand):
    help = "Show, create, or compare the BigQuery read model schema."
    stealth_options = (*BaseCommand.stealth_options, "client_factory")

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Create the dataset and tables if they do not already exist.",
        )
        parser.add_argument(
            "--compare",
            action="store_true",
            help="Compare existing BigQuery metadata against the schema contract.",
        )

    def handle(self, *args: object, **options: object) -> None:
        execute = bool(options["execute"])
        compare = bool(options["compare"])
        require_credentials = execute or compare
        client_factory = options.get("client_factory")

        try:
            settings = load_bigquery_settings(require_credentials=require_credentials)
        except BigQuerySettingsError as exc:
            raise CommandError(str(exc)) from exc

        tables = read_model_tables(table_prefix=settings.table_prefix)
        create_sql = [
            build_create_dataset_sql(settings),
            *(build_create_table_sql(settings, table) for table in tables),
        ]
        metadata_sql = build_schema_metadata_sql(settings)

        mode = _mode_label(execute=execute, compare=compare)
        self.stdout.write(f"Mode: {mode}")
        self.stdout.write(f"Target dataset: {settings.project_id}.{settings.dataset_id}")
        self.stdout.write("Target tables: " + ", ".join(table.name for table in tables))
        self.stdout.write("Repository query/upsert: not executed by this command")
        self.stdout.write("")
        self.stdout.write("Create SQL:")
        for sql in create_sql:
            self.stdout.write(sql)
            self.stdout.write("")

        if not execute and not compare:
            self.stdout.write("Dry-run result: no BigQuery client was created")
            return

        factory = _coerce_client_factory(client_factory)
        client = factory(settings)

        if execute:
            for sql in create_sql:
                _run_query(client, sql)
            self.stdout.write("Execute result: create statements submitted")

        if compare:
            rows = _run_query(client, metadata_sql)
            diff = _compare_rows(tables, rows)
            self._write_compare_result(diff)
            if not diff.compatible:
                raise CommandError("BigQuery read model schema is incompatible")

    def _write_compare_result(self, diff: SchemaDiff) -> None:
        if diff.compatible:
            self.stdout.write("Compare result: compatible schema")
        else:
            self.stderr.write("Compare result: incompatible schema")

        if diff.missing:
            self.stderr.write("Missing:")
            for entry in diff.missing:
                self.stderr.write(f"- {entry}")
        if diff.incompatible:
            self.stderr.write("Incompatible:")
            for entry in diff.incompatible:
                self.stderr.write(f"- {entry}")
        if diff.extra:
            self.stdout.write("Extra informational:")
            for entry in diff.extra:
                self.stdout.write(f"- {entry}")


def _mode_label(*, execute: bool, compare: bool) -> str:
    if execute and compare:
        return "execute+compare"
    if execute:
        return "execute"
    if compare:
        return "compare"
    return "dry-run"


def _coerce_client_factory(client_factory: object) -> BigQueryClientFactory:
    if client_factory is None:
        return _default_bigquery_client
    if not callable(client_factory):
        raise CommandError("client_factory must be callable when provided.")
    return client_factory


def _default_bigquery_client(settings: BigQueryReadModelSettings) -> object:
    from google.cloud import bigquery

    return bigquery.Client(project=settings.project_id, location=settings.location)


def _run_query(client: object, sql: str) -> list[Mapping[str, object]]:
    query = getattr(client, "query", None)
    if not callable(query):
        raise CommandError("BigQuery client must expose a callable query(sql) method.")

    result = query(sql)
    if result is None:
        return []
    return [_row_to_mapping(row) for row in result]


def _compare_rows(
    expected_tables: tuple[BigQueryTable, ...],
    rows: Sequence[Mapping[str, object]],
) -> SchemaDiff:
    column_rows = tuple(row for row in rows if row.get("metadata_kind") == "column")
    option_rows = tuple(row for row in rows if row.get("metadata_kind") == "option")
    return compare_metadata(
        expected=expected_tables,
        actual_columns=column_rows,
        actual_options=option_rows,
    )


def _row_to_mapping(row: object) -> Mapping[str, object]:
    if isinstance(row, Mapping):
        return row
    if hasattr(row, "items"):
        return dict(row.items())
    return {key: getattr(row, key) for key in dir(row) if not key.startswith("_")}
