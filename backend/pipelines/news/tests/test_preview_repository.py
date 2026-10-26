"""가짜 connection/cursor와 합성 1,024차원 벡터만 사용한다. 실제 DB 사용 금지."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import re
from types import SimpleNamespace

import pytest

from backend.pipelines.news import preview_repository as repository
from backend.pipelines.news.preview import preview_articles

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = BASE + timedelta(days=1)
KST = timezone(timedelta(hours=9))
COLUMNS = ("news_id", "title", "publisher", "published_at", "url",
           "embedding_news_id", "model", "variant", "dense", "variant_row_count", "incomplete_row_count")


class Status(Enum):
    IDLE = 0
    INTRANS = 2
    INERROR = 3


def db_row(news_id=1, *, hours=1, **changes):
    data = {
        "news_id": news_id, "title": f"합성 기사 {news_id}", "publisher": "합성 매체",
        "published_at": BASE + timedelta(hours=hours), "url": f"https://example.test/{news_id}",
        "embedding_news_id": news_id, "model": "BAAI/bge-m3", "variant": "hybrid",
        "dense": json.dumps([1.0] + [0.0] * 1023),
        "variant_row_count": 1, "incomplete_row_count": 0,
    }
    return {**data, **changes}


def missing(news_id=1, *, other_model=False, hours=1, **changes):
    return db_row(news_id, hours=hours, **{
        "embedding_news_id": None, "model": None, "variant": None, "dense": None,
        "variant_row_count": int(other_model), **changes,
    })


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False
        self.phase = None

    def __enter__(self):
        self.connection.maybe_fail("cursor_enter")
        return self

    def __exit__(self, *args):
        self.closed = True

    def execute(self, sql, params=None):
        assert sql.lstrip().upper().startswith("SELECT")
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|COMMIT|ROLLBACK)\b", sql, re.I)
        self.phase = "guard" if sql == repository.READ_ONLY_SQL else "data"
        self.connection.calls.append((sql, params))
        self.connection.maybe_fail("execute_" + self.phase)

    def fetchone(self):
        assert self.phase == "guard"
        self.connection.maybe_fail("fetchone")
        return self.connection.readonly

    def fetchall(self):
        assert self.phase == "data"
        self.connection.maybe_fail("fetchall")
        if self.connection.end_transaction:
            self.connection.info.transaction_status = Status.IDLE
        return deepcopy(self.connection.rows)


class FakeConnection:
    def __init__(self, rows=(), *, readonly=("on",), autocommit=False, status=Status.INTRANS,
                 fail=None, end_transaction=False):
        self.rows = rows
        self.readonly = readonly
        self.autocommit = autocommit
        self.info = SimpleNamespace(transaction_status=status)
        self.fail = fail
        self.end_transaction = end_transaction
        self.calls = []
        self.cursors = []
        self.control_calls = []

    def maybe_fail(self, stage):
        if self.fail == stage:
            raise RuntimeError("synthetic sensitive driver detail")

    def cursor(self):
        self.maybe_fail("cursor")
        cursor = FakeCursor(self)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.control_calls.append("commit")
        raise AssertionError("commit forbidden")

    def rollback(self):
        self.control_calls.append("rollback")
        raise AssertionError("rollback owned by caller")

    def close(self):
        self.control_calls.append("close")
        raise AssertionError("connection lifetime owned by caller")

    def transaction(self):
        self.control_calls.append("transaction")
        raise AssertionError("transaction creation owned by caller")


def fetch(connection, **options):
    return repository.fetch_preview_rows(connection, BASE, END, **options)


def test_tuple_cursor_returns_exact_preview_contract_without_modifying_rows():
    first = db_row(2, hours=2)
    second = db_row(1)
    raw = [tuple(first[key] for key in COLUMNS), tuple(second[key] for key in COLUMNS)]
    connection = FakeConnection(raw)
    before = deepcopy(raw)
    result = fetch(connection)
    assert [row["news_id"] for row in result] == [1, 2]
    assert all(set(row) == {"news_id", "title", "publisher", "published_at", "url",
                            "model", "variant", "dense"} for row in result)
    assert result[0]["dense"] == [1.0] + [0.0] * 1023
    assert result[0]["title"] == second["title"] and result[0]["publisher"] == second["publisher"]
    assert result[0]["url"] == second["url"]
    assert raw == before and connection.rows == before
    assert connection.control_calls == [] and connection.cursors[0].closed
    assert connection.autocommit is False and connection.info.transaction_status is Status.INTRANS


def test_dict_cursor_and_missing_embedding_feed_existing_preview():
    connection = FakeConnection([db_row(1), missing(2)])
    rows = fetch(connection)
    assert rows[1]["model"] is rows[1]["variant"] is rows[1]["dense"] is None
    report = preview_articles(rows)
    assert report["input_article_count"] == 2 and report["processed_article_count"] == 1
    assert report["missing_embedding_ids"] == [2]
    assert report["groups"][0]["article_ids"] == [1]
    assert report["groups"][0]["representative"]["url"] == "https://example.test/1"
    assert report["groups"][0]["min_similarity"] is None
    assert connection.control_calls == []


@pytest.mark.parametrize("other_model", [False, True])
def test_only_other_variants_or_other_models_preserve_news_as_requested_embedding_missing(other_model):
    # SQL ON의 모델/variant 필터에 의해 미매칭된 LEFT JOIN 행.
    rows = fetch(FakeConnection([missing(other_model=other_model)]))
    assert rows[0]["model"] is rows[0]["variant"] is rows[0]["dense"] is None


def test_model_variant_filters_stay_on_left_join_and_values_are_bound():
    connection = FakeConnection()
    fetch(connection, max_articles=2)
    assert len(connection.calls) == 2
    sql, params = connection.calls[1]
    assert params == ("hybrid", "hybrid", BASE, END, 3, "BAAI/bge-m3", "hybrid", 3)
    assert sql.count("%s") == len(params)
    assert "BAAI/bge-m3" not in sql and "'hybrid'" not in sql
    join = sql.split("LEFT JOIN news_embedding_variants AS v", 1)[1]
    assert re.search(r"ON\s+v.news_id\s*=\s*a.id\s+AND\s+v.model\s*=\s*%s\s+AND\s+v.variant\s*=\s*%s", join)
    assert "LEFT JOIN news_sources" in sql
    assert "v.dense::text AS dense" in sql
    assert "check_v.variant = %s" in sql and "bad_v.variant = %s" in sql
    assert sql.index("LIMIT %s") < sql.index("LEFT JOIN")
    assert "ORDER BY a.published_at, a.id" in sql
    for where in re.findall(r"WHERE(.*?)(?:ORDER BY|\))", sql, re.S):
        assert not re.search(r"\bv\.(?:model|variant)", where)


@pytest.mark.parametrize("change", [{"model": "other"}, {"variant": "dense"}, {"variant": "HYBRID"}])
def test_unexpected_model_or_variant_in_result_is_rejected(change):
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([db_row(**change)]))
    assert caught.value.code == "embedding_mismatch"


@pytest.mark.parametrize("since,until", [
    (BASE, BASE), (END, BASE), (BASE, BASE + timedelta(days=7, microseconds=1)),
])
def test_invalid_or_excessive_window_is_rejected_before_cursor(since, until):
    connection = FakeConnection()
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        repository.fetch_preview_rows(connection, since, until)
    assert caught.value.code == "invalid_window" and connection.calls == [] and connection.cursors == []


@pytest.mark.parametrize("since,until", [
    (BASE.replace(tzinfo=None), END), (BASE, END.replace(tzinfo=None)),
    (BASE.isoformat(), END), (BASE, None), (1, END),
])
def test_timezone_aware_datetime_arguments_are_required(since, until):
    connection = FakeConnection()
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        repository.fetch_preview_rows(connection, since, until)
    assert caught.value.code == "invalid_time" and connection.calls == []


def test_query_boundaries_normalize_to_utc_and_seven_days_is_allowed():
    connection = FakeConnection([db_row(published_at=BASE.astimezone(KST))])
    result = repository.fetch_preview_rows(
        connection, BASE.astimezone(KST), (BASE + timedelta(days=7)).astimezone(KST))
    assert connection.calls[1][1][2:4] == (BASE, BASE + timedelta(days=7))
    assert result[0]["published_at"] == BASE and result[0]["published_at"].tzinfo is timezone.utc
    assert repository.MAX_QUERY_SPAN == timedelta(days=7)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "2", None, 101, 10 ** 1000, "1; DELETE"])
def test_invalid_or_excessive_article_limits_fail_before_query(limit):
    connection = FakeConnection()
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(connection, max_articles=limit)
    assert caught.value.code == "invalid_limit" and connection.calls == []


@pytest.mark.parametrize("options", [
    {"model": "other"}, {"model": None}, {"variant": "dense"}, {"variant": None},
    {"model": "BAAI/bge-m3'; DELETE FROM news_articles; --"},
])
def test_unsupported_embedding_options_are_rejected_without_sql(options):
    connection = FakeConnection()
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(connection, **options)
    assert caught.value.code == "invalid_embedding_option" and connection.calls == []


def test_limit_probe_refuses_silent_truncation_and_exact_limit_is_allowed():
    rows = [db_row(1), missing(2)]
    result = fetch(FakeConnection(rows), max_articles=2)
    assert len(result) == 2
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection(rows), max_articles=1)
    assert caught.value.code == "limit_exceeded"
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection(rows + [missing(3)]), max_articles=1)
    assert caught.value.code == "limit_exceeded"


def test_default_article_limit_has_a_bounded_probe():
    connection = FakeConnection()
    assert fetch(connection) == []
    assert connection.calls[1][1][4] == connection.calls[1][1][-1] == 101


@pytest.mark.parametrize("raw", [
    db_row(variant_row_count=2),
    missing(variant_row_count=2),
])
def test_counter_catches_duplicates_even_when_model_filter_hides_rows(raw):
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([raw]))
    assert caught.value.code == "embedding_conflict"


def test_duplicate_returned_article_ids_are_not_silently_selected_even_at_limit():
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([db_row(), db_row()]), max_articles=1)
    assert caught.value.code == "duplicate_article"


@pytest.mark.parametrize("changes", [
    {"embedding_news_id": 2}, {"embedding_news_id": True}, {"embedding_news_id": "1"},
    {"variant_row_count": 0},
])
def test_conflicting_embedding_article_id_or_count_is_rejected(changes):
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([db_row(**changes)]))
    assert caught.value.code == "embedding_conflict"


@pytest.mark.parametrize("field", ["model", "variant", "dense"])
def test_partial_null_existing_embedding_is_an_error(field):
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([db_row(**{field: None})]))
    assert caught.value.code == "incomplete_embedding"


def test_all_null_fields_on_an_existing_embedding_row_are_not_missing():
    raw = db_row(model=None, variant=None, dense=None)
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([raw]))
    assert caught.value.code == "incomplete_embedding"


@pytest.mark.parametrize("change", [
    {"model": "BAAI/bge-m3"}, {"variant": "hybrid"}, {"dense": "[1]"},
])
def test_partial_join_fields_without_embedding_id_are_not_corrected(change):
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([missing(**change)]))
    assert caught.value.code == "incomplete_embedding"


def test_filtered_out_malformed_hybrid_is_not_disguised_as_missing():
    raw = missing(other_model=True, incomplete_row_count=1)
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([raw]))
    assert caught.value.code == "incomplete_embedding"


@pytest.mark.parametrize("field,value", [
    ("variant_row_count", None), ("variant_row_count", True), ("variant_row_count", -1),
    ("variant_row_count", "1"), ("incomplete_row_count", None), ("incomplete_row_count", True),
    ("incomplete_row_count", -1), ("incomplete_row_count", 2),
])
def test_invalid_integrity_counters_are_rejected(field, value):
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([db_row(**{field: value})]))
    assert caught.value.code == "invalid_result"


@pytest.mark.parametrize("raw", [
    "not-json", "[]", "[1,2]", json.dumps([0.0] * 1024), json.dumps([1.0] * 1023),
    json.dumps([1.0] * 1025), json.dumps([True] + [0.0] * 1023),
    json.dumps(["1"] + [0.0] * 1023), json.dumps([None] + [0.0] * 1023),
    json.dumps([float("nan")] + [0.0] * 1023),
    json.dumps([float("inf")] + [0.0] * 1023),
    json.dumps([1.7e308] * 1024), "null", '{"a":1}', '"vector"', [1.0] * 1024,
])
def test_malformed_or_invalid_pgvector_text_is_rejected(raw):
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([db_row(dense=raw)]))
    assert caught.value.code == "invalid_dense"


@pytest.mark.parametrize("field,value", [
    ("news_id", True), ("news_id", 0), ("news_id", "1"), ("title", None),
    ("title", " "), ("publisher", None), ("publisher", ""), ("url", None), ("url", " "),
])
def test_metadata_is_not_fabricated_for_incomplete_article_or_source(field, value):
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([db_row(**{field: value})]))
    assert caught.value.code == "invalid_metadata"


@pytest.mark.parametrize("timestamp,code", [
    (BASE.replace(tzinfo=None), "invalid_time"), (None, "invalid_time"),
    (BASE.isoformat(), "invalid_time"), (BASE - timedelta(seconds=1), "outside_window"),
    (END, "outside_window"),
])
def test_returned_timestamp_must_be_aware_and_inside_half_open_window(timestamp, code):
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([db_row(published_at=timestamp)]))
    assert caught.value.code == code


@pytest.mark.parametrize("raw", [None, [], (1, 2), {"news_id": 1}])
def test_malformed_result_row_has_clear_error(raw):
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection([raw]))
    assert caught.value.code == "invalid_result"


def test_unexpected_fetchall_type_is_rejected():
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(FakeConnection(None))
    assert caught.value.code == "invalid_result"


@pytest.mark.parametrize("readonly", [("off",), (True,), (None,), ("ON",)])
def test_readonly_must_be_confirmed_by_server_before_article_select(readonly):
    connection = FakeConnection(readonly=readonly)
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(connection)
    assert caught.value.code == "read_only_required"
    assert len(connection.calls) == 1 and connection.control_calls == []
    assert connection.cursors[0].closed


@pytest.mark.parametrize("readonly", [None, (), {}, ("on", "extra")])
def test_unprovable_readonly_response_refuses_data_query(readonly):
    connection = FakeConnection(readonly=readonly)
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(connection)
    assert caught.value.code == "invalid_result" and len(connection.calls) == 1


@pytest.mark.parametrize("autocommit,status", [
    (True, Status.INTRANS), (None, Status.INTRANS), (False, Status.IDLE),
    (False, Status.INERROR), (False, None), (False, 2),
])
def test_active_non_autocommit_transaction_is_required(autocommit, status):
    connection = FakeConnection(autocommit=autocommit, status=status)
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(connection)
    assert caught.value.code == "transaction_required" and connection.calls == []


def test_unknown_connection_interface_is_refused_without_guessing():
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(object())
    assert caught.value.code == "transaction_required"


def test_dict_row_readonly_check_and_connection_state_are_preserved():
    connection = FakeConnection([db_row()], readonly={"transaction_read_only": "on"})
    assert len(fetch(connection)) == 1
    assert len(connection.calls) == 2
    assert connection.control_calls == [] and connection.autocommit is False


def test_transaction_end_during_select_is_detected():
    connection = FakeConnection([db_row()], end_transaction=True)
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(connection)
    assert caught.value.code == "transaction_required" and connection.control_calls == []


@pytest.mark.parametrize("stage", ["cursor", "cursor_enter", "execute_guard", "fetchone", "execute_data", "fetchall"])
def test_query_failures_are_sanitized_not_retried_or_committed(stage):
    connection = FakeConnection([db_row()], fail=stage)
    with pytest.raises(repository.PreviewRepositoryError) as caught:
        fetch(connection)
    error = caught.value.as_dict()
    assert error["code"] == "query_failed" and error["cause_type"] == "RuntimeError"
    assert "synthetic sensitive driver detail" not in str(caught.value)
    assert "synthetic sensitive driver detail" not in json.dumps(error)
    assert caught.value.__suppress_context__ is True
    assert connection.control_calls == []
    assert len(connection.calls) <= 2
    if connection.cursors and stage != "cursor_enter":
        assert connection.cursors[0].closed


def test_result_order_is_deterministic_by_utc_timestamp_then_id():
    original = [db_row(3, hours=1), db_row(1, hours=2), missing(2, hours=1)]
    before = deepcopy(original)
    first = fetch(FakeConnection(original))
    second = fetch(FakeConnection(list(reversed(original))))
    assert first == second and [row["news_id"] for row in first] == [2, 3, 1]
    assert original == before


def test_repository_does_not_call_clustering(monkeypatch):
    from backend.pipelines.news import preview
    monkeypatch.setattr(preview, "cluster_articles", lambda *a, **k: pytest.fail("repository must not cluster"))
    assert len(fetch(FakeConnection([db_row()]))) == 1
