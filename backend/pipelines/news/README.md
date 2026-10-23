# 뉴스 수집·임베딩·클러스터링 개발 안내

저장소 최상위에서 실행한다. 이 문서는 팀 코드 리뷰와 재현 준비용이다.
아래 설치·실행 예시는 **이번 문서 보완 작업에서 실행하지 않았다**.
기존 환경의 실험 성공이 신규 환경의 설치 성공을 보장하지 않는다.

## 1. 기본 개발 환경

`environment.yml`의 Python 3.11 및 기존 패키지·버전 제약은 유지했다.
뉴스 코드가 import하는 feedparser와 PyYAML, 단위 테스트용 pytest를 추가했다.

| 추가 패키지 | 고정 버전 | 기존 환경 메타데이터의 Python 요구 조건 |
|---|---|---|
| feedparser | 6.0.14 | >=3.10 |
| PyYAML | 6.0.3 | >=3.8 |
| pytest | 9.1.1 | >=3.10 |

Python 3.11과 위 조건의 정적 호환성을 확인했다. 신규 Conda 환경 생성,
전체 의존성 해결 및 설치는 아직 검증하지 않았다. 기존 무버전 패키지와
전이 의존성까지 고정한 잠금 파일은 아니다.

설치가 별도로 승인된 환경에서 사용할 준비 명령:

```bash
conda env create -f environment.yml
conda activate ai_memo
```

기본 환경은 RSS·네이버 코드와 DB 없는 테스트를 위한 것이다.
**FlagEmbedding, torch, transformers는 기본 환경에 추가하지 않았다.**
기존 dense 벡터를 입력받는 클러스터링 순수 함수에도 모델 패키지가 필요 없다.

설정은 `.env`의 `DATABASE_URL` 또는 `POSTGRES_*`를 사용한다.
네이버 수집에는 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`이 추가로 필요하다.
`.env`, 비밀번호, API 키, 전체 접속 문자열은 출력·공유·커밋하지 않는다.

## 2. 실제 모델 실행 환경: 선택 설치

기존 실험 환경의 패키지 메타데이터는 다음과 같다.

- FlagEmbedding 1.4.2
- transformers 4.51.3
- torch 2.5.1+cu121

아래는 이를 참고한 **신규 환경에서 설치 성공이 검증되지 않은 후보 절차**다.
CPU 또는 GPU용 torch 중 하나만 선택한다. GPU 설치는 NVIDIA GPU,
드라이버의 CUDA 12.1 지원 여부와 여유 VRAM을 먼저 확인해야 한다.
CPU 설치와 GPU 설치를 순서대로 모두 실행하지 않는다.

CPU 후보:

```bash
python -m pip install "torch==2.5.1" --index-url https://download.pytorch.org/whl/cpu
```

CUDA 12.1 GPU 후보:

```bash
python -m pip install "torch==2.5.1" --index-url https://download.pytorch.org/whl/cu121
```

선택한 torch 설치 후의 모델 패키지 후보:

```bash
python -m pip install "transformers==4.51.3" "FlagEmbedding==1.4.2"
```

FlagEmbedding의 전이 의존성까지 고정하지 않았으므로 resolver 충돌이나
CPU·GPU 차이가 발생할 수 있다. 충돌 시 기존 패키지를 임의 교체하지 말고
설치 로그에서 비밀정보를 제거한 뒤 검토한다. 대용량 패키지 설치와 모델
다운로드는 별개이며, 둘 다 실행 전 승인이 필요하다.

### 모델 캐시와 실험 설정

기존 BGE-M3 캐시는 저장소에 포함하지 않는다. 사전 준비된 로컬 캐시가
있는 경우에만 다음 환경변수를 모델 로딩 전에 설정해 오프라인 실행한다.
캐시가 없으면 실패 원인을 확인하고 중단하며 자동 다운로드로 전환하지 않는다.

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
```

