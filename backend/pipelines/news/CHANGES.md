# 예빈에게: 뉴스 코드 변경 사항 (2026-10-22)

이 폴더의 파일을 같은 이름의 파일로 교체하면 된다 (`backend/pipelines/news/`에 넣고, `tests/`는 그 안의 `tests/`에, `alembic_versions/`의 파일은 `alembic/versions/`에 넣는다).
넣지 않은 것: `__init__.py`(빈 파일, 그대로), `tests/test_rss.py`, `tests/test_db_integration.py`(바꾸지 않았다), `backend/pipelines/common/db.py`(팀 파일이니 덮어쓰지 말 것).
`_구버전_무시_`로 시작하는 파일은 이전에 잘못 올린 것이니 쓰지 않는다.
예전에 받은 Drive 코드와 달라진 점은 아래와 같다.

## 1. 방향이 바뀐 것

| 항목 | 예전 | 지금 |
|---|---|---|
| 네이버 API | 쓰지 않음 (지침 v1.2) | **사용**. RSS가 놓치는 4개 종목 기사를 보강한다. 4개 매체 도메인만 저장 |
| 임베딩 대상 | 종목 태그된 기사만, 전날분 | **전체 기사**. 태깅은 참고 표시. 메모와 유사도가 높은 기사를 가져온다 |
| 임베딩 방식 | dense는 예빈, hybrid는 서린 | **둘 다 hybrid**. dense만 쓰는 것은 가중치를 `1:0`으로 두는 것과 같다 |
| 날짜 기준 | (작업서에 "수집한 날짜"로 적혀 있었음) | **기사 발행일**(`published_at`, KST 자정 기준). 코드는 처음부터 발행일 기준이었다 |
| 수집 주기 | 1시간 | **RSS 30분**, **네이버 2시간**(`--hours 3`) |
| 실행 방식 | 명령을 직접 실행 | `hourly --embed --loop 1800` 한 줄로 30분마다 수집 + 새 기사 임베딩을 계속 반복 |

이유: RSS는 피드당 최신 약 50건만 줘서 지난 기사를 되돌려 받을 수 없다. 네이버 검색은 한 번에 최신 1,000건까지만 줘서 삼성전자는 약 10시간분만 나온다. 그래서 둘 다 계속 돌려서 DB에 쌓는다.

## 2. 파일별 변경

| 파일 | 변경 |
|---|---|
| pipeline.py | `hourly --embed --loop SECONDS`, `--keep-days`, `--include-untagged`, `--skip-naver` 추가. 모델은 한 번만 불러 계속 쓴다 |
| embedder.py | BGE-M3 로딩 시 `dtype` 오류를 고치는 호환 코드 추가(`_patch_dtype_compat`), `include_untagged`. 한 기사가 오류를 내도 나머지는 계속 처리하고(실패 기사는 다음 주기에 재시도), 회차마다 대상·성공·실패 건수와 걸린 시간을 로그로 남긴다 |
| tagger.py | `title_only`(제목에 있을 때만 연결) 지원 |
| naver.py | 네이버 수집. 검색어에서 종목이 정해져 `news_stocks`에 바로 연결. `--hours`, `--dry-run` |
| rss.py | 매체 코드를 DB 값(`sedaily`, `mk`, `hankyung`, `yonhap`)에 맞춤 |
| stocks.yaml | SK하이닉스 별칭 "삼전닉스" 추가, NAVER는 `title_only: true` (일반 단어라 오탐이 많았다) |
| naver_queries.yaml | NAVER 검색어를 "네이버 주가", "네이버 실적", "네이버 클라우드", "네이버 AI"로 나눔 |
| feeds.yaml | 매체 코드 수정 |
| seed.sql | `news_feeds`에 RSS 4개만 넣는다. 위치는 `backend/pipelines/news/seed.sql` (여러 번 실행해도 중복 없음) |
| evaluate.py (새 파일) | Recall@k, MRR, nDCG. 가중치와 sparse 정규화 방식을 바꿔 가며 비교. `--only-tagged`로 종목 연결 기사만 검색하는 경우와 전체 검색을 비교 |
| tests/ | 위 변경에 맞춘 테스트. `tests/conftest.py`(새 파일): `TEST_DATABASE_URL`의 DB 이름에 `test`가 없으면 테스트를 시작하지 않는다 |
| alembic/0006_news_embedding_variants.py | 임베딩 테이블. 팀의 0005 다음 번호(0006). **팀 승인 전이라 자기 로컬 DB에만 적용**하고 커밋하지 않는다 |

