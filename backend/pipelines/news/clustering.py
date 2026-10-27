"""같은 사건 기사 묶기 규칙 (DB 없음, 계산만).

새 기사 1건을 기존 묶음 후보들과 비교해 어디에 넣을지 정한다 (증분 방식).
  - 묶음의 '모든' 기사와 코사인 유사도가 threshold 이상이어야 합류한다 (complete-link).
    하나라도 연결되면 이어 붙이는 방식(single-link)은 A-B-C-D 사슬로 다른 사건까지 묶어
    봐야 할 기사를 숨길 수 있어서 쓰지 않는다.
  - 묶음의 모든 기사가 새 기사와 window(기본 48시간) 안에 발행돼야 한다.
  - 통과한 묶음이 여럿이면 평균 유사도가 가장 높은 묶음, 같으면 id가 작은 묶음.
  - 통과한 묶음이 없으면 새 묶음을 만든다 (None 반환).
  - 여러 사건을 모은 브리핑(톱뉴스·헤드라인·다이제스트)과 같은 틀에 내용만 다른 고정 꼭지
    ([부고]·[인사]·[게시판]·운세·[표] 등)는 아무 묶음과도 비슷하게 나와 잘못 묶이므로 항상 혼자 둔다.
dense 벡터만 쓴다. 0.65·48시간은 실험값이며 경계 구간 사람 확인 후 다시 정한다.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Sequence

import numpy as np

# 대표 기사 선정 시 같은 조건이면 앞쪽 매체를 고른다 (통신사 원문 우선).
SOURCE_PRIORITY = ("yonhap", "mk", "hankyung", "sedaily")
SUMMARY_MIN_CHARS = 40   # 이보다 짧은 요약은 화면 대표로 쓰기에 부족하다고 본다

# 묶지 않고 혼자 두는 제목. 테스트 DB(10/21~22) 결과에서 잘못 묶인 사례를 보고 정했다.
STANDALONE_TITLE_PATTERNS = (
    r"이 시각 헤드라인", r"톱뉴스", r"주요 신문", r"다이제스트", r"모닝\s*브리핑",   # 여러 사건 모음
    r"\[부고\]", r"\[인사\]", r"\[게시판\]", r"\[표\]", r"운세",               # 같은 틀, 다른 내용
    r"오늘의\s*(국감|국회일정|경기|메모|증권가 콜)", r"◇오늘의",
)
_STANDALONE_RE = re.compile("|".join(STANDALONE_TITLE_PATTERNS))


def is_standalone_title(title: str | None) -> bool:
    return bool(title and _STANDALONE_RE.search(title))


@dataclass(frozen=True)
class ClusterParams:
    threshold: float = 0.65
    window: timedelta = timedelta(hours=48)
    candidates: int = 10      # 새 기사와 가까운 기존 기사 몇 건까지 후보로 볼지
    max_size: int = 30        # 묶음 최대 기사 수

    def __post_init__(self):
        if not (isinstance(self.threshold, (int, float)) and math.isfinite(self.threshold)
                and -1 <= self.threshold <= 1):
            raise ValueError("threshold는 -1 이상 1 이하의 실수여야 합니다")
        if self.window <= timedelta(0):
            raise ValueError("window는 0보다 커야 합니다")
        if self.candidates < 1 or self.max_size < 1:
            raise ValueError("candidates와 max_size는 1 이상이어야 합니다")

    @property
    def method_version(self) -> str:
        """배정 당시 규칙. news_cluster_members.method_version에 남겨 기준이 바뀐 뒤에도 구분한다."""
        hours = int(self.window.total_seconds() // 3600)
        return f"complete-link-v2:t{self.threshold:.2f}:w{hours}h:k{self.candidates}:m{self.max_size}"


@dataclass(frozen=True)
class Member:
    news_id: int
    published_at: datetime
    dense: Sequence[float]
    standalone: bool = False   # True면 묶지 않고 혼자 둔다 (is_standalone_title)


@dataclass(frozen=True)
class Candidate:
    """비교할 기존 묶음 1개와 그 소속 기사 전부."""
    cluster_id: int
    members: tuple[Member, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Decision:
    cluster_id: int | None    # None이면 새 묶음
    min_similarity: float | None
    mean_similarity: float | None = None


def _unit(vec: Sequence[float]) -> np.ndarray:
    arr = np.asarray(vec, dtype=np.float64)
    if arr.ndim != 1 or not np.all(np.isfinite(arr)):
        raise ValueError("벡터는 유한한 실수 1차원 배열이어야 합니다")
    norm = float(np.linalg.norm(arr))
    if norm == 0:
        raise ValueError("벡터의 크기가 0입니다")
    return arr / norm


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    ua, ub = _unit(a), _unit(b)
    if ua.shape != ub.shape:
        raise ValueError("두 벡터의 차원이 다릅니다")
    return float(np.clip(ua @ ub, -1.0, 1.0))


def choose_cluster(new: Member, candidates: Sequence[Candidate], params: ClusterParams) -> Decision:
    """새 기사가 들어갈 묶음을 고른다. 입력을 바꾸지 않고, 같은 입력이면 항상 같은 결과를 낸다."""
    if new.standalone:
        return Decision(None, None)
    target = _unit(new.dense)
    best: tuple[float, int, float] | None = None   # (평균 유사도, -cluster_id, 최소 유사도)
    for cand in candidates:
        if not cand.members or len(cand.members) >= params.max_size:
            continue
        if any(m.standalone for m in cand.members):
            continue
        if any(m.news_id == new.news_id for m in cand.members):
            raise ValueError(f"news_id={new.news_id}가 이미 묶음 {cand.cluster_id}에 있습니다")
        if any(abs(m.published_at - new.published_at) > params.window for m in cand.members):
            continue
        sims = [float(np.clip(target @ _unit(m.dense), -1.0, 1.0)) for m in cand.members]
        low = min(sims)
        if low < params.threshold:
            continue
        key = (sum(sims) / len(sims), -cand.cluster_id, low)
        if best is None or key[:2] > best[:2]:
            best = key
    if best is None:
        return Decision(None, None)
    return Decision(-best[1], best[2], best[0])


@dataclass(frozen=True)
class RepresentativeInfo:
    news_id: int
    published_at: datetime
    source_code: str | None
    summary: str | None


def pick_representative(articles: Sequence[RepresentativeInfo]) -> int:
    """화면 대표 기사: 요약이 충분한 기사 우선 → 먼저 발행 → 매체 우선순위 → 작은 id."""
    if not articles:
        raise ValueError("대표를 고를 기사가 없습니다")

    def key(a: RepresentativeInfo):
        has_summary = bool(a.summary and len(a.summary.strip()) >= SUMMARY_MIN_CHARS)
        rank = SOURCE_PRIORITY.index(a.source_code) if a.source_code in SOURCE_PRIORITY else len(SOURCE_PRIORITY)
        return (not has_summary, a.published_at, rank, a.news_id)

    return min(articles, key=key).news_id
