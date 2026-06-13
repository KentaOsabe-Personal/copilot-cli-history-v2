from history_read_model.bigquery_errors import classify_bigquery_exception


class _ReasonedError(Exception):
    def __init__(self, reason: str) -> None:
        self.errors = [{"reason": reason}]
        super().__init__(reason)


class _NamedError(Exception):
    pass


class Forbidden(_NamedError):
    pass


class NotFound(_NamedError):
    pass


class BadRequest(_NamedError):
    pass


class TooManyRequests(_NamedError):
    pass


# 概要・目的: BigQuery credentials failure を repository error kind として分類する。
# テストケース: credentials 系 class 名の例外を分類する。
# 期待値: credentials_error になり、query_failed と混同しない。
def test_classify_bigquery_exception_credentials_error() -> None:
    error = classify_bigquery_exception(RuntimeError("DefaultCredentialsError: missing ADC"))

    assert error.kind == "credentials_error"


# 概要・目的: BigQuery permission failure を呼び出し側が識別できる kind に分類する。
# テストケース: Forbidden 相当の例外を分類する。
# 期待値: permission_denied の RepositoryError が返る。
def test_classify_bigquery_exception_permission_denied() -> None:
    error = classify_bigquery_exception(Forbidden("access denied"))

    assert error.kind == "permission_denied"


# 概要・目的: BigQuery schema mismatch を query failure と分離して分類する。
# テストケース: NotFound と invalidQuery reason を分類する。
# 期待値: schema_mismatch の RepositoryError が返る。
def test_classify_bigquery_exception_schema_mismatch() -> None:
    not_found = classify_bigquery_exception(NotFound("table not found"))
    invalid_query = classify_bigquery_exception(_ReasonedError("invalidQuery"))

    assert not_found.kind == "schema_mismatch"
    assert invalid_query.kind == "schema_mismatch"


# 概要・目的: maximum bytes billed 超過を success や一般 query failure と混同しない。
# テストケース: billingTierLimitExceeded reason の例外を分類する。
# 期待値: cost_limit_exceeded の RepositoryError が返る。
def test_classify_bigquery_exception_cost_limit_exceeded() -> None:
    error = classify_bigquery_exception(_ReasonedError("billingTierLimitExceeded"))

    assert error.kind == "cost_limit_exceeded"


# 概要・目的: 未知の BigQuery job failure を安定した query_failed kind に分類する。
# テストケース: rateLimitExceeded など既知分類外の例外を分類する。
# 期待値: query_failed の RepositoryError が返り、message に元例外の内容を保持する。
def test_classify_bigquery_exception_query_failed_fallback() -> None:
    error = classify_bigquery_exception(TooManyRequests("retry later"))

    assert error.kind == "query_failed"
    assert "retry later" in error.message