| 설정 | 코드 기본값 | 소규모 GPU 실험 |
|---|---|---|
| 모델 | BAAI/bge-m3 | 동일한 기존 캐시 |
| variant | pipeline CLI는 hybrid | hybrid |
| batch_size | 16 | 2 |
| use_fp16 | False | True |
| fail_fast | False: 모델 배치 오류 시 개별 재시도 가능 | True: 재시도 없이 중단 |
| 오프라인 | 코드가 강제하지 않음 | 위 환경변수로 다운로드 차단 |

CPU에서는 FP16=True를 그대로 사용하지 말고 FP32(use_fp16=False)를 기준으로
별도 검증한다. GPU 6GB에서도 길이·드라이버·다른 프로세스에 따라 메모리
부족이 생길 수 있다. 실험에서는 batch_size=2를 사용했다. OOM이 발생하면
재시도 없이 중단해야 한다.
표의 설정은 함수 인자다. CLI에 `--batch-size`, `--fp16`,
`--fail-fast`, `--news-ids` 옵션이 있는 것은 아니다.

## 3. 단계별 실행 전제조건

| 단계 | 필요한 것 | 주의할 부작용 |
|---|---|---|
| RSS | 기본 환경, RSS 네트워크 접근, 설정 파일, 저장 시 DB·언론사·피드 구성 | 외부 요청, 기사·수집 기록 저장 |
| 네이버 | 기본 환경, API 키·접근 권한, 검색 설정, 저장 시 DB·종목 구성 | 실제 API 요청, 기사·종목 연결 저장 |
| 임베딩 | 모델 실행 환경·캐시, 기존 기사, pgvector 및 0006 테이블 | 모델 계산, 임베딩 INSERT; pipeline은 태깅·수집·정리도 수행 가능 |
| 클러스터링 | 기사 ID·제목·언론사·시간대 있는 발행시각·기존 dense 벡터 | 순수 함수의 메모리 계산만 수행 |

RSS는 설정된 4개 매체를 수집하고, 네이버는 설정된 종목 검색어와
허용 언론사로 보강한다. 실제 접근 가능 여부·응답 건수는 별도 확인 대상이다.
발행일 필터는 `published_at`을 기준으로 하며 일별 경계는 KST 자정이다.

`0006_news_embedding_variants.py`는 **PR에 포함되는 검토 대상**이다.
revision은 `0006`, 선행 revision은 `0005`다.
기존 `news_articles`에 연결된 `news_embedding_variants`를 생성하고
dense vector(1024), sparse JSONB 및 variant별 인덱스를 정의한다.
**공유 DB 적용은 팀 승인 후에만 진행한다.** 다른 작업의 revision·테이블과
충돌하는지 확인해야 하며, PR 포함이 마이그레이션 실행 승인을 뜻하지 않는다.
DB 스키마·피드 시드 준비 역시 승인된 별도 작업으로 수행한다.

### 수집·일별 처리 예시

다음은 실행이 승인된 로컬 평가 환경을 위한 예시다.
수집·DB 쓰기·모델 계산을 수행하므로 단순 상태 확인 명령으로 실행하지 않는다.
평가 데이터를 보존하도록 모든 pipeline 예시에 `--keep-days 0`을 명시했다.

```bash
# RSS 한 번: 임베딩 없음
python -m backend.pipelines.news.pipeline hourly --keep-days 0

# 반복 RSS 및 임베딩: 1800초 간격, 모델은 지연 로딩 후 재사용
python -m backend.pipelines.news.pipeline hourly --embed --loop 1800 --keep-days 0

# 특정 발행일: 네이버 수집 생략, 태깅 및 전체 기사 임베딩
python -m backend.pipelines.news.pipeline daily --variant hybrid --skip-naver --include-untagged --date 2026-10-22 --keep-days 0

# 네이버 최근 3시간 보강: 자동 반복은 별도 스케줄링 필요
python -m backend.pipelines.news.naver --hours 3
```

`hourly --embed`는 최근 `--embed-days`일(기본 3)의 기사를 종목 태그 유무와
무관하게 처리한다. `daily`는 기본적으로 종목 태그가 있는 기사만 처리하며
전체 기사 대상이면 `--include-untagged`가 필요하다. daily는
`--skip-naver`가 없으면 네이버도 수집한다. 수집과 임베딩은 순차 실행이므로
모델 계산이 오래 걸리면 다음 수집이 늦어질 수 있다.

