"""임베더 단위 테스트. 실제 DB·모델 대신 mock만 사용한다."""

import json
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

from backend.pipelines.news import embedder


SINCE = datetime(2026, 10, 21, tzinfo=timezone.utc)
UNTIL = datetime(2026, 10, 23, tzinfo=timezone.utc)


def vector():
    return [0.1] * 1024


def embedding():
    return vector(), {"1": 0.5}


def connection(rows=()):
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = list(rows)
    cur.rowcount = 1
    return conn, cur


def insert_calls(cur):
    return [call for call in cur.execute.call_args_list if "INSERT INTO" in call.args[0]]


@pytest.fixture
def fake_model(monkeypatch):
    """모델 모듈을 먼저 대체하므로 실제 FlagEmbedding도 import하지 않는다."""
    model = Mock()
    model.encode.side_effect = lambda texts, **kwargs: {
        "dense_vecs": [vector() for _ in texts],
        "lexical_weights": [{"1": 0.5} for _ in texts],
    }
    factory = Mock(return_value=model)
    monkeypatch.setitem(sys.modules, "FlagEmbedding", SimpleNamespace(BGEM3FlagModel=factory))
    monkeypatch.setattr(embedder, "_patch_dtype_compat", Mock())
    return factory, model


def test_pending_articles_preserves_old_positional_arguments():
    rows = [(10, "제목", None)]
    conn, cur = connection(rows)
    assert embedder.pending_articles(conn, "hybrid", SINCE, UNTIL, 5, False) == rows
    sql, params = cur.execute.call_args.args
    assert "AND EXISTS (SELECT 1 FROM news_stocks" in sql
    assert "a.id = ANY" not in sql
    assert params == [SINCE, UNTIL, "hybrid", 5]


def test_pending_articles_binds_selected_ids_before_limit_and_keeps_exclusion():
    conn, cur = connection([(10, "제목", None)])
    embedder.pending_articles(conn, "hybrid", SINCE, UNTIL, 2, True, news_ids=[10, 59, 10])
    sql, params = cur.execute.call_args.args
    assert "a.id = ANY(%s)" in sql
    assert sql.index("a.id = ANY(%s)") < sql.index("ORDER BY") < sql.index("LIMIT %s")
    assert "NOT EXISTS (SELECT 1 FROM news_embedding_variants" in sql
    assert "v.news_id = a.id AND v.variant = %s" in sql
    assert "AND EXISTS (SELECT 1 FROM news_stocks" not in sql
    assert params == [SINCE, UNTIL, "hybrid", [10, 59], 2]


def test_empty_ids_do_not_open_cursor_or_invoke_encoder():
    conn, cur = connection()
    encode = Mock(spec=[])
    assert embedder.pending_articles(conn, "hybrid", SINCE, UNTIL, news_ids=[]) == []
    assert embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL, news_ids=[]) == 0
    conn.cursor.assert_not_called()
    encode.assert_not_called()


@pytest.mark.parametrize("ids", [["10"], [True], [0], [-1], ["10); DROP TABLE news_articles; --"]])
def test_invalid_ids_rejected_without_query(ids):
    conn, _ = connection()
    with pytest.raises(ValueError, match="news_ids"):
        embedder.pending_articles(conn, "hybrid", SINCE, UNTIL, news_ids=ids)
    conn.cursor.assert_not_called()


def test_all_already_embedded_does_not_recompute_or_write():
    # Mock the DB response to the NOT EXISTS query: no pending rows.
    conn, cur = connection()
    encode = Mock(spec=[])
    assert embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL, news_ids=[10, 59]) == 0
    sql, params = cur.execute.call_args.args
    assert "v.news_id = a.id AND v.variant = %s" in sql
    assert params == [SINCE, UNTIL, "hybrid", [10, 59]]
    encode.assert_not_called()
    assert not insert_calls(cur)


def test_only_pending_selected_rows_encoded_and_saved():
    # 59 already has hybrid; the DB returns only the pending ID 10.
    conn, cur = connection([(10, "제목", "요약")])
    encode = Mock(spec=[], return_value=[embedding()])
    assert embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL,
                                 include_untagged=True, news_ids=[10, 59]) == 1
    encode.assert_called_once_with(["제목\n요약"])
    writes = insert_calls(cur)
    assert len(writes) == 1
    sql, params = writes[0].args
    assert "ON CONFLICT DO NOTHING" in sql
    assert params[0:2] == (10, "hybrid")
    assert len(json.loads(params[2])) == 1024
    assert json.loads(params[3]) == {"1": 0.5}


