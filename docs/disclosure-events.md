# 수시공시 수집 (run_events)

코스피 상장사의 수시공시를 매일 받아 DB에 저장한다. 목적은 **"새 공시 → 메모 카드"** 흐름의 재료를 만드는 것이다.
숫자(배당금, 계약금액, 잠정실적 등)는 원문 표에서 **규칙으로** 뽑고, LLM은 쓰지 않는다.

- 설정: `configs/disclosure_events.yaml`
- 코드: `backend/pipelines/disclosures/` 의 `events_list.py`(목록·거르기), `events_parse.py`(원문 표 읽기),
  `events_fields.py`(항목값 뽑기), `events_loader.py`(DB 저장), `run_events.py`(실행)
- 테이블: `disclosure_events` (마이그레이션 `0014_disclosure_events`) + 기존 `disclosures`, `disclosure_chunks`

## 1. 모으는 것

- **대상**: 코스피(`corp_cls=Y`)의 주요사항보고서(B), 거래소공시(I), 기타공시(E).
  - `disclosures.kind`는 B → `major`, I·E → `other`. `period_end`는 비운다(정기보고서가 아니므로).
- **종류**: 보고서명을 정리한 뒤 설정의 `events` 패턴으로 33가지 `event_type`으로 나누고, 6개 `topic`으로 묶는다.

| topic | 뜻 | 주요 event_type |
|---|---|---|
| `earnings` | 실적 | 잠정실적, 매출·손익 30% 이상 변동, 실적 전망, 결산실적 예고 |
| `shareholder_return` | 주주환원 | 배당, 자사주 취득·처분, 주식 소각, 기업가치 제고 계획 |
| `business` | 사업 | 공급계약 체결·해지, 기술도입·이전·제휴, 시설투자, 타법인 주식 취득·처분, 유형자산 거래, 영업양수도, 장래사업계획, 기타 경영사항 |
| `capital` | 자본·구조 | 유상·무상증자, CB·BW·EB 발행, 합병·분할·주식교환, 주식 병합·분할, 감자, 최대주주 변경 |
| `risk` | 위험 | 풍문 해명, 조회공시, 투자주의·관리종목·상장적격성, 생산중단, 감사보고서, 거래정지, 회생·부도, 소송 |
| `schedule` | 일정 | IR 개최 |

- **자회사 공시**: `(자회사의주요경영사항)`, `(종속회사의주요경영사항)`이 붙은 것도 받고 `is_subsidiary=true`로 표시한다.
- **원본과 정정본 모두** 받는다(`last_reprt_at=N`). 원본을 지우지 않고 정정본과 연결한다(4절).

## 2. 모으지 않는 것과 이유

### 2-1. `[첨부정정]` 제출본 — 설정 `skip_prefixes`

공시는 **본문**(합병 비율, 계약 금액 같은 공시 내용 표)과 **첨부서류**(외부평가 의견서, 계약서, 이사회 의사록 등)로 되어 있다.
제목 앞 꼬리표는 다시 낸 이유를 나타낸다.

| 꼬리표 | 뜻 | 수집 |
|---|---|---|
| `[기재정정]` | 본문 내용을 고쳐서 다시 냄 | **받는다** (고친 값이 본문에 있음, `is_correction=true`) |
| `[첨부정정]` | 본문은 그대로, 첨부서류만 고쳐서 다시 냄 | **받지 않는다** |
| `[첨부추가]` | 첨부서류를 붙여서 냄 | **받는다** (본문이 있고, 그 사건의 유일한 공시일 수 있음. `is_correction=false`) |

`[첨부정정]`을 빼는 이유:
- DART가 본문 파일을 주지 않는다. `document.xml`로 받으면 **`014: 파일이 존재하지 않습니다`** 가 난다.
  2026-10-21 ~ 11-04의 `[첨부정정]`은 12건(합병 9, 주식교환 1, 잠정실적 1, 지속가능경영 1)이었다.
  지속가능경영(원래 제외 대상)을 뺀 11건을 받아 봤고 11건 모두 014였다.
