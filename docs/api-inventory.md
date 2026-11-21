# API 목록 (연결 0단계)

기준: `dev` `e84571a`. 백엔드 라우터 데코레이터 grep 결과입니다(테스트 제외). 실제 경로 = 라우터 prefix + 데코레이터 경로입니다.

## 1. 엔드포인트 (60개)

| 메서드 | 경로 | 파일 |
|---|---|---|
| GET | /health · /health/db | app/main.py |
| GET | /api/v1/auth/{provider}/start · /{provider}/callback | app/auth/routes.py |
| POST | /api/v1/auth/mobile/exchange · /refresh · /logout | app/auth/routes.py |
| GET | /api/v1/auth/me | app/auth/routes.py |
| GET · POST | /api/v1/stocks | app/stocks/routes.py |
| GET | /api/v1/stocks/search · /api/v1/stocks/{code} | app/stocks/routes.py |
| PATCH · DELETE | /api/v1/stocks/{code} | app/stocks/routes.py |
| PUT | /api/v1/stocks/order | app/stocks/routes.py |
| GET | /stocks/{code}/board · /board-items/{memo_id} · /memos/pinned | app/board/routes.py |
| PUT | /stocks/{code}/board-order · /memos/{memo_id}/ai-link | app/board/routes.py |
| POST | /stocks/{code}/memos · /checklists · /references · /memos/{memo_id}/confirmations | app/board/routes.py |
| PATCH | /board-items/{memo_id} · /checklists/{memo_id}/items/{item_id} | app/board/routes.py |
| DELETE | /board-items/{memo_id} | app/board/routes.py |
| GET | /updates · /stocks/{code}/ai-updates · /memos/{memo_id}/timeline · /ai-updates/summary | app/updates/routes.py |
| POST | /ai-updates/{update_id}/read | app/updates/routes.py |
| GET | /memos/{memo_id}/answers | app/answers/routes.py |
| GET | /stocks/{code}/quote · /candles · /profile · /financials | app/marketdata/routes.py |
| GET | /news/headlines · /market/overview | app/marketdata/routes.py |
| GET | /me/usage | app/credits/routes.py |
| GET | /ai/stats · /data/stats | app/stats/routes.py |
| POST | /feedback | app/stats/routes.py |
| GET · PUT | /home/layout | app/account/routes.py |
| GET · PATCH | /settings · /me | app/account/routes.py |
| GET · POST | /checklist-items | app/home/routes.py |
| GET | /price-conditions | app/home/routes.py |
| PATCH | /memos/{memo_id}/price-conditions/{condition_id} | app/home/routes.py |
| GET · POST | /api/v1/journal | app/journal/routes.py |
| PATCH · DELETE | /api/v1/journal/{entry_id} | app/journal/routes.py |
| GET | /api/v1/trash | app/trash/routes.py |
| POST | /api/v1/trash/{trash_id}/restore | app/trash/routes.py |
| DELETE | /api/v1/trash/{trash_id} | app/trash/routes.py |

(prefix 없는 줄은 `/api/v1` 아래)

## 2. 화면 항목별 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| 로그인·세션 | 있음·그대로 | app/auth/routes.py |
| 종목 | 있음·그대로 | app/stocks/routes.py |
| 메모 CRUD·position | 있음·그대로 (board-order) | app/board/routes.py |
| 체크리스트 pinned | 있음·그대로 | app/board/schemas.py |
| AI 연결 | 있음·그대로 (ai-link · confirmations) | app/board/routes.py |
| 업데이트 타임라인 | 있음·그대로 | app/updates/routes.py |
| 시세·차트 | 있음·그대로 (quote · candles) | app/marketdata/routes.py |
| 지수·매크로 | 있음·보강 (market/overview만 · 매크로 지표 없음) | app/marketdata/routes.py |
| 재무 | 있음·그대로 | app/marketdata/routes.py |
| 홈 뉴스 | 있음·그대로 (news/headlines) | app/marketdata/routes.py |
| 질문 답 | 있음·그대로 (읽기만) | app/answers/routes.py |
| 크레딧·사용량 | 있음·보강 (사용량 읽기만 · 충전·차감 API 없음) | app/credits/routes.py |
| 스튜디오 결과물 | 없음 (표 studio_items · audio_assets만, 라우트 없음) | alembic/versions/0019_ai_outputs_and_credits.py |
| 투자 기록 (blocks) | 있음·그대로 | app/journal/routes.py |
| 사용자 설정 (user_settings) | 있음·그대로 | app/account/routes.py |
| 사이드바 종목 순서 | 있음·그대로 (PUT stocks/order) | app/stocks/routes.py |
| 휴지통 | 있음·그대로 | app/trash/routes.py |
| 알림함 | 없음 (알림 설정만) | app/account/schemas.py |
| 피드백 | 있음·그대로 | app/stats/routes.py |
| 약관 동의 | 없음 | — (backend/app 에 terms·consent 없음) |
| 탈퇴 | 없음 | — (backend/app 에 withdraw·탈퇴 없음) |

## 3. 구조

- 투자 기록 `journal_entries.blocks` (jsonb, 원본 · `body`는 blocks로 만든 Markdown): 블록 `type` = paragraph(text · highlight) / heading(text · highlight) / checklist(text · checked) / table(rows) / attachment(name …) — app/journal/markdown.py
- `user_settings` 칸: notify_disclosure · notify_news · notify_price_condition · notify_surge · surge_threshold_pct · notify_push · notify_email · notify_in_app · notify_frequency · quiet_hours_enabled · quiet_start · quiet_end · ai_default_on · ai_source_disclosure · ai_source_news · ai_source_price · ai_sensitivity · price_color — app/account/service.py
