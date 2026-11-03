# news 파이프라인 (뉴스 담당)

저장소 맨 위 폴더에서 실행한다 (`.env`는 거기 또는 상위에 둔다).

## dev2 기반 선별 이전 및 개발용 미리보기

`feature/yebin-next`에서 보존 커밋 `dc1caddab7e66f0ee54d7b38071ba5f7b2b352ed`의
뉴스 기능만 선별 반영했다. 기존 수집·태깅·pipeline의 호출 순서는 유지한다.
공용 `common/db.py`, 기존 검색 평가 `evaluate.py`의 `get_read_dsn()` 사용,
`environment.yml`, Alembic 이력 및 다른 팀 코드는 교체하지 않는다.

- `clustering.py`: 실제 L2 norm으로 정규화한 dense 코사인과 complete-link 그룹 구성.
  그룹 내 모든 쌍이 기준을 만족해야 하며 대표 기사는 가장 이른 발행시각, 동률이면 작은 ID다.
- `evaluate_clustering.py`와 `evaluation/`: 사람이 승인한 관계만 평가한다. 현재 개발용
  라벨은 승인 15건(기사 10·그룹 3·쌍 2), 미승인 26건이며 독립 검증 자료가 아니다.
  라벨 없는 교차 쌍을 negative로 만들지 않는다. 기존 라벨 ID는 이전 DB 기준이므로
  새 DB와 제목·언론사·발행시각·URL을 대조하기 전에는 연결하거나 재평가하지 않는다.
- `preview.py`: 메모리의 조회 행을 검증하고 기존 `cluster_articles()`를 호출한다.
  필수 키는 `news_id`, `title`, `publisher`, `published_at`, `url`, `model`, `variant`, `dense`다.
  발행시각에는 시간대가 필요하고, 임베딩 누락은 model·variant·dense가 모두 None이어야 한다.
  누락 ID를 별도 반환하며 누락 기사를 정상 단독 그룹으로 만들지 않는다.
- `preview_repository.py`: 외부에서 받은 psycopg 3 호환 connection으로 SELECT만 수행한다.
  autocommit=False인 활성 읽기 전용 트랜잭션이 필요하며 확인되지 않으면 거부한다.
  조회 기간은 최대 7일, 기사 수는 1~100건이고 한도를 넘기면 오류다.
  연결 생성·DB 설정 읽기·commit·rollback·close는 수행하지 않으며 호출자가 담당한다.

**클러스터링·미리보기는 자동 pipeline·API·프론트엔드에 연결되지 않았다.**
DB에 그룹을 저장하지 않는다. 미리보기는 `BAAI/bge-m3` / `hybrid` 행의 dense만 사용하며
sparse 가중합 검색 점수와 다르다. 임계값 0.65·최대 시간 차이 24시간은 개발용 예시이고
운영 임계값으로 확정하지 않았다. 순수 함수 테스트에는 DB·모델 패키지가 필요 없다.

지정 ID 임베딩은 `pending_articles(..., news_ids=[...])` 및
`embed_window(..., news_ids=[...], batch_size=2, fail_fast=True)`로 제한한다.
`news_ids=[]`는 DB 조회 없이 0건이며, 지정 ID에도 날짜·종목 필터가 적용된다.
기존 variant는 건너뛰고, 제목+요약(요약이 없으면 제목) 입력을 유지한다.
출력 수·dense 1,024차원·유한값·양의 norm·hybrid sparse 사전을 모두 검사한 뒤 INSERT한다.
hybrid의 None sparse는 오류이며 빈 사전은 허용한다. batch_size 기본값은 16,
FP16 기본값은 False, fail_fast 기본값은 False다. 기존 호출 형식은 유지한다.
함수는 commit하지 않으므로 저장 전체의 원자성은 호출자의 명시적 트랜잭션에 달려 있다.
기존 pipeline의 autocommit 동작까지 바뀌는 것은 아니다.

이전 환경의 소규모 GPU 실험은 batch_size=2·FP16=True·fail_fast=True와
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`을 사용했다.
이는 CLI 옵션이 아니며 코드가 오프라인을 강제하지 않는다. 새 환경의 설치·GPU·캐시와
새 DB의 기사·임베딩 존재 여부는 미검증이다. 캐시가 없으면 자동 다운로드하지 않는다.
실제 수집·모델 실행·DB 조회/쓰기·마이그레이션은 별도 승인 대상이다.

## 구조

```
RSS 4개 매체 (30분마다) ──┐
                          ├─> news_articles ──┬─> 홈 최신 뉴스 위젯 (저장된 기사를 바로 조회, 임베딩 불필요)