- 우리가 쓰는 항목값은 전부 본문에 있고, 본문은 원래 공시와 같다. 원래 공시(또는 `[기재정정]`)는 제출일에 따로 받으므로 잃는 값이 없다.
- 받으려 하면 매번 실패로 남아 다음 실행 때마다 다시 시도하게 된다.

`[첨부추가]`를 받는 이유:
- 같은 기간의 `[첨부추가]` 1건(아센디오 회사합병결정, 20261023000356)은 본문이 정상으로 받아졌다.
- 이사회 결의일이 제출일(10/23)과 같고, 2025~2026년에 아센디오의 다른 회사합병결정 공시는 없었다.
  즉 이 합병을 알리는 **유일한 공시**였다. 빼면 사건 자체를 놓친다.
- 원래 공시가 따로 있는 경우에는 같은 내용이 두 번 저장될 수 있다. 놓치는 것보다 낫다고 보고 받는다.

합병 결정에서 특히 많이 나온다(외부평가 의견서 등 첨부가 많아서).
처음(2026-11-05)에는 `[첨부추가]`도 뺐다가, 위 확인 뒤 다시 받도록 바꿨다.
몇 건을 뺐는지는 dry-run·실행 보고서의 `skipped_prefix`에 남는다.

### 2-2. 카드로 쓸 일이 거의 없는 종류 — 설정 `exclude`

양이 많거나 투자 판단 카드와 거리가 먼 공시다. 예:
- 최대주주등소유주식변동신고서 (하루 수십 건, 2주에 약 100건)
- 주주총회 소집·결과, 주주명부폐쇄, 사외이사·대표이사 변경
- 금전대여, 채무보증·담보제공, 단기차입금 증가
- 자기주식 취득·처분 **결과** 보고서, 신탁계약 결과 보고서 (결정 공시는 받는다)
- 유상증자·사채의 후속 공시: 신주발행가액 확정, 청약결과, 발행결과 (결정 공시는 받는다. 2026-11-05 팀장 결정: 유상증자는 결정 공시만으로 충분)
- 주식매수선택권 부여, 전환가액 조정, 지속가능경영보고서 등

전체 목록은 설정 파일의 `exclude`를 본다. 뺀 공시는 보고서의 `excluded_titles`에 건수만 남는다.

### 2-3. 어느 규칙에도 맞지 않는 공시

`exclude`에도 `events`에도 없는 새 보고서명은 저장하지 않고 보고서의 `unclassified_titles`에만 남긴다.
새 공시 종류를 놓치지 않게 dry-run 결과를 가끔 확인해서, 필요하면 `events`나 `exclude`에 추가한다.

### 2-4. DB `stocks`에 없는 종목

`disclosures.symbol`이 `stocks`를 참조하므로, `stocks`에 없는 종목은 건너뛰고 `skipped_unknown_symbol`에 남긴다.

## 3. 저장되는 모습

공시 1건마다 세 곳에 쓴다(1건 = 1트랜잭션).

- `disclosures`: 접수번호, 종목, 제목, kind, 접수일, DART 링크
- `disclosure_events`
  - `fields`: 규칙으로 뽑은 값. 금액은 원 단위 정수, 날짜는 `YYYY-MM-DD`. 예) 배당 `{"dps_common": 160, "record_date": "2026-09-30"}`
  - `pairs`: 원문 표 전체를 `항목 경로: 값` 목록으로. 규칙이 놓친 값이 있어도 원문을 다시 받지 않고 다시 뽑을 수 있다.
  - `parse_status`: `ok`(필수 값 다 있음) / `partial`(일부 없음) / `failed`(원문을 못 받거나 못 읽음)
  - `parse_issues`: 빠진 값, 경고
- `disclosure_chunks`: `[회사 날짜 수시공시 | 제목]` 머리말 + `항목: 값` 줄. 값이 `-`인 줄은 뺀다. `block_type=event`, 1,500자 단위로 나눈다.
  임베딩은 정기보고서와 같은 BGE-M3 설정으로 채운다.

