from pathlib import Path

from copilot_history.types import ResolvedHistoryRoot, SessionSource


class SourceCatalog:
    def list_sources(self, root: ResolvedHistoryRoot) -> tuple[SessionSource, ...]:
        current_sources = self._list_current_sources(Path(root.current_root))
        legacy_sources = self._list_legacy_sources(Path(root.legacy_root))
        return tuple([*current_sources, *legacy_sources])

    def _list_current_sources(self, current_root: Path) -> tuple[SessionSource, ...]:
        if not self._can_scan_optional_source_root(current_root):
            return ()

        sources: list[SessionSource] = []
        for session_dir in sorted(current_root.iterdir(), key=lambda path: path.name):
            if not session_dir.is_dir():
                continue
            sources.append(
                SessionSource(
                    session_id=session_dir.name,
                    source_format="current",
                    source_path=str(session_dir),
                    artifact_paths={
                        "workspace": str(session_dir / "workspace.yaml"),
                        "events": str(session_dir / "events.jsonl"),
                    },
                    metadata={"session_id_source": "directory_name"},
                )
            )
        return tuple(sources)

    def _list_legacy_sources(self, legacy_root: Path) -> tuple[SessionSource, ...]:
        if not self._can_scan_optional_source_root(legacy_root):
            return ()

        sources: list[SessionSource] = []
        for legacy_file in sorted(legacy_root.glob("*.json"), key=lambda path: path.name):
            if not legacy_file.is_file():
                continue
            sources.append(
                SessionSource(
                    session_id=legacy_file.stem,
                    source_format="legacy",
                    source_path=str(legacy_file),
                    artifact_paths={"legacy_json": str(legacy_file)},
                    metadata={"session_id_source": "file_stem"},
                )
            )
        return tuple(sources)

    def _can_scan_optional_source_root(self, path: Path) -> bool:
        return path.exists() and path.is_dir()
