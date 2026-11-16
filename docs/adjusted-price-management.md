# 수정주가 관리 (adjusted_price_manager)

기존 시장 데이터 수집(capture·finalize·morning)은 그대로 두고, 그 옆에서 수정주가 조정이 필요할 수 있는 종목만 골라
**감지 → 제한적 KIS 재조회 → 재동기화 계획(dry-run) → 승인 후 적용**한다.
KIS가 준 수정주가를 다시 계산하거나 보정하지 않는다.

## 1. 구성

| 파일 | 역할 |
|---|---|
| `backend/pipelines/market/adjusted_history_diagnostics.py` | 가격 기반 이상징후 (기존) |
| `scripts/diagnose_adjusted_history.py` | 가격 탐지 CLI, 읽기 전용 연결 `connect_read_only` (기존) |
| `backend/pipelines/market/corporate_actions.py` | DART 기업행동 추출·정정공시 묶기·후보·가격 탐지와 통합 |
| `backend/pipelines/market/adjusted_recheck.py` | 요청 상한 클라이언트·응답 재사용·DB 비교·상태 판정·중복 억제 |
| `backend/pipelines/market/adjusted_resync.py` | 재동기화 계획 검증과 승인 후 적용(백업·트랜잭션·검증) |
| `scripts/adjusted_price_manager.py` | `detect` · `recheck` · `resync-plan` · `resync-apply` · `resync-restore` |
| `configs/systemd/memos-adjusted-price-check.{service,timer}` | 비활성 예약 템플릿 (설치하지 않음) |

재사용한 기존 코드: `KisClient`(FHKST03010100, `FID_ORG_ADJ_PRC=0`, 요청 간격·재시도·토큰 캐시), `fetch_daily_range`,
`normalize_daily_row`, `daily_refresh_lock`·`ADVISORY_LOCK_KEY`, `common.db.get_read_dsn`·`database_url`,
`updates.preferred.build_map`, `market.symbol_status.load_symbol_statuses`, `common.file_lock`.
DART 수집 코드·테이블, KIS capture·finalize 코드는 바꾸지 않았다.

## 2. 실행

```bash
cd ~/projects/AI_investment_memo
# 1) 감지: 읽기 전용, API 없음. 가격 탐지를 다시 계산하거나 기존 결과를 재사용
PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py detect
PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py detect \
    --price-report logs/diagnostics/adjusted_history/<시각>/findings.json --window-days 5

# 2) 제한적 재조회: 가장 최근 detect 결과의 재조회 권장 종목만. 대상만 보기는 --list-only
PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py recheck --list-only
PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py recheck --max-symbols 5 --max-requests 10

# 3) 재동기화 계획(dry-run): HISTORY_RESYNC_CANDIDATE 종목만. KIS 전체 이력 조회 + 검증, DB 쓰기 없음
PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py resync-plan --symbols 047400 --max-requests 25

# 4) 승인 후 적용: 한 종목, 계획 sha256 확인, 쓰기 확인 플래그 필수 (DATABASE_URL로 쓴다)
PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py resync-apply \
    --plan logs/diagnostics/adjusted_price_manager/<시각>_resync-plan/plan_047400.json \
    --symbol 047400 --confirm <plan_sha256> --i-understand-this-writes-db
```

결과는 `logs/diagnostics/adjusted_price_manager/<KST 시각>_<단계>/`에 매번 새 폴더로 남는다
(`detect.json/md`, `recheck.json/md`, `kis_raw_responses.json`, `plan_<종목>.json`, `plan.md`).
상태는 `logs/market/adjusted_price_state/state.json`, 적용 전 백업은 `logs/market/adjusted_price_backups/`.

## 3. 감지 (detect)

**가격 기반**(기존 탐지기): 조정비율 급변, 수정주가만 급변, 거래량 0 가격 재설정, 조정 기준 혼재.
`consistent_adjustment`(정상 조정 패턴)는 `NORMAL_ADJUSTMENT`로 두고 재조회하지 않는다. high만 재조회를 권한다.

**공시 기반**: `share_count_change`, `capital_reduction`, `bonus_issue`, `rights_offering`, `restructuring`과 보조 신호
`trading_halt`(정지 사유에 병합·분할·감자·무상증자·합병·교환이 있을 때만).

- 날짜 칸을 따로 둔다: 공시일(`rcept_dt`), 결정일, 주주총회일, 기준일, 효력발생일, 매매거래정지 시작·종료, 신주상장예정일,
  합병·분할기일, 납입일. **권리락일은 원문에 칸이 있을 때만** 쓰고 기준일에서 계산하지 않는다(`ex_rights_status=unconfirmed`).