**dry-run은 네트워크 차단 모드가 아니다.**

```bash
python -m backend.pipelines.news.rss --dry-run
python -m backend.pipelines.news.naver --dry-run
```

두 명령 모두 실제 외부 요청을 수행한다. DB 저장을 생략하는 옵션이며,
RSS에 `--db-feeds`까지 지정하면 피드 구성을 위한 DB SELECT도 수행한다.
네이버 dry-run에도 API 키가 필요하다.

### 지정 ID 임베딩과 트랜잭션

`pending_articles(..., news_ids=[...])`와 `embed_window(..., news_ids=[...],
batch_size=2, fail_fast=True)`를 사용하면 지정 ID만 대상으로 제한할 수 있다.
`news_ids=[]`는 SQL 조회 없이 0건이다. ID 필터에도 날짜·종목 필터는
그대로 적용되므로 기간과 `include_untagged=True`를 확인하고, 실행 직전
선택된 ID 집합이 승인 목록과 정확히 일치하는지 검증해야 한다.

기존 `(news_id, variant)` 임베딩은 제외하며 덮어쓰지 않는다.
입력은 제목과 요약을 줄바꿈으로 연결하고 요약이 없으면 제목만 사용한다.
모든 계산 결과의 개수, dense 1024차원·유한값·0이 아닌 norm,
hybrid sparse 사전의 키·가중치를 검증한 후 INSERT를 시작한다.
hybrid sparse의 NULL은 오류이며 빈 사전 `{}`은 허용한다.

**함수는 트랜잭션을 직접 시작·커밋하지 않는다.**
기존 pipeline은 autocommit 연결을 사용한다. 따라서 일부 SQL 저장 실패까지
전체 원자성을 보장하려면 호출자가 명시적 단일 트랜잭션을 열고, INSERT 후
ID·건수·variant·벡터·sparse를 SELECT 검증한 뒤에만 COMMIT해야 한다.
실패 시 ROLLBACK하며 임의 재실행하지 않는다. 동시 임베딩도 피한다.

## 4. 클러스터링은 독립적인 미리보기

`clustering.py`는 **RSS·네이버·기존 pipeline에 자동 연결되어 있지 않다.**
DB 조회 어댑터나 클러스터 결과 저장 기능도 없다.
호출자가 승인된 SELECT 결과를 `NewsArticle`로 변환하여 전달한다.

```python
from datetime import timedelta
from backend.pipelines.news.clustering import cluster_articles

# articles: 호출자가 미리 준비한 NewsArticle 목록. 이 예시는 DB 조회를 하지 않는다.
preview = cluster_articles(
    articles, threshold=0.65, max_time_gap=timedelta(hours=24)
)
```

실제 L2 norm으로 정규화한 코사인 유사도를 사용한다. complete-link로
그룹 내 모든 쌍이 임계값 이상이고 시간 차이도 범위 이내인 경우만 합친다.
A-B와 B-C만 유사하다는 이유로 A-C까지 같은 그룹으로 잇지 않는다.
대표 기사는 발행시각이 가장 이른 기사이며 동률이면 작은 ID를 선택한다.
입력 순서가 바뀌어도 결과가 안정적이다.

중복 ID, 잘못된 차원·NaN·무한대·영벡터, 누락되거나 시간대가 없는 발행시각은
오류다. dense가 None인 기사는 `missing_embedding_ids`로 보고한다.
결과에는 대표 기사, 소속 ID, 기사 수, 최소 유사도가 포함된다.
단독 기사에는 비교 쌍이 없어 최소 유사도가 None이다.
**기본 임계값 0.65와 시간 범위 24시간은 실험용이며 운영 기준으로 확정하지 않았다.**

## 5. 자동 정리와 테스트의 데이터 삭제 위험

