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