- 비율: 병합·분할은 전후 보통주 수, 감자는 감자비율(%), 무상증자는 1주당 배정 주식수, 합병 비율은 서술형 원문 그대로.
  유상증자는 DART 팀이 이미 뽑은 `fields`를 그대로 쓴다. 원문에 없는 값은 비운다.
- 정정공시: `corrects`(54/251건만 연결)만 믿지 않고 종목·`base_title`·원 제출일·결정일로 묶는다.
  원 제출일이 같은 원본이 여럿이거나 결정일이 서로 다르면 `REVIEW_REQUIRED`로 두고 날짜·비율을 확정하지 않는다.
  파싱 실패 공시는 최신본이 되지 않는다. 정정으로 조정 관련 날짜가 바뀌면 `schedule_changed`.
- 자회사 공시(`is_subsidiary`)는 `NO_ACTION`으로 따로 둔다(우선주 파생도 하지 않는다).
- 우선주: `preferred.build_map`으로 보통주 공시에서 파생 후보를 올린다. 비율은 옮기지 않는다(같다고 가정하지 않음).
- 재조회 권장은 종류별 기준 날짜(병합: 정지 시작·효력발생·상장, 감자: 정지·기준일·상장, 무상·유상: 권리락·기준일·상장,
  합병·분할: 정지·합병기일·상장)가 지난 뒤에만. 제3자배정 유상증자는 검토만 하고 재조회는 권하지 않는다(권리락이 없는 경우가 일반적이라는 추정).
- 종료 종목(`configs/kis_symbol_status.json`)은 `TERMINAL_EXCLUDED`: 정리매매 급락 등이 섞여 있어 운영 대상과 나눈다.

## 4. 재조회 (recheck)

- 감지에서 재조회를 권한 종목만, 발생일 전후 짧은 구간만 요청한다. `--max-symbols`, `--max-requests`로 상한을 둔다.
  `BudgetedClient`가 상한·허용 종목·수정주가 전용을 강제하고 모든 응답 원본을 `kis_raw_responses.json`에 남긴다.
- 실행 조건: 일일 갱신 advisory lock(581094001)을 잡아야 하고, 07:30~09:45와 18:15~21:30에는 KIS를 부르지 않는다.
- 이전 응답 재사용: 같은 구간을 덮는 7일 안의 응답(`adjusted_history_recheck`, 이전 recheck·resync-plan)은 다시 요청하지 않는다.
  100행이 꽉 찬 잘린 페이지는 믿지 않는다.
- 판정
  - `HISTORY_RESYNC_CANDIDATE`: DB와 현재 KIS가 다르고 현재 KIS 이력은 구간 안에서 연속 → 다음은 resync-plan(승인 후)
  - `SOURCE_DISCONTINUITY`: 다시 받아도 같은 단절 → 재조회 반복·보정 금지
  - `NO_ACTION`: 같고 단절 없음
  - `REVIEW_REQUIRED`: KIS 날짜 누락·중복·0 가격·응답 오류·DB와 다른데 KIS에도 단절
- 중복 억제: 종목마다 증거 키(비정보성 가격 탐지 날짜·판정 + 공시 묶음 최신 접수번호·지난 기준 날짜)를 남긴다.
  같은 키면 다시 요청하지 않는다. 새 정정공시, 새 기준 날짜 경과, 새 가격 이상이 생기면 키가 바뀌어 다시 본다.
  응답 오류는 6시간 뒤, 최대 3번까지만 다시 시도한다. 요청 상한에 걸린 종목은 상태를 바꾸지 않고 다음 실행으로 미룬다.

## 5. 재동기화 (resync-plan / resync-apply)

계획(dry-run)에서 막는 조건 (하나라도 실패하면 `blocked`):
재조회 상태가 `HISTORY_RESYNC_CANDIDATE`가 아님 · KIS와 DB 날짜 집합 불일치 · 중복 날짜 · 0 가격 행 · 조정 기준(adjustment_basis) 혼재 ·
가격 이상(OHLC 순서·음수) · 원시 거래량 0과 수정 거래량 0 불일치 · 수정 거래량이 조정비율과 맞지 않는 행이 5% 초과 ·
전체 KIS 이력에 수정주가 단절(수정만 급변·원시 단절 미조정).
변경 행 수, 변경 구간, 조정비율 구간(DB·KIS), 차이 표본, 원본 지문, `plan_sha256`을 남긴다.

