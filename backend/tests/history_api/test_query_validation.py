from datetime import UTC, datetime

from django.http import QueryDict

from history_api.query_validation import parse_include_raw, validate_session_list_query


# 概要・目的: 有効な一覧 query が repository criteria に変換される契約を守る。
# テストケース: from/to/search/limit を含む query string を validation する。
# 期待値: timezone-aware datetime、検索語、limit を持つ criteria が返る。
def test_validate_session_list_query_returns_repository_criteria() -> None:
    result = validate_session_list_query(
        QueryDict(
            "from=2026-06-01T00:00:00Z&to=2026-06-30T23:59:59Z&search=hello&limit=25"
        )
    )

    assert not isinstance(result, Exception)
    assert result.criteria.from_datetime == datetime(2026, 6, 1, tzinfo=UTC)
    assert result.criteria.to_datetime == datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC)
    assert result.criteria.search_term == "hello"
    assert result.criteria.limit == 25


# 概要・目的: 日時として解釈できない from/to を frontend 互換 details に変換する。
# テストケース: from に不正な日時文字列を指定する。
# 期待値: field、reason、value を持つ validation error が返る。
def test_validate_session_list_query_rejects_invalid_datetime() -> None:
    result = validate_session_list_query(QueryDict("from=not-a-date&to=2026-06-30T00:00:00Z"))

    assert isinstance(result, Exception)
    assert result.field == "from"
    assert result.reason == "invalid_datetime"
    assert result.value == "not-a-date"


# 概要・目的: 一覧 query の期間順序が無効な場合に validation error として扱う。
# テストケース: from が to より後の日時になる query を指定する。
# 期待値: range field と from_after_to reason が返る。
def test_validate_session_list_query_rejects_invalid_range() -> None:
    result = validate_session_list_query(
        QueryDict("from=2026-07-01T00:00:00Z&to=2026-06-30T00:00:00Z")
    )

    assert isinstance(result, Exception)
    assert result.field == "range"
    assert result.reason == "from_after_to"


# 概要・目的: limit の許可範囲外指定を validation error として扱う。
# テストケース: limit=0 と API 上限超過の limit を validation する。
# 期待値: どちらも limit field の positive_integer_required reason が返る。
def test_validate_session_list_query_rejects_limit_out_of_range() -> None:
    zero = validate_session_list_query(
        QueryDict("from=2026-06-01T00:00:00Z&to=2026-06-30T00:00:00Z&limit=0")
    )
    too_large = validate_session_list_query(
        QueryDict("from=2026-06-01T00:00:00Z&to=2026-06-30T00:00:00Z&limit=501")
    )

    assert isinstance(zero, Exception)
    assert zero.field == "limit"
    assert zero.reason == "positive_integer_required"
    assert isinstance(too_large, Exception)
    assert too_large.field == "limit"
    assert too_large.reason == "positive_integer_required"


# 概要・目的: search の表示不適切な入力を validation error として扱う。
# テストケース: 制御文字を含む search と長すぎる search を validation する。
# 期待値: search field の control_character または too_long reason が返る。
def test_validate_session_list_query_rejects_invalid_search() -> None:
    control = validate_session_list_query(
        QueryDict("from=2026-06-01T00:00:00Z&to=2026-06-30T00:00:00Z&search=hello%01")
    )
    too_long = validate_session_list_query(
        QueryDict(f"from=2026-06-01T00:00:00Z&to=2026-06-30T00:00:00Z&search={'x' * 201}")
    )

    assert isinstance(control, Exception)
    assert control.field == "search"
    assert control.reason == "control_character"
    assert isinstance(too_long, Exception)
    assert too_long.field == "search"
    assert too_long.reason == "too_long"


# 概要・目的: raw opt-in query が文字列 true のみに限定される契約を守る。
# テストケース: include_raw 未指定、true、True、1 を parse する。
# 期待値: true だけが True になり、それ以外は False になる。
def test_parse_include_raw_only_accepts_lowercase_true() -> None:
    assert parse_include_raw(QueryDict("")) is False
    assert parse_include_raw(QueryDict("include_raw=true")) is True
    assert parse_include_raw(QueryDict("include_raw=True")) is False
    assert parse_include_raw(QueryDict("include_raw=1")) is False
