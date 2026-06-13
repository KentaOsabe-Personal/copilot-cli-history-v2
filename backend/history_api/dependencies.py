from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from django.conf import settings

from copilot_history.catalog_reader import SessionCatalogReader
from copilot_history.types import ReadFailureResult, ReadSuccessResult
from history_read_model.bigquery_repository import BigQuerySessionReadModelRepository
from history_read_model.bigquery_settings import BigQueryReadModelSettings, load_bigquery_settings
from history_read_model.fake_repository import FakeBigQueryReadModelRepository
from history_read_model.repository import SessionReadModelRepository

Clock = Callable[[], datetime]
BigQuerySettingsLoader = Callable[..., BigQueryReadModelSettings]
BigQueryClientFactory = Callable[[str], object]


class SessionCatalogReaderLike(Protocol):
    def read(self) -> ReadSuccessResult | ReadFailureResult: ...


@dataclass
class _DependencyState:
    repository: SessionReadModelRepository | None = None
    reader: SessionCatalogReaderLike | None = None
    clock: Clock | None = None
    bigquery_settings_loader: BigQuerySettingsLoader | None = None
    bigquery_client_factory: BigQueryClientFactory | None = None


_state = _DependencyState()


def get_repository() -> SessionReadModelRepository:
    if _state.repository is not None:
        return _state.repository

    backend = str(getattr(settings, "HISTORY_API_REPOSITORY_BACKEND", "fake")).strip().lower()
    if backend == "fake":
        return FakeBigQueryReadModelRepository()
    if backend == "bigquery":
        bigquery_settings = _bigquery_settings()
        return BigQuerySessionReadModelRepository(
            client=_bigquery_client_factory()(bigquery_settings.project_id),
            settings=bigquery_settings,
        )

    msg = f"Unsupported HISTORY_API_REPOSITORY_BACKEND: {backend}"
    raise RuntimeError(msg)


def get_reader() -> SessionCatalogReaderLike:
    if _state.reader is not None:
        return _state.reader
    return SessionCatalogReader()


def get_clock() -> Clock:
    if _state.clock is not None:
        return _state.clock
    return lambda: datetime.now(UTC)


@contextmanager
def dependency_overrides(
    *,
    repository: SessionReadModelRepository | None = None,
    reader: SessionCatalogReaderLike | None = None,
    clock: Clock | None = None,
    bigquery_settings_loader: BigQuerySettingsLoader | None = None,
    bigquery_client_factory: BigQueryClientFactory | None = None,
) -> Iterator[None]:
    previous = _DependencyState(
        repository=_state.repository,
        reader=_state.reader,
        clock=_state.clock,
        bigquery_settings_loader=_state.bigquery_settings_loader,
        bigquery_client_factory=_state.bigquery_client_factory,
    )
    _state.repository = repository
    _state.reader = reader
    _state.clock = clock
    _state.bigquery_settings_loader = bigquery_settings_loader
    _state.bigquery_client_factory = bigquery_client_factory
    try:
        yield
    finally:
        _state.repository = previous.repository
        _state.reader = previous.reader
        _state.clock = previous.clock
        _state.bigquery_settings_loader = previous.bigquery_settings_loader
        _state.bigquery_client_factory = previous.bigquery_client_factory


def _bigquery_settings() -> BigQueryReadModelSettings:
    loader = _state.bigquery_settings_loader or load_bigquery_settings
    return loader(require_credentials=True)


def _bigquery_client_factory() -> BigQueryClientFactory:
    if _state.bigquery_client_factory is not None:
        return _state.bigquery_client_factory

    def create_client(project_id: str) -> Any:
        from google.cloud import bigquery

        return bigquery.Client(project=project_id)

    return create_client


__all__ = [
    "dependency_overrides",
    "get_clock",
    "get_reader",
    "get_repository",
]
