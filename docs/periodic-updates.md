# 정기보고서 증분 업데이트 (`run_periodic_updates`)

`run_all`(본문)과 `run_financials_all`(재무)은 처음 한 번 코스피 전체를 모으는 명령이에요. 대상 기간이
`configs/common.yaml`의 `periods`(2024-03-31 ~ 2026-06-30)로 고정돼 있고, 끝난 기업은 다시 보지 않아요.
그래서 그 뒤에 나온 보고서(3분기 보고서, 비12월 결산 기업의 새 보고서, 정정본)는 이 명령으로 받아요.

## 확정한 정책 (2026-11-06)

| 항목 | 정책 |
|---|---|
| 보존 | **계속 쌓기.** 오래된 기간을 지우지 않아요. 메모·카드가 참조한 공시를 지킬 수 있고, 늘어나는 양은 분기당 약 4GB예요. |
| 실행 | **매일 새벽 1회** (작업 스케줄러, 02:00). 보고서 시즌에는 임베딩이 하루를 넘길 수 있어서, 다음 실행이 남은 것부터 이어서 해요. |
| 정정본 | **현행 규칙 유지.** `loader.upsert_disclosure`가 같은 (종목, 종류, 기준일)의 예전 본을 교체해요. 서비스가 참조 중인 원본은 교체하지 않고 실패로 기록해요. |
| 범위 | **본문 + 재무 + 비율을 한 번에** 갱신해요. |

## 흐름

```
① 목록    날짜별 list.json (정기공시 A · 코스피 · 정정 이력 포함)
          기본 기간: 지난 실행 종료일 - 3일 ~ 오늘. 첫 실행은 2026-07-01부터
② 판단    사업·반기·분기보고서만 남기고, 아래 경우는 건너뜀
          · DB나 상태 파일에 이미 있는 접수번호
          · DB의 같은 슬롯이 같거나 더 새 접수번호 (DB에 정정본이 있고 목록에 원본이 나온 경우)
          · [첨부추가]·[첨부정정] (첨부만 바뀌어 본문이 같음. 받으면 같은 본문을 통째로 다시 임베딩하게 됨)
          · 2024-01-01 이전 기간 (대상 기간 밖 보고서의 정정본)
③ 본문    run_all의 BatchRun 그대로: collect → parse → chunk → load (슬롯 선택만 계획한 슬롯으로)
④ 재무    본문을 받은 (종목, 기준일)은 그 기간 재무 API를 다시 받아(refresh) financials·financials_fin 갱신
          재무 API에 아직 자료가 없으면(013) 다음 실행에서 다시 봐요 (최대 14일)
⑤ 비율    재무를 갱신한 금융사만 run_financial_ratios (BIS · K-ICS · NCR)
⑥ 임베딩  이번·이전 실행에서 저장했는데 아직 임베딩 없는 청크
⑦ 검증    임베딩까지 끝난 문서에 validate (dense·sparse 빈 값, 노름, 매니페스트 일치 등)
```

재무와 비율을 임베딩보다 먼저 해요. 그래서 카드에 쓰는 숫자는 임베딩이 몇 시간 걸려도 바로 갱신돼요.

## 실행

```bash
# 계획만 (DB 읽기 전용, 원문 다운로드·쓰기 없음)
PYTHONPATH=backend python -m pipelines.disclosures.run_periodic_updates --dry-run

# 실행
PYTHONPATH=backend python -m pipelines.disclosures.run_periodic_updates --offline

# 테스트 DB에서 몇 개사만 (상태 폴더를 따로 써야 실제 상태와 섞이지 않아요)
scripts/with_test_db.sh python -m pipelines.disclosures.run_periodic_updates --symbols 005850,015360 \
  --state-dir data/periodic_updates_test --offline
```

| 옵션 | 뜻 |
|---|---|
| `--since`, `--until` | 목록 기간 (기본: 지난 종료일 - 3일 ~ 오늘) |
| `--symbols` | 이 종목만 (시험용) |
| `--max-companies N` | 계획의 앞 N개사만 (시험용) |
| `--no-embed` | 임베딩·검증을 건너뜀 (다음 실행이 채워요) |
| `--state-dir` | 상태 폴더 (기본 `data/periodic_updates`) |

종료 코드: 0 정상 · 1 실패 있음 · 3 DART 한도(020, 다음 실행에서 이어 감) · 4 API 키 없음.

### 작업 스케줄러 (사용자가 등록)

```powershell
# 미리 시험 (DB에 쓰지 않음)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_periodic_updates.ps1 -DryRun
# 등록 (매일 02:00) / 해제
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_periodic_updates_task.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_periodic_updates_task.ps1 -Uninstall
```

로그는 `logs\periodic_updates\`(run_*.log, history.log)에 남아요. 수시공시 작업(12:30·19:30)과 시간이 겹치지 않아요.

## 상태와 결과 파일 (`data/periodic_updates/`)

| 파일 | 내용 |
|---|---|
| `state.json` | `last_until`(마지막 목록 종료일), `handled`(처리한 접수번호와 결과), `attempts`(실패 횟수), `pending_financials`(재무 대기), `embed_queue`(임베딩 남은 문서) |
| `runs/run_*.json` | 실행마다 계획·본문 실패·재무·비율·임베딩·검증 결과 |
| `manifest.jsonl` | 청크 해시 (검증용) |
| `provenance/{종목}.jsonl` | 재무 컬럼별 출처 |
| `ratios/` | 비율 결과·검토 목록 |

`handled`의 status:
- `loaded`: 본문을 저장했어요. fingerprint가 같아 건너뛴 경우도 포함해요.
- `gave_up`: 3번 실행해도 실패했어요. 예를 들어 DART 원문이 없거나(014), 참조 중이라 교체를 보류했거나, 리츠처럼 결산월 규칙과 맞지 않아 슬롯을 못 고른 경우예요. 다시 받으려면 그 접수번호를 `handled`에서 지우면 돼요.

## 규모 (2026년 3분기 보고서)

- 마감: 9/30 + 45일 = 11/14(토) → **11/16(월)**. 코스피 약 795개사가 11/13~16에 몰려요.
- 분기보고서 1건은 평균 356청크예요. 795건이면 약 28만 청크이고, RTX 3060 노트북 GPU(초당 5~7청크)로 **11~16시간** 걸려요.
- DART 호출은 기업당 목록 3회, 원문 1회, 재무 2~4회예요. 하루 한도(약 2만 회) 안에 들어와요.

## 첫 실행 dry-run (2026-11-06, 중앙 DB 읽기)

2026-07-01 ~ 11-06 목록에서 정기보고서 913건이 나왔어요.
- 893건은 이미 반영돼 있어요.
- 처리할 슬롯은 **20개(18개사)**예요. 신규 19건(비12월 결산 반기·사업보고서, 일찍 낸 3분기 2건 등)과 정정 1건이에요.
- 첨부만 바뀐 제출본 92건, 대상 기간 전 정정본 6건은 건너뛰었어요.