**보관 정책 기본값은 30일이다.** `hourly --loop`는 시작 후 하루 한 번,
`daily`는 실행 시 오래된 기사를 정리한다. 종목 연결(`news_stocks`),
추적 매칭(`tracking_matches`), 업데이트 근거(`update_sources`)가 없는
기사가 삭제 대상이며, 연결된 임베딩은 FK의 ON DELETE CASCADE로 함께 삭제된다.
평가 정답 여부는 확인하지 않는다. `--keep-days 0`은 자동 정리만 끄며
수집·태깅·임베딩 저장까지 막는 옵션은 아니다.

**DB 통합 테스트는 DROP TABLE 및 TRUNCATE ... CASCADE를 실행한다.**
기사·연결·수집 기록을 비우고 임베딩 테이블을 다시 만들 수 있다.
`TEST_DATABASE_URL`의 DB 이름에 test가 있는지 검사하지만 이 검사만으로
데이터 안전을 보장하지 않는다. 개발 DB·공유 DB에는 절대 지정하지 않는다.
전체 pytest나 뉴스 테스트 폴더 전체 실행을 기본 안내로 사용하지 않는다.

이전 분리 작업에서는 명시적으로 선택한 DB 없는 테스트 140개가 통과했다
(클러스터링 58, 임베딩 59, 검색 평가 8, 네이버 mock 10, pipeline mock 5).
현재 문서 보완에서는 테스트를 다시 실행하지 않았다.
DB 테스트는 실행하지 않았으며 PostgreSQL·pgvector·마이그레이션·실제 수집의
통합 검증을 의미하지 않는다. DB 없는 테스트도 fixtures와 플러그인을
확인하고 외부 통신·실제 모델을 mock하는 범위만 선택한다.

## 6. 기존 실험 결과와 남은 검증

- 기존 로컬 실험: 원본 기사 270건을 보존하며 hybrid 32건 저장(5+25+2).
- 30건 미리보기: 0.65에서 잠정 동일 사건 8쌍은 같은 그룹,
  별개 사건 5쌍은 다른 그룹. 13쌍은 독립적인 확정 정답이 아니다.
- 론스타 ID 10·59·106·201: 0.60/0.65/0.70에서 4건 그룹,
  최소 유사도 약 0.742431. 201번 요약이 `(`뿐인 입력 품질 한계가 있다.
- 위 결과는 이전 실행 기록이다. 이번 변경에서 DB·모델로 재검증하지 않았다.

추가로 사건 단위 정답을 사람이 검토하고, 3건 이상 그룹 및 어려운 별개 사건을
보강해야 한다. 임계값 조정용과 최종 검증용 사건을 분리하고 Precision,
Recall, F1 및 그룹 단위 품질을 평가한다. 제목만 vs 제목+요약 실험,
공유 DB 적용, 자동 파이프라인 연결, 운영 스케줄·자원 설정은 후속 승인 대상이다.
RSS·API 이용 조건과 접근 권한도 팀에서 확인한다.

## 주요 파일

| 파일 | 역할 |
|---|---|
| rss.py / naver.py | RSS·네이버 수집 |
| repository.py / tagger.py | 피드 조회·중복 판별, 종목 태깅 |
| embedder.py | BGE-M3 dense/hybrid, 지정 ID·배치·출력 검증 |
| pipeline.py | hourly/daily 실행·반복·자동 정리 |
| clustering.py | 기존 dense 기반 complete-link 메모리 미리보기 |
| scoring.py / evaluate.py | dense/sparse 점수와 검색 평가 |
| feeds.yaml / stocks.yaml / naver_queries.yaml / seed.sql | 설정·피드 시드 |
| tests/ | 순수 함수·mock 테스트와 별도 DB 통합 테스트 |

공통 DB 도우미는 `backend/pipelines/common/db.py`를 사용한다.
검색 평가 `evaluate.py`는 클러스터링 평가와 별개다. 질의 평가에는 모델이,
후보 CSV 내보내기에는 DB 읽기와 파일 쓰기가 필요하므로 별도 승인 후 실행한다.
