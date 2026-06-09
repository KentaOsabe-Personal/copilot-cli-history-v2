from copilot_history.types import ReadIssue


class IssuePresenter:
    def present(self, issue: ReadIssue) -> dict[str, object]:
        return {
            "code": issue.code,
            "severity": issue.severity,
            "message": issue.message,
            "source_path": issue.source_path,
            "scope": "event" if issue.sequence is not None else "session",
            "event_sequence": issue.sequence,
        }

    def present_many(self, issues: tuple[ReadIssue, ...]) -> list[dict[str, object]]:
        return [self.present(issue) for issue in issues]


__all__ = ["IssuePresenter"]
