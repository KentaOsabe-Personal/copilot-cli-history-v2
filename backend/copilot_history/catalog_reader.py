from pathlib import Path

from copilot_history.current_reader import CurrentSessionReader
from copilot_history.legacy_reader import LegacySessionReader
from copilot_history.root_resolver import RootResolver
from copilot_history.source_catalog import SourceCatalog
from copilot_history.types import (
    NormalizedSession,
    ReadFailureResult,
    ReadSuccessResult,
    SessionSource,
)


class SessionCatalogReader:
    def __init__(
        self,
        *,
        root_resolver: RootResolver | None = None,
        source_catalog: SourceCatalog | None = None,
        current_reader: CurrentSessionReader | None = None,
        legacy_reader: LegacySessionReader | None = None,
    ) -> None:
        self._root_resolver = root_resolver or RootResolver()
        self._source_catalog = source_catalog or SourceCatalog()
        self._current_reader = current_reader or CurrentSessionReader()
        self._legacy_reader = legacy_reader or LegacySessionReader()

    def read(self, root: str | Path | None = None) -> ReadSuccessResult | ReadFailureResult:
        resolved_root = self._root_resolver.resolve(root)
        if isinstance(resolved_root, ReadFailureResult):
            return resolved_root

        sessions = tuple(
            self._read_source(source)
            for source in self._source_catalog.list_sources(resolved_root)
        )
        return ReadSuccessResult(root=resolved_root, sessions=sessions)

    def _read_source(self, source: SessionSource) -> NormalizedSession:
        if source.source_format == "current":
            return self._current_reader.read(source)
        return self._legacy_reader.read(source)


__all__ = ["SessionCatalogReader"]