네이버 검색 API (2시간마다) ┘                   └─> 임베딩(BGE-M3 hybrid) -> news_embedding_variants
 (4개 종목 검색, 4개 매체 도메인만 저장)            메모와 유사도가 높은 기사를 찾아 AI 업데이트 근거로 사용
```

- RSS: 4개 매체(서울경제 sedaily, 매일경제 mk, 한국경제 hankyung, 연합뉴스 yonhap) 전체뉴스. 홈 최신 뉴스 + 기본 수집.
- 네이버 API: 삼성전자·SK하이닉스·NAVER·KB금융 기사를 검색해 RSS가 놓친 종목 기사를 보강. 한 번에 최신 1,000건까지만 받을 수 있어서 2시간마다 최근 3시간분(`--hours 3`)을 받는다.
- 임베딩은 종목 태그와 상관없이 **전체 기사**를 대상으로 한다. 종목 태깅(`news_stocks`)은 참고 표시로만 남긴다.
- 날짜 기준은 기사 **발행일**(`published_at`, KST 자정 기준)이다. 수집일이 아니다.
- RSS는 피드당 최신 약 50건(연합뉴스 120건)만 주므로 지난 기사를 되돌려 받을 수 없다. 계속 켜 두고 쌓아야 한다.

## 실행

    # 계속 켜 두는 것 (터미널 2개)
    python -m backend.pipelines.news.pipeline hourly --embed --loop 1800 --keep-days 0  # 30분마다 RSS 수집 + 새 기사 임베딩
    while true; do python -m backend.pipelines.news.naver --hours 3; sleep 7200; done   # 2시간마다 네이버 보강

    # 한 번만 실행
    python -m backend.pipelines.news.pipeline hourly --keep-days 0              # RSS 수집 1회 (임베딩 없음)
    python -m backend.pipelines.news.rss --dry-run                              # 피드 확인 (DB에 쓰지 않음)
    python -m backend.pipelines.news.naver --dry-run                            # 네이버 확인 (DB에 쓰지 않음)
    python -m backend.pipelines.news.pipeline daily --variant hybrid --skip-naver --include-untagged --date 2026-10-22 --keep-days 0  # 특정 날짜 태깅 + 임베딩

위 명령은 실행이 별도 승인된 환경용 예시이며 이번 선별 이전에서는 실행하지 않는다.
`--dry-run`도 실제 RSS/API 요청을 하며 네트워크 차단 기능은 아니다.
RSS의 `--db-feeds`는 dry-run에서도 피드 구성을 위해 DB를 읽을 수 있다.

DB 없는 회귀 검증은 DB 환경변수와 pytest 자동 플러그인을 차단하고, 네트워크·실제 모델 접근을
막은 실행기에서 다음 5개 파일만 선택한다. 바이트코드·pytest 캐시도 비활성화한다.
`test_clustering.py`, `test_embedder.py`, `test_evaluate_clustering.py`, `test_preview.py`,
`test_preview_repository.py`. `test_pipeline.py`와 전체 테스트 폴더는 이번 검증에서 실행하지 않는다.

**주의 1: 자동 삭제.** `hourly --loop`(하루 한 번)과 `daily`는 종목 연결이 없고 `--keep-days`일(기본 30)이 지난 기사를 지운다. 기사를 지우면 그 임베딩도 함께 지워진다. 평가 정답으로 적은 기사인지는 이 코드가 모르므로, 평가가 끝날 때까지는 `--keep-days 0`(정리 안 함)으로 돌린다.
**주의 2: DB 테스트.** DB 테스트는 임베딩 테이블을 지우고 다시 만들며 기사·종목 연결·수집 기록 테이블을 비운다. `TEST_DATABASE_URL`에는 버려도 되는 별도 DB만 지정하고(이름에 `test`가 없으면 테스트가 시작되지 않는다), 뉴스를 모으는 `memos` DB는 지정하지 않는다.
**주의 3: 임베딩은 한 번에 하나만.** `--loop` 반복이 도는 동안 같은 DB에 `daily ... --include-untagged`를 따로 돌리지 않는다.
**참고: 임베딩 대상 범위.** `--embed`는 최근 `--embed-days`일(기본 3) 발행분 중 임베딩이 없는 기사를 찾는다. 이 범위를 넘긴 미처리 기사는 자동 재시도 대상이 아니므로, 필요하면 `--embed-days`를 늘려 한 번 돌린다. 수집과 임베딩은 한 반복 안에서 차례로 실행되므로 임베딩이 길어지면 다음 수집이 늦어질 수 있다. 서버에서 상시 운영할 때는 둘을 별도 작업으로 나눈다.

## 파일

| 파일 | 역할 |
|---|---|
| rss.py | 언론사 RSS 수집 -> news_articles |
| naver.py | 네이버 뉴스 검색 API 수집 -> news_articles + news_stocks (검색어에서 종목이 정해진다) |
| pipeline.py | 실행기 (`hourly [--embed --loop]`, `daily`) |
| tagger.py | 제목·요약에서 종목 이름을 찾아 news_stocks 연결 (stocks.yaml). NAVER는 제목에 있을 때만 (`title_only`) |
| embedder.py | BGE-M3 임베딩 -> news_embedding_variants. 지정 ID·배치 크기·fail_fast 및 저장 전 출력 검증 지원. 기본 모델 오류 처리는 개별 재시도 |
| scoring.py | dense / sparse / hybrid 점수 식 (가중치는 인자로 받는다) |
| evaluate.py | 평가: Recall@k, MRR, nDCG. 가중치·정규화 방식을 바꿔 가며 비교 |
| repository.py | news_sources·news_feeds 조회, 중복 판별 해시 |
| feeds.yaml, stocks.yaml, naver_queries.yaml | 설정 |
| seed.sql | news_feeds에 전체뉴스 RSS 4개를 넣는다 (여러 번 실행해도 중복되지 않는다) |

관련 파일: `alembic/versions/0006_news_embedding_variants.py`는 이미 dev2에 있다.
뉴스 0006과 시장 0006_market은 병합 revision `511517f9874b`로 연결되고 공시 0007로 이어진다.
이를 예전 이력으로 교체하거나 이미 적용됐다고 가정하지 않는다. **공유 DB 마이그레이션은 팀 승인 후**에만 진행한다.
`backend/pipelines/common/db.py`도 덮어쓰지 않는다. 뉴스가 쓰는 `start_run`, `finish_run`,
`load_env`, `get_dsn`과 새 `get_read_dsn` 등 공용 인터페이스를 보존한다.

## 처음 시작하는 순서 (서린·예빈 같은 순서)

아래는 실제 실행을 별도 승인받은 환경의 준비 체크리스트다. 새 연결을 이전 로컬 DB와
같다고 가정하지 않는다. `.env`, DB 비밀번호·API 키·전체 연결 문자열은 출력하거나 커밋하지 않는다.

1. **패키지와 .env**: 현재 `environment.yml`의 기존 선언은 유지한다. PyYAML·pytest·FlagEmbedding·transformers는 이미 선언됐고 feedparser는 누락돼 있다. 보존 브랜치의 `feedparser==6.0.14`는 추가 검토 후보이며 이번에는 의존성 파일 변경·설치를 하지 않는다. 수집에는 requests·PyYAML·feedparser, DB 작업에는 psycopg, 모델 실행에는 별도 torch·캐시·CPU/GPU 호환성 확인이 필요하다. 신규 환경 설치 성공을 검증한 것은 아니다. `.env`의 수집용 키와 쓰기·읽기 DB 설정도 승인된 환경에서 따로 준비한다.
2. **DB 상태 확인**: 승인된 대상에서 `news_sources`(sedaily, mk, hankyung, yonhap), `news_feeds`, `news_articles`, `news_stocks`, `ingest_runs`, `stocks`와 실제 Alembic revision을 확인한다. 현재 DB가 0005라고 가정하지 않는다.
3. **마이그레이션 번호**: 뉴스 테이블은 **0006**(`revision = "0006"`, `down_revision = "0005"`)이며 dev2의 시장·공시·병합 revision과 함께 보존한다.
4. **시드 적용**: `seed.sql`을 실행해 `news_feeds`에 RSS 4개를 넣는다. (매체와 시범 종목은 DB에 이미 있다.)
5. **RSS 확인과 수집**: `rss --dry-run`으로 4개 모두 건수가 나오는지, `pipeline hourly`를 두 번 실행해 두 번째 신규 건수가 크게 줄어드는지 본다.
6. **네이버 확인**: `naver --dry-run`으로 종목별 조회 건수와 보관 건수를 본다. 조회가 1,000건이면 한도에 닿은 것이다.
7. **마이그레이션 적용 판단**: 0006 파일은 이미 저장소에 포함돼 있다. 실제 DB revision과 팀 승인을 확인한 별도 작업에서만 적용 여부를 결정한다. 선별 이전이나 테스트만을 위해 migration을 실행하지 않는다.
8. **BGE-M3 준비**: 기존 캐시와 torch의 CPU/GPU 호환성을 확인한다. 실제 로딩·계산·다운로드는 별도 승인 후 수행하며 DB 없는 단위 테스트에서는 mock을 사용한다.
9. **계속 돌리기**: 위 "계속 켜 두는 것" 두 줄을 각각 터미널에서 실행한다(평가 전에는 첫 줄에 `--keep-days 0`을 붙인다). 절전 설정을 꺼 둔다.
10. **임베딩 확인**: `SELECT variant, count(*) FROM news_embedding_variants GROUP BY variant;` 에 `hybrid`가 쌓이는지 본다.

## 평가

- 질문(페르소나별 예상 메모)과 정답 기사를 사람이 표시한다. 정답은 DB가 달라도 쓸 수 있게 기사 URL로 적는다.
- 후보 기사 목록 내보내기:

      python -m backend.pipelines.news.evaluate --export-pool pool.csv --date-from 2026-10-22 --date-to 2026-10-22

- 평가 실행: `python -m backend.pipelines.news.evaluate --queries queries.csv --date-from ... --date-to ...`
- 가중치 `dense : sparse`는 검색할 때 곱하는 값이라 저장된 임베딩을 다시 만들지 않고 바꿔 볼 수 있다. `1:0`이 dense만, `0:1`이 sparse만이다. sparse 점수 정규화(`none` / `sparse-minmax` / `minmax`)도 같이 비교한다.
- 비교할 설정: 전체 기사에서 검색(기본) vs 종목이 연결된 기사만 검색(`--only-tagged`). 같은 질문·정답으로 두 번 돌려 비교한다. `--only-tagged`는 질문과 같은 종목이 아니라 **어느 종목이든 태그가 있는 기사**를 대상으로 한다.
- 정답 기사가 검색 풀에 없으면(태그 없음, 기간 밖, 임베딩 없음) 못 찾은 것으로 계산한다. 정답에서 빼지 않는다. DB에 없는 정답 URL(오타, 삭제)은 경고하고 정답에서 뺀다.
- 두 DB의 기사 집합이 다르면 같은 정답으로 비교할 수 없다. 평가는 한쪽 DB에서 돌리거나 기사 집합을 맞춘 뒤 돌린다.

## 팀 레포에 합치기

- `backend/pipelines/news/`도 dev2의 기존 코드와 비교해 파일·변경분을 선별 반영한다. 폴더 전체를 교체하지 않는다.
- `backend/pipelines/common/db.py`는 덮어쓰지 말고 필요한 네 함수가 팀 파일에 같은 이름·인자로 있는지 본다.
- 이미 있는 0006 및 연결된 마이그레이션 이력은 보존한다. 공유 DB 적용은 별도 팀 승인 사항이다.

## 아직 열려 있는 것

- 실제 연결 DB의 스키마·기사·벡터 확인 및 필요한 공유 DB 작업 승인
- sparse 정규화 방식, 종목 필터 사용 여부(평가로 결정)
- 지속 수집을 돌릴 환경(서버)과 팀 공용 DB
- 팀 지침(v1.2)의 "네이버 API 미사용" 문구를 "RSS + 네이버 병행"으로 고치기
- 매일경제·연합뉴스 RSS 이용약관(AI 사용 조건)
- 한국경제 RSS의 갱신 지연 여부(최신 기사 시각이 멈추는지 확인 중)
- NAVER 검색어: 일반 단어("네이버")라 노이즈가 많아 구체적인 검색어 사용