적용(`resync-apply`)의 안전장치:
1. `--i-understand-this-writes-db`와 `--confirm <plan_sha256>`이 모두 있어야 하고, 상태가 `HISTORY_RESYNC_CANDIDATE`여야 한다.
2. 계획 파일이 바뀌었거나(해시), 24시간이 지났거나, `ready`가 아니면 거부한다.
3. 일일 갱신 advisory lock을 잡은 뒤 한 트랜잭션 안에서: 행 잠금(`FOR UPDATE`) → 계획 당시 DB 지문·날짜 집합과 같은지 확인 →
   원본 백업 파일 기록(fsync, 덮어쓰기 금지) → 기존 행만 `UPDATE`(행마다 정확히 1행) → 다시 읽어 계획과 같은지 확인.
   하나라도 실패하면 전체 롤백한다(백업 파일은 남는다).
4. 대상은 `adjusted_prices_daily`의 그 종목뿐. `INSERT`/`DELETE`는 없다. `prices_daily`, `stock_fundamentals_snapshot`,
   공시 테이블, Capture/Finalize 파일은 건드리지 않는다.
5. 적용 뒤 상태는 `NO_ACTION`(적용 시각·계획 해시·백업 경로 기록).

### 복원 (resync-restore)

```bash
# dry-run (기본): 백업 무결성·대상 종목·날짜 집합·현재 DB 상태 확인 → restore_sha256 출력. DB 쓰기 없음
PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py resync-restore \
    --backup logs/market/adjusted_price_backups/<파일>.json --symbol 047400
# 실제 복원: dry-run이 보여 준 restore_sha256과 쓰기 확인 플래그 필수
PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py resync-restore \
    --backup <파일> --symbol 047400 --confirm <restore_sha256> --i-understand-this-writes-db
```

- 백업 파일(형식 2): `payload_sha256`(파일 전체), `rows_fingerprint`(행), `row_count`, 날짜 중복, 대상 테이블,
  행마다 `source`·`adjustment_basis`·`collected_at`을 확인한다. 하나라도 어긋나면 `BackupInvalid`.
- 승인된 종목만: 상태 파일에 그 백업을 만든 `resync-apply` 기록(`applied_plan` 또는 `backup_path`)이 있어야 한다.
- 복원 전 정합성: 현재 DB 날짜 집합 = 백업 날짜 집합, 현재 DB 지문 = 백업의 `expected_after_fingerprint`
  (적용 직후 상태). 적용 뒤 새 일봉이 추가됐거나 값이 바뀌었으면 `blocked`. 이미 같으면 `already_restored`.
- `restore_sha256`은 백업과 '현재 DB 지문'을 함께 묶는다. dry-run 뒤 DB가 바뀌면 값이 달라져 실제 복원이 거부된다.
- 한 트랜잭션: 행 잠금 → 다시 확인 → 현재 값을 `pre-restore` 백업으로 기록 → 값·`collected_at`을 백업대로 UPDATE →
  다시 읽어 백업 지문·`collected_at`이 같은지 확인. 실패하면 전체 롤백. dry-run·결과는 `*_restore/`에 남는다.
- 복원 뒤 상태는 다시 `HISTORY_RESYNC_CANDIDATE`가 된다(복원한 옛 값은 최신 KIS와 다르기 때문).

### collected_at 정책

- 적용: 바뀐 행과 바뀌지 않은 행 모두 `collected_at`을 계획의 KIS 조회 시각(`kis_fetched_at`)으로 바꾼다.
  "이 값은 그 시각 KIS 응답으로 확인됐다"는 뜻이다. 원래 시각은 백업에 남는다.
- 복원: 백업에 있던 원래 `collected_at`으로 되돌린다.

### 새 계획이 필요한 경우

계획은 아래 중 하나라도 해당하면 적용이 거부되므로 `resync-plan`을 다시 실행한다.
`kis_fetched_at`에서 24시간이 지남 · finalize 등으로 그 종목 일봉이 추가·변경됨(지문·날짜 집합 불일치) ·
계획 파일이 바뀜(해시) · 재조회 상태가 `HISTORY_RESYNC_CANDIDATE`가 아님 · 기업행동 정정·매매 재개 등 새 증거.

## 6. 정기 실행

`memos-adjusted-price-check.timer` (2026-11-16 설치·활성화, 원본 `configs/systemd/`): 평일 14:30 KST(+최대 2분 무작위 지연)에
`detect` → `recheck --max-symbols 5 --max-requests 10`. DB 쓰기 없음. `resync-plan`·`resync-apply`·`resync-restore`는 넣지 않는다.

- 로그: `logs/market/adjusted_price_check.log` (stdout·stderr 누적), 결과 `logs/diagnostics/adjusted_price_manager/<시각>_detect|_recheck/`,
  상태 `logs/market/adjusted_price_state/state.json`