def test_old_embed_window_call_keeps_default_batch_and_dense_support():
    conn, cur = connection([(i, f"제목{i}", None) for i in range(1, 18)])
    encode = Mock(spec=[], side_effect=lambda texts: [(vector(), None) for _ in texts])
    # Mock callables have dynamic attributes; use a plain legacy callable.
    def legacy_encode(texts):
        return encode(texts)
    assert embedder.embed_window(conn, "dense", legacy_encode, SINCE, UNTIL, None, True) == 17
    assert [len(call.args[0]) for call in encode.call_args_list] == [16, 1]
    assert all(call.args[1][3] is None for call in insert_calls(cur))


@pytest.mark.parametrize("factory_batch,outer_batch,expected", [(16, None, 16), (2, None, 2), (16, 2, 2), (2, 4, 4)])
def test_inner_and_outer_batches_stay_consistent(fake_model, factory_batch, outer_batch, expected):
    factory, model = fake_model
    encode = embedder.make_bge_m3_encoder("hybrid", True, batch_size=factory_batch)
    conn, _ = connection([(i, f"제목{i}", None) for i in range(1, 6)])
    assert embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL, batch_size=outer_batch) == 5
    factory.assert_called_once_with(embedder.MODEL_NAME, use_fp16=True)
    lengths = [len(call.args[0]) for call in model.encode.call_args_list]
    assert lengths == [min(expected, 5 - i) for i in range(0, 5, expected)]
    assert all(call.kwargs["batch_size"] == expected for call in model.encode.call_args_list)
    assert all(call.kwargs["return_sparse"] and call.kwargs["max_length"] == 512
               for call in model.encode.call_args_list)


def test_encoder_old_call_defaults_and_dense_mode(fake_model):
    factory, model = fake_model
    encode = embedder.make_bge_m3_encoder("dense")
    assert encode(["제목"]) == [(vector(), None)]
    factory.assert_called_once_with(embedder.MODEL_NAME, use_fp16=False)
    assert model.encode.call_args.kwargs["batch_size"] == 16
    assert model.encode.call_args.kwargs["return_sparse"] is False


@pytest.mark.parametrize("bad_size", [0, -1, True, 1.5])
def test_invalid_batch_size_prevents_model_load_and_query(fake_model, bad_size):
    factory, _ = fake_model
    with pytest.raises(ValueError, match="batch_size"):
        embedder.make_bge_m3_encoder("hybrid", batch_size=bad_size)
    factory.assert_not_called()
    conn, _ = connection()
    with pytest.raises(ValueError, match="batch_size"):
        embedder.embed_window(conn, "hybrid", lambda texts: [], SINCE, UNTIL, batch_size=bad_size)
    conn.cursor.assert_not_called()


def test_default_model_error_retries_individually_and_skips_failed_article():
    conn, cur = connection([(1, "좋은 기사", None), (2, "오류 기사", None)])
    encode = Mock(spec=[], side_effect=[RuntimeError("batch error"), [embedding()], RuntimeError("article error")])
    assert embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL) == 1
    assert encode.call_count == 3
    assert [call.args[1][0] for call in insert_calls(cur)] == [1]


def test_fail_fast_propagates_original_error_without_retry_or_save():
    conn, cur = connection([(1, "제목", None), (2, "제목2", None)])
    error = RuntimeError("CUDA out of memory")
    encode = Mock(spec=[], side_effect=error)
    with pytest.raises(RuntimeError) as caught:
        embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL, fail_fast=True, batch_size=2)
    assert caught.value is error
    encode.assert_called_once()
    assert not insert_calls(cur)


@pytest.mark.parametrize("failure", [RuntimeError("model failed"), embedder.EmbeddingValidationError("count mismatch")])
def test_later_batch_failure_saves_nothing(failure):
    conn, cur = connection([(1, "제목", None), (2, "제목2", None)])
    encode = Mock(spec=[], side_effect=[[embedding()], failure])
    with pytest.raises(type(failure)):
        embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL, batch_size=1, fail_fast=True)
    assert encode.call_count == 2
    assert not insert_calls(cur)