## 3. 지금 하면 되는 것

README.md의 "처음 시작하는 순서" 1~10을 서린과 같은 순서로 돌린다. 요점만:

1. 새 파일로 뉴스 폴더 교체. `alembic/versions/`에는 `0006_news_embedding_variants.py`를 넣는다 (`revision = "0006"`, `down_revision = "0005"`).
2. `seed.sql` 적용 -> `rss --dry-run` -> `pipeline hourly` 두 번(두 번째 신규가 줄어야 함).
3. `naver --dry-run`으로 종목별 조회·보관 건수 확인. (네이버 키는 `.env`에 있어야 한다.)
4. `alembic upgrade head` (자기 로컬 DB에만).
5. `pipeline hourly --embed --loop 1800` 을 켜 둔다. 절전 설정은 끈다.
6. `SELECT variant, count(*) FROM news_embedding_variants GROUP BY variant;` 에 `hybrid`가 쌓이는지 확인.

주의:
- DB는 각자 따로라서 서로의 기사는 보이지 않는다. 평가는 한쪽 DB에서 돌리거나 기사 집합을 맞춘 뒤에 한다.
- 정리(자동 삭제)는 하루 한 번, 종목 연결이 없고 `--keep-days`일(기본 **30**)이 지난 기사를 지운다. 기사를 지우면 그 임베딩도 같이 지워진다. `hourly --loop`과 `daily` 둘 다 이 값을 쓰고, `--keep-days 0`이면 지우지 않는다. 평가 정답으로 적은 기사는 이 코드가 알지 못하므로 평가가 끝날 때까지는 0으로 두는 것이 안전하다.
- DB 테스트는 테이블을 비운다. 실제 작업 DB(`memos`)를 `TEST_DATABASE_URL`에 넣지 말고, 버려도 되는 별도 DB(이름에 `test` 포함)에서만 돌린다. 지금은 전체 pytest를 DB 없이(`TEST_DATABASE_URL` 없이) 돌리면 DB 테스트는 자동으로 건너뛴다.
- 평가(`evaluate.py`): 정답 기사가 검색 풀에 없으면(태그가 없어 `--only-tagged`에서 빠졌거나 기간 밖) 정답에서 지우지 않고 **못 찾은 것으로 계산**한다. DB에 아예 없는 정답 URL(오타, 삭제)은 경고하고 정답에서 뺀다.
- 빈 sparse 결과는 NULL 대신 빈 사전 `{}`로 저장한다 (hybrid의 sparse는 NULL이면 안 되는 DB 규칙 때문).
- 임베딩 작업은 한 번에 하나만 실행한다.
- 팀 공용 DB는 임베딩 비교가 끝난 뒤 따로 정한다.

## 4. 같이 정할 것

- 평가용 질문과 정답: 페르소나별 예상 메모 문장 20~30개, 정답은 기사 URL로 표시한다.
- 평가는 서린 DB 한 곳에서 돌리고, 예빈은 질문과 정답 작성을 맡는 것을 제안한다.
- 비교 설정: 종목 태그된 기사만 검색 vs 전체 기사 검색, 가중치 조합, sparse 정규화, k 값(3, 5, 10).
- 0006 승인, 지속 수집 서버, 팀 지침의 네이버 API 문구 정정, 연합뉴스·매일경제 RSS 이용약관 확인.
