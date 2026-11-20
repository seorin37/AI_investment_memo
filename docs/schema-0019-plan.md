# 마이그레이션 0019 — 질문 답·스튜디오 결과물·크레딧 (2026-11-20 초안)

파일: `alembic/versions/0019_ai_outputs_and_credits.py` (0018 다음)

## 1. 왜 필요한가
중앙 DB(0018)에는 **카드**(`tracking_updates`)만 저장할 곳이 있다. 앱 화면에 이미 있는 아래 기능은 저장할 곳이 없다.

| 기능 | 화면 | 지금 |
|---|---|---|
| 질문 답·즉시 답변 | 메모 상세 AI 탭 | 실험 결과 파일에만 있음 |
| 주간보고서·AI 오디오·투자 실험실 | 스튜디오 (만든 항목 30일 보관) | 테이블 없음 |
| 크레딧 | MY·스튜디오 "이번 달 AI 사용량 %", 다 쓰면 AI 업데이트 멈춤·크레딧 구매 | 추적 항목 개수 한도(`plan_limits`)만 있음 |
| 비교 메모·결론 낼 메모 위젯 | 홈 | 비교 상대·원래 메모를 담을 칸 없음 |

## 2. 원칙
1. 사용자 데이터는 모두 `users`까지 FK로 이어지고, 사용자를 지우면 같이 지워진다.
2. 덜 정해진 내용(리포트·오디오 대본 모양)은 jsonb에 둔다. 모양이 바뀌어도 마이그레이션이 필요 없다.
3. 크레딧은 묶음 + 장부. 잔액이 틀려도 장부로 다시 계산할 수 있다.
4. 기존 데이터는 바꾸지 않는다. 새 칸은 NULL 허용이거나 기본값이 있다.

## 3. 사용자 연결 구조 (0019 후)
```
users
├─ memos  (position(새): 보드 안 순서)
│   └─ tracking_items  type: topic | price_below | price_above | ask(새) | compare(새)
│       └─ tracking_updates  type: news | disclosure | price | price_condition | answer(새)
│           └─ update_sources
├─ journal_entries ── source_memo_id(새) → memos
├─ studio_items(새)  kind: report | audio | lab
│   └─ audio_assets(새)
├─ credit_grants(새) ─┐
└─ credit_ledger(새) ─┘ grant_id
plan_limits.monthly_credits(새)
user_settings.auto_audio / auto_report(새)
```

## 4. 바뀌는 것

### ① 질문 답·즉시 답변 — 새 테이블 없음
- 질문 문장 → `tracking_items.type='ask'`. 한 번 답하면 `status='done'`.
- 답 → `tracking_updates.type='answer'`, 출처 → `update_sources`. 카드와 같은 읽음 표시·메모 수정본 연결을 쓴다.
- `details`(jsonb)에 `{"status": "answer"|"no_answer", "mode": "daily"|"instant", "fin_table": …, "calc": …}`.
- 즉시 답변(저장하자마자)과 06:30 답변은 **답하는 시점만 다르다**. 같은 행 모양이고 `details.mode`로 구분한다.
- 비교 메모: `type='compare'` + `target_symbol` (compare일 때만 값이 있어야 함, CHECK).
- 수시공시 카드: `tracking_items.topic` (earnings·shareholder_return·business·capital·risk·schedule, `event-card-criteria.md` 결정 1).
- 결론 → 투자 기록: `journal_entries.source_memo_id` (메모가 지워지면 NULL).
- 메모 보드 순서: `memos.position` (팀장님 질문 2026-11-20). 앱은 이미 `position` 순으로 그리는데 백엔드가 작성 순으로 계산만 하고
  "순서 저장 칸이 없어 변경 불가"로 막고 있었다(`backend/app/board/service.py`). 보드 하나 = 사용자 × 종목이라 별도 테이블 없이 칸 하나로 된다.
  기존 메모는 지금 화면 순서(작성 순)로 채운다. 옮길 때는 그 보드의 position을 0부터 다시 매긴다(보드당 메모 수가 적음).

### ② 스튜디오 결과물 — `studio_items`, `audio_assets`
| 칸 | 뜻 |
|---|---|
| `kind` | report · audio · lab |
| `trigger` | auto(정해진 주기) · request(사용자 요청) |
| `status` | queued → generating → ready / failed |
| `period_start/end`, `symbols` | 다룬 기간·종목 |
| `content` | 화면 모양 그대로 jsonb (주간보고서 = `WeeklyReport.types.ts`, 라디오 = 대본, 실험실 = 결과) |
| `sources` | 출처 목록 (공시 접수번호·뉴스 ID) |
| `credits_used` | 이 결과물에 쓴 크레딧 |
| `expires_at` | 기본 30일 뒤 |