항목값 규칙은 13가지 종류에만 있다(잠정실적, 배당, 자사주 취득·처분, 소각, 공급계약, 풍문 해명, 장래사업계획, 시설투자, 결산 예고, IR, 기타 경영사항, 유상증자).
나머지 종류는 `pairs`와 청크만 저장한다.

### 원문에 원래 값이 없는 경우: `ok` + `fields.note`

필수 값이 비었어도 원문에 원래 그 값이 없는 공시는 `partial`이 아니라 `ok`로 저장한다.
사유는 `fields.note`와 `parse_issues`에 남긴다(`events_fields.expected_missing_note`).

| `fields.note` | 조건 | 예 |
|---|---|---|
| `monthly_operating` | 잠정실적인데 대상 기간(`period_start`~`period_end`)이 한 달 이하. 표준 표의 매출·영업이익 칸을 비우고 판매대수·판매량 등 회사 기준 실적을 아래에 적는다 | 현대차·기아·KG모빌리티 판매대수, GKL·파라다이스 카지노 매출, 지역난방공사 판매량 |
| `amount_withheld` | `공시유보 관련내용 > 유보사유`에 사유가 있음 (모든 종류) | 아시아나항공 항공기 임차 연장 시설투자 |

- 카드에 숫자를 넣을 수 없다는 신호로 쓰면 된다. `monthly_operating`은 분기 실적이 아니므로 실적 카드와 섞지 않는다.
  회사 기준 실적은 `pairs`와 청크에 그대로 있다.
- 분기 잠정실적에서 매출·영업이익이 비면 그대로 `partial`이다 (검토 대상).
- 2026-11-06 반영 전에 저장된 8건(10/22, 11/02~11/03)은 `--reparse`로 다시 저장한다.
  청크 내용은 같아서 임베딩은 다시 하지 않는다.

## 4. 정정공시 처리

- 원본은 **지우지 않는다**. 정정본의 `corrects`에 원본 접수번호를 넣어 연결한다.
- 정정본 맨 앞의 정정표에서 `정정일자`, `정정관련 공시서류`, `정정관련 공시서류제출일`, `정정사유`를 `correction`에 담는다.
- 원본 찾기: 같은 종목, 같은 보고서명, 더 앞선 접수번호 중 가장 최근 것. 원래 제출일을 알면 그날 접수된 것만 본다.
- **추측하지 않는다**: 원래 제출일의 공시가 DB에 없으면 `corrects`는 비워 두고 `correction.original_date`만 남긴다.
  (수집 기간 밖의 원본을 고친 정정공시가 대부분 이 경우다.)
- 정정표 칸을 **바꿔 적은** 공시(예: 1번 서류명 칸에 날짜, 2번 제출일 칸에 서류명)는 날짜인 쪽을 제출일로 쓴다.
  둘 다 날짜가 아니면 원본을 연결하지 않고, 적힌 글자를 `correction.original_date_raw`에 남긴다.

## 5. 실행

`(ai_memo)` 환경, 저장소 루트에서 실행한다. 저장 모드는 `DATABASE_URL`의 DB에 쓰고, 시작할 때 접속 대상을 출력한다.

```bash
# 미리 보기 (DB에 쓰지 않음): 종류별·날짜별 건수 → data/events/dryrun_*.json
PYTHONPATH=backend python -m pipelines.disclosures.run_events --dry-run --since 2026-10-21 --until 2026-11-04

# 오늘치 저장 + 임베딩 (하루 2번 실행용)
PYTHONPATH=backend python -m pipelines.disclosures.run_events

# 기간 몰아 받기
PYTHONPATH=backend python -m pipelines.disclosures.run_events --since 2026-10-21 --until 2026-11-04
```

| 옵션 | 뜻 |
|---|---|
| `--date` / `--since` / `--until` | 기간 (기본: 오늘, KST) |
| `--dry-run` | DB를 쓰지 않고 집계만 |
| `--reparse` | 이미 저장한 공시도 원문을 다시 읽어 저장 (규칙을 바꾼 뒤) |
| `--no-embed` | 청크만 저장하고 임베딩은 다음 실행에서 |
| `--no-cache` | 지난 날짜 목록도 DART에서 다시 받기 |

