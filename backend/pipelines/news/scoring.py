"""dense / hybrid 점수 계산. 두 사람이 같은 식을 쓰도록 여기 한 곳에서만 정의한다.

dense  : 정규화된 임베딩의 내적(= 코사인 유사도)
sparse : BGE-M3 lexical matching = 질의·문서에 공통으로 있는 토큰의 (질의 가중치 x 문서 가중치) 합
hybrid : W_DENSE * dense + W_SPARSE * sparse   (7 : 3)
주의: sparse 점수는 dense처럼 0~1로 정규화되지 않는다. 실험 전에 정규화 여부를 확정할 것.
"""
W_DENSE, W_SPARSE = 0.7, 0.3


def dense_score(q: list[float], d: list[float]) -> float:
    return sum(a * b for a, b in zip(q, d))


def sparse_score(q: dict[str, float], d: dict[str, float]) -> float:
    return sum(w * d[t] for t, w in q.items() if t in d)


def hybrid_score(dense: float, sparse: float, w_dense: float = W_DENSE, w_sparse: float = W_SPARSE) -> float:
    return w_dense * dense + w_sparse * sparse