- 자동 생성은 `(user_id, kind, period_start)`가 겹치지 않는다 (같은 주 보고서가 두 번 생기지 않게).
- `audio_assets`: 파일은 DB 밖에 두고 위치(`storage_path`)·길이·목소리·대본 해시(`text_hash`, 같은 대본 재사용)·이어 듣기 위치만 저장한다.
- `user_settings.auto_audio`(기본 끔), `auto_report`(기본 켬): 자동 생성 받기.

### ③ 크레딧 — 산 크레딧은 다음 달로 넘어간다
- `plan_limits.monthly_credits`: 요금제별 한 달 기본량 (값은 결정 후 UPDATE).
- `credit_grants`(묶음): 들어온 크레딧 한 덩어리.
  - `monthly`: 갱신일마다 1개, 다음 갱신일에 만료. 같은 기간 두 번 지급 안 됨.
  - `purchase`: 결제 1건에 1개, **다음 달로 넘어감** (`expires_at`은 정책값 또는 NULL). 같은 결제번호 두 번 지급 안 됨.
  - `bonus`, `refund`
- `credit_ledger`(장부): 충전 +, 사용 −, 만료 − 한 줄씩. 무엇에 썼는지(`reason`, `ref_kind`·`ref_id`).
- `tracking_usage_events`(0행)는 쓰지 않는다.

**쓰는 순서와 계산**
```
잔액      = 만료 안 된 묶음의 remaining 합
쓸 때     = 그 사용자 묶음을 잠그고(SELECT … FOR UPDATE) 만료가 빠른 것부터 remaining을 줄인다
            → 이번 달 기본량을 먼저 쓰고, 산 크레딧은 나중에 쓴다
            → 묶음마다 장부 한 줄 (grant_id)
사용량 %  = 이번 갱신 기간에 쓴 양 ÷ (이번 기간 기본량 + 기간 시작 때 남아 있던 산 크레딧 + 기간 중 산 크레딧)
다 쓰면   = 06:30 실행기가 그 사용자를 건너뛰고, 앱은 ai_paused
만료      = 정리 작업이 만료된 묶음의 remaining을 0으로 만들고 장부에 expire 줄
```

## 5. 되돌리기
`alembic downgrade -1`은 새 테이블·칸을 지운다. enum에 더한 값(ask·compare·answer)은 PostgreSQL에서 뺄 수 없어 남는다.
ask·compare 항목이나 answer 카드가 이미 있으면 되돌리기를 멈춘다(데이터 보호).

## 6. 값 결정 (마이그레이션과 무관, 출시 전까지)
| # | 결정 | 추천 |
|---|---|---|
| 1 | 기능별 크레딧 값 | 비용 비례 (카드 1·답 1·리포트 5·오디오 5·실험실 3 같은 식) |
| 2 | free/pro 한 달 기본량 | 비용 실측 후 |
| 3 | 매일 카드도 크레딧을 쓰나 | 쓴다 |
| 4 | 질문(ask)을 추적 항목 한도에 세나 | 안 센다 (크레딧만) |
| 5 | 산 크레딧 유효기간 | 1년 (넘어감은 확정, 2026-11-20) |
| 6 | 오디오 파일 위치·TTS 업체 | 개발 중 서버 폴더 → 출시 때 클라우드 |
| 7 | 자동/요청 생성 | 라디오 매일 자동(켠 사람만), 리포트 주 1회 자동 + 요청 |

## 7. 적용 순서
1. 테스트 DB에서 `upgrade` → `downgrade -1` → `upgrade` 확인
2. 서린 님(06:30 실행기·질문 답)과 앱 담당(API)에 공유
3. dev 머지와 중앙 DB 적용을 같은 날 (공시·재무 적재 코드가 DB 버전 = 코드 버전을 확인함)
4. 코드 연결 순서: 질문 답 저장 → 크레딧 차감(06:30) → 스튜디오 생성

## 8. 이번에 넣지 않은 것
- 오늘의 퀴즈 (`quiz_questions`·`quiz_submissions`): 보상 없음·크레딧 무관이라 별도로.
- 결제(영수증·환불 절차): 결제 방식이 정해지면. 지금은 `payment_ref`만.
