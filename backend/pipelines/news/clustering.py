"""같은 사건 기사 묶기 규칙 (DB 없음, 계산만).

새 기사 1건을 기존 묶음 후보들과 비교해 어디에 넣을지 정한다 (증분 방식).
  - 묶음의 '모든' 기사와 코사인 유사도가 threshold 이상이어야 합류한다 (complete-link).
    하나라도 연결되면 이어 붙이는 방식(single-link)은 A-B-C-D 사슬로 다른 사건까지 묶어
    봐야 할 기사를 숨길 수 있어서 쓰지 않는다.
  - 묶음의 모든 기사가 새 기사와 window(기본 24시간) 안에 발행돼야 한다.
  - 통과한 묶음이 여럿이면 평균 유사도가 가장 높은 묶음, 같으면 id가 작은 묶음.
  - 통과한 묶음이 없으면 새 묶음을 만든다 (None 반환).
  - 여러 사건을 모은 브리핑(톱뉴스·헤드라인·다이제스트)과 같은 틀에 내용만 다른 고정 꼭지
    ([부고]·[인사]·[게시판]·운세·[표] 등)는 아무 묶음과도 비슷하게 나와 잘못 묶이므로 항상 혼자 둔다.
기준은 "같은 사건(엄격)"이다. 유사도만으로는 같은 이야기의 다른 일(다른 날 후속, 다른 지역·회사)을 못 가르므로
dense를 통과한 묶음에 두 단계를 더 둔다 (v4).
  1. 규칙 검사 (외부 요청 없음): 묶음 기사 중 하나라도 새 기사와 ① 발행일(한국 시간)이 다르거나
     ② 제목의 지역(시·도)이 겹치지 않거나 ③ 제목의 금액(억·조)이 겹치지 않으면 합류하지 않는다.
  2. LLM 판정 (judge를 넘겼을 때만): 최소 유사도가 llm_below 미만인 애매한 묶음은 LLM에 같은 사건인지 묻는다.
     '다르다'거나 답을 못 받으면 합류하지 않는다 (잘못 숨기는 것이 중복보다 위험).
     judge가 없으면 규칙까지만 보고 합류한다.
0.70·0.85는 임시 정답 105쌍으로 정한 실험값이며 사람 확인 후 다시 정한다. 시간 범위는 24시간이다
(48시간이면 다음 날의 반대 방향 시황 같은 다른 날의 일까지 묶였다).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Sequence

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


KST = timezone(timedelta(hours=9))

# 제목의 시·도. 긴 이름은 짧은 이름으로 모은다. '경기'는 경제 뜻(경기 침체)이 많아 지역으로 쓰인 꼴만 본다.
_REGION_FULL = {"충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전북특별자치도": "전북",
                "전라남도": "전남", "경상북도": "경북", "경상남도": "경남", "강원도": "강원",
                "강원특별자치도": "강원", "제주도": "제주", "경기도": "경기"}
_REGION_RE = re.compile("|".join(
    [*sorted(_REGION_FULL, key=len, reverse=True),
     "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "강원", "충북", "충남",
     "전북", "전남", "경북", "경남", "제주", r"경기(?=\s?(?:북부|남부|\d|지역|일대|·))", r"(?<=·)경기"]))
_AMOUNT_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(조|억)")


def title_regions(title: str | None) -> frozenset[str]:
    return frozenset(_REGION_FULL.get(m, m) for m in _REGION_RE.findall(title or ""))


def title_amounts(title: str | None) -> frozenset[float]:
    """제목의 금액을 억 단위로 (예: '1조2천억'은 1조만 잡힘 — 겹침 판정용이라 충분하다)."""
    out = set()
    for num, unit in _AMOUNT_RE.findall(title or ""):
        value = float(num.replace(",", ""))
        out.add(value * 10000 if unit == "조" else value)
    return frozenset(out)


def rule_conflict(a: "Member", b: "Member", params: "ClusterParams") -> str | None:
    """두 기사가 같은 사건일 수 없는 이유 (없으면 None). 지역·금액은 양쪽 제목에 모두 있을 때만 비교한다."""
    if params.same_day and a.published_at.astimezone(KST).date() != b.published_at.astimezone(KST).date():
        return "day"
    ra, rb = title_regions(a.title), title_regions(b.title)
    if ra and rb and not ra & rb:
        return "region"
    ma, mb = title_amounts(a.title), title_amounts(b.title)
    if ma and mb and not ma & mb:
        return "amount"
    return None


@dataclass(frozen=True)
class ClusterParams:
    threshold: float = 0.70
    window: timedelta = timedelta(hours=24)
    candidates: int = 10      # 새 기사와 가까운 기존 기사 몇 건까지 후보로 볼지
    max_size: int = 30        # 묶음 최대 기사 수
    same_day: bool = True     # 발행일(한국 시간)이 다르면 묶지 않는다
    llm_below: float = 0.85   # 최소 유사도가 이 값 미만이면 LLM에 묻는다 (judge가 있을 때)
    llm_per_article: int = 2  # 기사 1건당 LLM에 물어볼 최대 묶음 수
    use_llm: bool = False     # 기록용: 배정에 judge를 썼는지 (method_version에 남김)

    def __post_init__(self):
        if not (isinstance(self.threshold, (int, float)) and math.isfinite(self.threshold)
                and -1 <= self.threshold <= 1):
            raise ValueError("threshold는 -1 이상 1 이하의 실수여야 합니다")
        if self.window <= timedelta(0):
            raise ValueError("window는 0보다 커야 합니다")
        if self.candidates < 1 or self.max_size < 1 or self.llm_per_article < 1:
            raise ValueError("candidates·max_size·llm_per_article는 1 이상이어야 합니다")
        if not self.threshold <= self.llm_below <= 1:
            raise ValueError("llm_below는 threshold 이상 1 이하여야 합니다")

    @property
    def method_version(self) -> str:
        """배정 당시 규칙. news_cluster_members.method_version에 남겨 기준이 바뀐 뒤에도 구분한다."""
        hours = int(self.window.total_seconds() // 3600)
        day = ":day" if self.same_day else ""
        llm = f"llm{self.llm_below:.2f}" if self.use_llm else "nollm"
        return (f"complete-link-v4:t{self.threshold:.2f}:w{hours}h:k{self.candidates}:m{self.max_size}"
                f"{day}:rules:{llm}")


@dataclass(frozen=True)
class Member:
    news_id: int
    published_at: datetime
    dense: Sequence[float]
    standalone: bool = False   # True면 묶지 않고 혼자 둔다 (is_standalone_title)
    title: str = ""
    summary: str | None = None


@dataclass(frozen=True)
class Candidate:
    """비교할 기존 묶음 1개와 그 소속 기사 전부."""
    cluster_id: int
    members: tuple[Member, ...] = field(default_factory=tuple)


# Decision.decided_by — news_cluster_members.decided_by에 그대로 저장한다.
#   합류: dense(최소 유사도 llm_below 이상이거나 judge 없음) / llm-same
#   새 묶음: new(유사도 통과 묶음 없음) / rule(규칙에 걸림) / llm-different / llm-unavailable(답 못 받음)
#   새 묶음의 이유는 가장 유력한(평균 유사도 최고) 묶음이 왜 안 됐는지다.
DECIDED_BY = ("dense", "llm-same", "new", "rule", "llm-different", "llm-unavailable")

# judge(새 기사, 묶음 기사들) → True(같은 사건) / False(다름) / None(답 못 받음)
Judge = Callable[["Member", Sequence["Member"]], "bool | None"]


@dataclass(frozen=True)
class Decision:
    cluster_id: int | None    # None이면 새 묶음
    min_similarity: float | None
    mean_similarity: float | None = None
    decided_by: str = "new"


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


def choose_cluster(new: Member, candidates: Sequence[Candidate], params: ClusterParams,
                   judge: Judge | None = None) -> Decision:
    """새 기사가 들어갈 묶음을 고른다. 입력을 바꾸지 않고, judge가 없으면 같은 입력에 항상 같은 결과를 낸다."""
    if new.standalone:
        return Decision(None, None)
    target = _unit(new.dense)
    passed: list[tuple[float, int, float, Candidate]] = []   # (평균 유사도, -cluster_id, 최소 유사도, 묶음)
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
        passed.append((sum(sims) / len(sims), -cand.cluster_id, low, cand))
    passed.sort(key=lambda p: p[:2], reverse=True)   # 평균 유사도 높은 순, 같으면 id 작은 순

    reason = "new"
    asked = 0
    for mean, neg_id, low, cand in passed:
        if any(rule_conflict(new, m, params) for m in cand.members):
            reason = "rule" if reason == "new" else reason
            continue
        if judge is None or low >= params.llm_below:
            return Decision(-neg_id, low, mean, "dense")
        if asked >= params.llm_per_article:
            break
        asked += 1
        verdict = judge(new, cand.members)
        if verdict is True:
            return Decision(-neg_id, low, mean, "llm-same")
        if reason == "new":
            reason = "llm-different" if verdict is False else "llm-unavailable"
    return Decision(None, None, None, reason)


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