@pytest.mark.parametrize("count", [0, 1, 3])
def test_output_count_mismatch_does_not_retry_or_save(count):
    conn, cur = connection([(1, "제목", None), (2, "제목2", None)])
    encode = Mock(spec=[], return_value=[embedding() for _ in range(count)])
    with pytest.raises(embedder.EmbeddingValidationError, match="count"):
        embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL)
    encode.assert_called_once()
    assert not insert_calls(cur)


def test_single_article_retry_also_checks_output_count():
    conn, cur = connection([(1, "제목", None)])
    encode = Mock(spec=[], side_effect=[RuntimeError("batch failed"), []])
    with pytest.raises(embedder.EmbeddingValidationError, match="count"):
        embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL)
    assert encode.call_count == 2
    assert not insert_calls(cur)


@pytest.mark.parametrize("field", ["dense_vecs", "lexical_weights"])
def test_model_output_count_checked_before_zip(fake_model, field):
    _, model = fake_model
    model.encode.side_effect = None
    out = {"dense_vecs": [vector(), vector()], "lexical_weights": [{}, {}]}
    out[field] = out[field][:1]
    model.encode.return_value = out
    encode = embedder.make_bge_m3_encoder("hybrid")
    conn, cur = connection([(1, "제목", None), (2, "제목2", None)])
    with pytest.raises(embedder.EmbeddingValidationError, match="count"):
        embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL)
    model.encode.assert_called_once()
    assert not insert_calls(cur)


@pytest.mark.parametrize("out", [
    None, {}, {"dense_vecs": [vector()]},
    {"dense_vecs": [["invalid"] * 1024], "lexical_weights": [{}]},
    {"dense_vecs": [vector()], "lexical_weights": [[]]},
])
def test_malformed_model_output_is_not_retried(fake_model, out):
    _, model = fake_model
    model.encode.side_effect = None
    model.encode.return_value = out
    encode = embedder.make_bge_m3_encoder("hybrid")
    conn, cur = connection([(1, "제목", None)])
    with pytest.raises(embedder.EmbeddingValidationError):
        embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL)
    model.encode.assert_called_once()
    assert not insert_calls(cur)


def test_missing_output_list_is_not_retried_or_saved():
    conn, cur = connection([(1, "제목", None)])
    encode = Mock(spec=[], return_value=None)
    with pytest.raises(embedder.EmbeddingValidationError):
        embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL)
    encode.assert_called_once()
    assert not insert_calls(cur)


@pytest.mark.parametrize("bad_dense", [
    [0.1] * 1023, [0.1] * 1025, [0.0] * 1024,
    [float("nan")] + [0.1] * 1023, [float("inf")] + [0.1] * 1023,
    [float("-inf")] + [0.1] * 1023, [True] * 1024, ["invalid"] * 1024, None,
])
def test_invalid_dense_prevents_all_saves(bad_dense):
    conn, cur = connection([(1, "제목", None), (2, "제목2", None)])
    encode = Mock(spec=[], side_effect=[[embedding()], [(bad_dense, {"1": 0.5})]])
    with pytest.raises(embedder.EmbeddingValidationError):
        embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL, batch_size=1)
    assert not insert_calls(cur)


@pytest.mark.parametrize("bad_sparse", [
    None, [], {1: 0.5}, {"": 0.5}, {"1": float("nan")}, {"1": float("inf")},
    {"1": -0.5}, {"1": "invalid"}, {"1": True},
])
def test_invalid_hybrid_sparse_prevents_all_saves(bad_sparse):
    conn, cur = connection([(1, "제목", None), (2, "제목2", None)])
    encode = Mock(spec=[], side_effect=[[embedding()], [(vector(), bad_sparse)]])
    with pytest.raises(embedder.EmbeddingValidationError):
        embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL, batch_size=1)
    assert not insert_calls(cur)


def test_empty_sparse_dict_is_valid_and_not_null():
    conn, cur = connection([(1, "제목", None)])
    assert embedder.embed_window(conn, "hybrid", lambda texts: [(vector(), {})], SINCE, UNTIL) == 1
    assert insert_calls(cur)[0].args[1][3] == "{}"


@pytest.mark.parametrize("bad_result", [None, (), (vector(),), (vector(), {}, "extra")])
def test_malformed_result_does_not_retry_or_save(bad_result):
    conn, cur = connection([(1, "제목", None)])
    encode = Mock(spec=[], return_value=[bad_result])
    with pytest.raises(embedder.EmbeddingValidationError):
        embedder.embed_window(conn, "hybrid", encode, SINCE, UNTIL)
    encode.assert_called_once()
    assert not insert_calls(cur)
