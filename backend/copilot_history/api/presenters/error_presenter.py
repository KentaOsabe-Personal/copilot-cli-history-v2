from copilot_history.api.types import (
    RootFailurePresentationInput,
    ValidationErrorPresentationInput,
)

SESSION_NOT_FOUND_CODE = "session_not_found"
SESSION_NOT_FOUND_MESSAGE = "session was not found"


class ErrorPresenter:
    def from_not_found(self, *, session_id: str) -> dict[str, object]:
        return self._error_body(
            code=SESSION_NOT_FOUND_CODE,
            message=SESSION_NOT_FOUND_MESSAGE,
            details={"session_id": session_id},
        )

    def from_validation(self, error: ValidationErrorPresentationInput) -> dict[str, object]:
        return self._error_body(
            code=error.code,
            message=error.message,
            details=dict(error.details),
        )

    def from_root_failure(self, failure: RootFailurePresentationInput) -> dict[str, object]:
        return self._error_body(
            code=failure.code,
            message=failure.message,
            details={"path": failure.path},
        )

    def _error_body(
        self, *, code: str, message: str, details: dict[str, object]
    ) -> dict[str, object]:
        return {
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        }


__all__ = ["ErrorPresenter"]
