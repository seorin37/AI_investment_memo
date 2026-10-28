import csv

import pytest

from backend.pipelines.news import cluster_eval as ce


def test_sparse_score_and_bucket():
    assert ce.sparse_score({"1": 0.5, "2": 0.2}, {"1": 0.4, "3": 1.0}) == pytest.approx(0.2)
    assert ce.sparse_score('{"1": 1.0}', None) == 0.0
    assert ce.bucket_of(0.55) == "0.55-0.60"
    assert ce.bucket_of(0.6499) == "0.60-0.65"
    assert ce.bucket_of(0.79) == "0.75-0.80"
    assert ce.bucket_of(0.95) == "0.95-1.00" and ce.bucket_of(0.9499) == "0.90-0.95"


def test_sample_pairs_dedupes_and_balances_buckets():
    rows = [(1, 2, 0.56, {}, {}), (2, 1, 0.56, {}, {})]                 # 같은 쌍이 양쪽에서 나옴
    rows += [(10 + i, 100 + i, 0.71, {}, {}) for i in range(30)]
    picked = ce.sample_pairs(rows, per_bucket=5)
    assert sum(1 for p in picked if p[:2] == (1, 2)) == 1
    assert sum(1 for p in picked if ce.bucket_of(p[2]) == "0.70-0.75") == 5
    assert picked == ce.sample_pairs(rows, per_bucket=5)                 # 같은 seed면 같은 결과


def _write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, ce.FIELDS)
        w.writeheader()
        for i, (sim, label) in enumerate(rows, 1):
            w.writerow({**{k: "" for k in ce.FIELDS}, "pair_id": i, "similarity": sim, "label": label})


def test_score_and_recommend(tmp_path):
    path = tmp_path / "pairs.csv"
    _write(path, [(0.58, "different"), (0.62, "different"), (0.66, "same"), (0.68, "different"),
                  (0.72, "same"), (0.76, "same"), (0.79, "same"), (0.60, "unsure"), (0.61, "")])
    labels = ce.load_labels(path)
    assert len(labels) == 7                                              # unsure·빈칸 제외
    by_t = {r["threshold"]: r for r in ce.score(labels)}
    assert by_t[0.55]["false_merge"] == pytest.approx(3 / 7)
    assert by_t[0.65]["false_merge"] == pytest.approx(1 / 5) and by_t[0.65]["missed"] == 0
    assert by_t[0.70]["false_merge"] == 0 and by_t[0.70]["missed"] == pytest.approx(1 / 4)
    assert ce.recommend(ce.score(labels)) == 0.69


def test_load_labels_rejects_unknown_value(tmp_path):
    path = tmp_path / "bad.csv"
    _write(path, [(0.6, "maybe")])
    with pytest.raises(ValueError):
        ce.load_labels(path)


def test_separation_auc():
    assert ce.separation_auc([(0.9, "same"), (0.8, "same"), (0.5, "different")]) == 1.0
    assert ce.separation_auc([(0.5, "same"), (0.9, "different")]) == 0.0
    assert ce.separation_auc([(0.7, "same"), (0.7, "different")]) == 0.5
    assert ce.separation_auc([(0.7, "same")]) is None


def test_colbert_pair_is_symmetric():
    import numpy as np
    a = np.array([[1.0, 0.0], [0.0, 1.0]])
    b = np.array([[1.0, 0.0]])
    assert ce._colbert_pair(a, b) == pytest.approx(ce._colbert_pair(b, a))
    assert ce._colbert_pair(a, a) == pytest.approx(1.0)


def test_add_colbert_keeps_labels_and_compare_uses_it(tmp_path, monkeypatch):
    import numpy as np
    path = tmp_path / "pairs.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, ce.FIELDS)
        w.writeheader()
        for i, (a, b, sim, label) in enumerate([(1, 2, 0.9, "same"), (3, 4, 0.8, "different"), (5, 6, 0.7, "same")], 1):
            w.writerow({**{k: "" for k in ce.FIELDS}, "pair_id": i, "a_id": a, "b_id": b,
                        "similarity": sim, "sparse_score": 0.1 * i, "label": label, "note": f"메모{i}"})
    names = [r["score"] for r in ce.compare(path)]
    assert names[:2] == ["dense", "sparse"] and "colbert" not in names       # colbert 칸이 비면 건너뜀
    assert "dense+0.2×sparse" in names
    vec = {1: [[1, 0]], 2: [[1, 0]], 3: [[1, 0]], 4: [[0, 1]], 5: [[1, 0]], 6: [[0.8, 0.6]]}
    monkeypatch.setattr(ce, "article_texts", lambda conn, ids: {i: f"t{i}" for i in ids})
    encode = lambda texts: [np.array(vec[int(t[1:])], dtype=float) for t in texts]
    assert ce.add_colbert(None, path, encode) == 3
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    assert [r["colbert_score"] for r in rows] == ["1.0000", "0.0000", "0.8000"]
    assert [r["label"] for r in rows] == ["same", "different", "same"] and rows[0]["note"] == "메모1"
    by = {r["score"]: r for r in ce.compare(path)}
    assert by["colbert"]["auc"] == 1.0 and by["dense"]["auc"] == 0.5
