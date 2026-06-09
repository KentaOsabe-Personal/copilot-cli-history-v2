from copilot_history.api.response_projection import SessionResponseProjector
from copilot_history.types import NormalizedSession


class SessionDetailPresenter:
    def __init__(self, projector: SessionResponseProjector | None = None) -> None:
        self._projector = projector or SessionResponseProjector()

    def present(
        self, session: NormalizedSession, *, include_raw: bool = False
    ) -> dict[str, object]:
        return {
            "data": self._projector.project_detail(session, include_raw=include_raw),
        }


__all__ = ["SessionDetailPresenter"]
