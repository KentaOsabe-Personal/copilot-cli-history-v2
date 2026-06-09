from collections.abc import Sequence

from copilot_history.api.response_projection import SessionResponseProjector
from copilot_history.types import NormalizedSession


class SessionIndexPresenter:
    def __init__(self, projector: SessionResponseProjector | None = None) -> None:
        self._projector = projector or SessionResponseProjector()

    def present(self, sessions: Sequence[NormalizedSession]) -> dict[str, object]:
        data = [self._projector.project_summary(session) for session in sessions]
        return {
            "data": data,
            "meta": {
                "count": len(data),
                "partial_results": any(self._is_degraded(summary) for summary in data),
            },
        }

    def _is_degraded(self, summary: dict[str, object]) -> bool:
        return summary.get("degraded") is True


__all__ = ["SessionIndexPresenter"]
