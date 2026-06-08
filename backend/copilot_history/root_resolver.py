from pathlib import Path

from copilot_history.types import ReadFailureResult, ResolvedHistoryRoot, RootFailure


class RootResolver:
    def resolve(self, root: str | Path | None = None) -> ResolvedHistoryRoot | RootFailure:
        root_path = self._candidate_root(root)
        root_text = str(root_path)

        if not root_path.exists():
            return ReadFailureResult(
                code="root_missing",
                message=f"history root does not exist: {root_text}",
                root_path=root_text,
            )

        if not root_path.is_dir():
            return ReadFailureResult(
                code="root_unreadable",
                message=f"history root is not a directory: {root_text}",
                root_path=root_text,
            )

        if not self._has_directory_read_access(root_path):
            return ReadFailureResult(
                code="root_permission_denied",
                message=f"history root is not readable: {root_text}",
                root_path=root_text,
            )

        return ResolvedHistoryRoot(
            requested_root=root_text,
            current_root=str(root_path / "session-state"),
            legacy_root=str(root_path / "history-session-state"),
        )

    def _candidate_root(self, root: str | Path | None) -> Path:
        if root is not None:
            return Path(root).expanduser()

        from os import environ

        configured_root = environ.get("COPILOT_HOME")
        if configured_root:
            return Path(configured_root).expanduser()
        return Path.home() / ".copilot"

    def _has_directory_read_access(self, path: Path) -> bool:
        mode = path.stat().st_mode
        read_bits = 0o444
        execute_bits = 0o111
        return bool(mode & read_bits) and bool(mode & execute_bits)