- 확인: `systemctl --user list-timers memos-adjusted-price-check.timer`, `systemctl --user status memos-adjusted-price-check.service`
- 중지: `systemctl --user disable --now memos-adjusted-price-check.timer` (기존 capture·finalize·morning 타이머와 무관)

## 6-1. 보류(hold)

기업행동 근거가 확인되지 않은 종목은 보류한다. 상태 파일에 남고, 재조회 결과로 상태가 바뀌어도 지워지지 않는다.
보류 중에는 `recheck`가 건너뛰고(`on_hold`), `resync-plan`·`resync-apply`가 거부한다(종료 코드 3).

```bash
PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py hold --symbol 047400 --reason "<사유>" --by <이름>
# 해제: 종목코드 재입력·승인자·근거·승인 플래그 필수. 해제 뒤 계획은 반드시 다시 만든다
PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py release-hold --symbol 047400 \
    --confirm-symbol 047400 --approved-by <승인자> --note "<근거: 공시 접수번호 등>" --i-approve-release
```

2026-11-16 현재: 047400 보류(기업행동 근거 미확인, ready 계획 적용 금지). 101140은 `SOURCE_DISCONTINUITY`로,
같은 증거 키이거나 이미 확인한 단절 날짜(`verified_dates`)만 다시 잡히면 다시 요청하지 않는다.

## 7. 테스트

```bash
PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests/test_corporate_actions.py \
  backend/tests/test_adjusted_recheck.py backend/tests/test_adjusted_resync.py \
  backend/tests/test_adjusted_history_diagnostics.py
```

### 격리 PostgreSQL 통합 테스트 (운영 DB 금지)

조건: localhost, 5432가 아닌 포트, DB 이름에 `test`, `DATABASE_URL`·`READONLY_DATABASE_URL`과 다른 주소.
예시 (Docker Desktop을 켠 뒤, 데이터는 컨테이너 안 tmpfs라 볼륨을 만들지 않는다):

```bash
# 포트: 55432는 Windows 예약 범위(55406~55505, Hyper-V)에 걸려 바인딩이 거부됐다. 2026-11-16 실행은 54329를 썼다.
# 예약 범위 확인: netsh interface ipv4 show excludedportrange protocol=tcp
docker run -d --rm --name memos-adjusted-test -p 127.0.0.1:54329:5432 \
  --env-file <POSTGRES_USER·POSTGRES_PASSWORD·POSTGRES_DB를 담은 파일> \
  --tmpfs /var/lib/postgresql/data:rw,size=1g pgvector/pgvector:pg16
# 스키마: 테스트 DB에만 alembic head 적용 (운영 ALEMBIC_DATABASE_URL을 쓰지 않도록 그 명령에서만 덮어쓴다)
ALEMBIC_DATABASE_URL=postgresql+psycopg://memos_test:<값>@127.0.0.1:54329/memos_adjusted_test .venv/bin/alembic upgrade head
ADJUSTED_RESYNC_INTEGRATION_DATABASE_URL=postgresql+psycopg://memos_test:<값>@127.0.0.1:54329/memos_adjusted_test \
  PYTHONPATH=backend .venv/bin/python -m pytest -q -rs backend/tests/test_adjusted_resync_postgres_integration.py
docker stop memos-adjusted-test   # --rm이라 컨테이너와 데이터가 함께 사라진다
```

실행 결과 (2026-11-16): PostgreSQL 16.15(pgvector) 격리 컨테이너에서 7개 모두 통과, 건너뜀 0.
`-rs`로 건너뛴 테스트가 없는지 꼭 확인한다(환경변수가 없으면 7개 모두 skip되며 통과가 아니다).

확인 항목: 정상 UPDATE 정합성·`collected_at`, 다른 종목·`prices_daily` 불변, 중간 실패 전체 롤백, 지문 불일치 거부,
sha256 불일치 거부, 백업 실패 시 UPDATE 거부, 적용 후 검증 실패 롤백, 복원 왕복·복원 중간 실패 롤백.

## 8. 한계

- 공시 데이터는 2026-10-21부터다. 그 이전 기업행동은 가격 탐지로만 찾는다.
- 권리락일·매매재개일이 원문에 없으면 확정하지 못한다. KIS가 조정을 반영하는 정확한 날짜는 종목마다 실측이 필요하다.
- 합병 비율처럼 서술형인 값은 숫자로 확정하지 않는다.
- 우선주와 보통주의 조정비율이 같은지는 재조회로만 확인한다.
- `SOURCE_DISCONTINUITY` 종목(예: 101140)은 차트에서 어떻게 보여 줄지 별도 결정이 필요하다.