동작 규칙:
- **이어 받기**: 같은 파서 버전으로 이미 저장한 공시(`failed` 제외)는 건너뛴다. 실패한 것만 다시 시도한다.
- **임베딩**: 이번에 저장한 공시만이 아니라 **기간 안 공시 전체**에서 임베딩이 빠진 청크를 채운다.
  앞 실행이 임베딩 전에 멈췄거나 `--no-embed`로 돌렸어도, 같은 기간으로 다시 실행하면 채워진다.
- **목록 캐시**: 지난 날짜 목록만 `data/raw/dart/events/lists/YYYYMMDD.json`에 저장하고 다시 받지 않는다.
  오늘 목록은 하루 중에도 늘어나므로 저장하지 않는다. 그날이 끝나기 전에 쓴 옛 캐시 파일(파일 시각이 그날)도 믿지 않고 다시 받는다.
  그래서 하루 마지막 실행 뒤에 나온 공시는 **다음 날 실행이 어제~오늘을 받을 때** 들어온다. 자동 실행은 `--since 어제`로 돌린다.
- **DART 한도(020)**: 그 자리에서 멈추고 종료 코드 3. 다음 실행에서 이어 받는다.
- **한 건 저장 실패**: 그 건만 되돌리고 `failures`에 남긴 뒤 계속한다. **5건 연속**이면(DB 장애 등) 멈춘다.
- **점검**: 저장 전 DB의 alembic 버전이 코드와 같은지, `disclosure_events`가 있는지 확인한다. 다르면 시작하지 않는다.
- 결과: `data/events/run_*.json` (저장 건수, parse_status별 건수, 실패 목록, 임베딩 결과)

### 5-1. 매일 자동 실행 (Windows 작업 스케줄러)

GPU가 있는 Windows PC에서 매일 12:30, 19:30에 돈다. 기간은 **어제~오늘(KST)** 이다(목록 캐시 규칙 참고).

```powershell
# 미리 시험 (DB에 쓰지 않음)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_event_disclosures.ps1 -DryRun
# 작업 등록 / 해제
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_event_disclosure_task.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_event_disclosure_task.ps1 -Uninstall
# 상태 확인 / 지금 한 번 실행
Get-ScheduledTask -TaskName MemoEventDisclosures | Get-ScheduledTaskInfo
Start-ScheduledTask -TaskName MemoEventDisclosures
```

- `scripts/run_event_disclosures.ps1`: 한 번 실행. ai_memo 환경의 python, `.env`의 `DATABASE_URL`, 모델은 로컬 캐시(`--offline`).
  같은 실행이 이미 돌고 있으면 바로 끝낸다(종료 코드 10).
- `scripts/install_event_disclosure_task.ps1`: 작업 `MemoEventDisclosures` 등록. 로그인한 사용자로, 로그인해 있을 때만 돈다(비밀번호 저장 안 함).
  PC가 꺼져 시간을 놓치면 켜진 뒤 한 번 돈다. 앞 실행이 돌고 있으면 건너뛰고, 2시간이 넘으면 멈춘다.
- 로그: `logs/event_disclosures/`
  - `history.log`: 실행마다 한 줄(시각, 기간, 종료 코드와 뜻, 걸린 시간). **먼저 이것만 보면 된다.**
  - `run_*.log`(요약 출력), `run_*.err.log`(진행·경고·오류 로그). 30일 지나면 지운다.
- 종료 코드 3(DART 한도)은 다음 실행에서 이어 받으므로 따로 할 일이 없다. 1이 이어지면 `run_*.err.log`를 본다.

## 6. 규모 (2026-10-21 ~ 11-03, 영업일 10일 기준)

- DART 목록 1,280건 → 거르고 남은 것 932건 (하루 약 90건, 정정본 약 15%)
- 공시 1건당 청크 약 1.7개, 원문 ZIP 약 6KB
- 1년이면 약 2만 3천 건, 청크 약 4만 개 — 정기보고서 청크(약 337만 개)의 1~2%
