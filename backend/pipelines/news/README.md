# news 파이프라인 (뉴스 담당)

저장소 맨 위 폴더에서 실행한다 (`.env`는 거기 또는 상위에 둔다).

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
    python -m backend.pipelines.news.pipeline hourly --embed --loop 1800        # 30분마다 RSS 수집 + 새 기사 임베딩
    while true; do python -m backend.pipelines.news.naver --hours 3; sleep 7200; done   # 2시간마다 네이버 보강

    # 한 번만 실행
    python -m backend.pipelines.news.pipeline hourly                            # RSS 수집 1회 (임베딩 없음)
    python -m backend.pipelines.news.rss --dry-run                              # 피드 확인 (DB에 쓰지 않음)
    python -m backend.pipelines.news.naver --dry-run                            # 네이버 확인 (DB에 쓰지 않음)
    python -m backend.pipelines.news.pipeline daily --variant hybrid --skip-naver --include-untagged --date 2026-10-22   # 특정 날짜 태깅 + 임베딩
    python -m pytest backend/pipelines/news/tests                               # 테스트. TEST_DATABASE_URL이 없으면 DB 테스트는 건너뛴다

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
| embedder.py | BGE-M3 임베딩 -> news_embedding_variants. hybrid는 dense와 sparse를 한 번에 저장. 한 기사가 오류를 내도 나머지는 계속 처리한다 |
| scoring.py | dense / sparse / hybrid 점수 식 (가중치는 인자로 받는다) |
| evaluate.py | 평가: Recall@k, MRR, nDCG. 가중치·정규화 방식을 바꿔 가며 비교 |
| repository.py | news_sources·news_feeds 조회, 중복 판별 해시 |
| feeds.yaml, stocks.yaml, naver_queries.yaml | 설정 |
| seed.sql | news_feeds에 전체뉴스 RSS 4개를 넣는다 (여러 번 실행해도 중복되지 않는다) |

관련 파일: `alembic/versions/0006_news_embedding_variants.py`(팀 승인 전이라 각자 로컬 DB에만 적용), `backend/pipelines/common/db.py`(팀 공용 파일이라 덮어쓰지 않는다. 뉴스 코드가 쓰는 함수는 `start_run`, `finish_run`, `load_env`, `get_dsn`).

## 처음 시작하는 순서 (서린·예빈 같은 순서)

각자 자기 PC의 DB에서 처음부터 끝까지 돌린다. 막히면 오류 메시지를 공유한다. (DB 비밀번호는 붙여 넣지 말 것)

1. **패키지와 .env**: `pip install feedparser requests pyyaml "psycopg[binary]" python-dotenv pytest FlagEmbedding`. `.env`에 `DATABASE_URL`(또는 `POSTGRES_*`)과 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`이 있어야 한다. (커밋 금지)
2. **DB 상태 확인**: `news_sources`(sedaily, mk, hankyung, yonhap), `news_feeds`, `news_articles`, `news_stocks`, `ingest_runs`, `stocks`가 있고 `alembic_version`이 0005여야 한다.
3. **마이그레이션 번호**: 팀의 `0005_schema_policy_hardening.py`가 이미 있으므로 이 폴더의 임베딩 마이그레이션은 **0006**(`revision = "0006"`, `down_revision = "0005"`)이다.
4. **시드 적용**: `seed.sql`을 실행해 `news_feeds`에 RSS 4개를 넣는다. (매체와 시범 종목은 DB에 이미 있다.)
5. **RSS 확인과 수집**: `rss --dry-run`으로 4개 모두 건수가 나오는지, `pipeline hourly`를 두 번 실행해 두 번째 신규 건수가 크게 줄어드는지 본다.
6. **네이버 확인**: `naver --dry-run`으로 종목별 조회 건수와 보관 건수를 본다. 조회가 1,000건이면 한도에 닿은 것이다.
7. **0006을 자기 로컬 DB에만 적용**: `.env`의 DB가 자기 로컬 DB인지 확인한 뒤 `alembic upgrade head`. 커밋하거나 팀 레포에 올리지 않는다.
8. **BGE-M3 확인**: `python -c "from FlagEmbedding import BGEM3FlagModel; m = BGEM3FlagModel('BAAI/bge-m3', use_fp16=False); print(m.encode(['삼성전자 실적'])['dense_vecs'].shape)"` 가 `(1, 1024)`이어야 한다.
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

- `backend/pipelines/news/`는 다른 파트와 겹치지 않으므로 그대로 넣는다.
- `backend/pipelines/common/db.py`는 덮어쓰지 말고 필요한 네 함수가 팀 파일에 같은 이름·인자로 있는지 본다.
- 0006은 팀 승인 뒤에 넣는다.

## 아직 열려 있는 것

- 0006(임베딩 테이블) 승인
- sparse 정규화 방식, 종목 필터 사용 여부(평가로 결정)
- 지속 수집을 돌릴 환경(서버)과 팀 공용 DB
- 팀 지침(v1.2)의 "네이버 API 미사용" 문구를 "RSS + 네이버 병행"으로 고치기
- 매일경제·연합뉴스 RSS 이용약관(AI 사용 조건)
- 한국경제 RSS의 갱신 지연 여부(최신 기사 시각이 멈추는지 확인 중)
- NAVER 검색어: 일반 단어("네이버")라 노이즈가 많아 구체적인 검색어 사용
