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

## 전수 검사 (2026-11-21)

### 규칙 (모든 묶음 공통)

- 대상: `frontend/src/ui/screens/**`, `frontend/src/store/*`, `*.mock.ts`(My.mock · Studio.mock.ts · Journal.mock.ts 포함), `src/types/models.ts`, `frontend/docs/API_CONTRACT.md`, 기존 API 호출 코드(`frontend/src/api/*`) ↔ backend `app/*/schemas.py` · `routes.py` · `models.py`, `alembic/versions`
- 표 A 데이터: | 화면 | mock 출처(파일·상수/함수) | 필드 | 백엔드(파일·스키마.필드) | 판정 | 메모 |
- 표 B 동작: | 화면 | 동작 | 프론트 위치(파일·함수) | 엔드포인트(METHOD 경로·파일) | 판정 | 메모 |
- 판정: 그대로 / 이름만 다름(→백엔드 이름) / 계산 필요(프론트·백엔드 중 어디) / 없음 / 확인 필요
- 표 C 새로 만들 것: | 항목 | 종류(엔드포인트·DB칸·표·프론트) | DB 변경(Y/N) | 메모 |
- '그대로 · 이름만 다름'은 백엔드 파일·클래스명을 반드시 적는다. 근거 없으면 '확인 필요'. DB 적용 상태는 확인 불가(마이그레이션 파일 기준만).
- 팀원 백엔드는 고치지 않는다. 고칠 게 보이면 메모에 '담당자 상의'.
- 경로 줄임: 프론트 `fe/` = `frontend/src/`, 백엔드 `be/` = `backend/app/`. 백엔드 경로는 모두 `/api/v1` 접두.
- DB 칸 근거는 ORM 정의(파일·클래스) 우선, 없으면 마이그레이션.
  - 확인 결과(`grep -rn "__tablename__" backend/app`): 0건. `models.py`·`DeclarativeBase`·`mapped_column`도 없다(백엔드는 SQL 직접 사용).
  - 그래서 DB 칸 근거 = `alembic/sql/0001_schema_full_v1_2.sql`(0001이 이 파일을 실행) + `alembic/versions/0002~0021`의 `ALTER TABLE`·`CREATE TABLE`. 표기: `0001sql users` · `0019 studio_items` 처럼.
- 메모 — 기기 저장소 패키지(`frontend/package.json`):
  - `expo-secure-store ~58.0.2` 있음 → `fe/lib/storage.ts` `storage.get/set/remove` (앱: SecureStore, 웹: `localStorage`). 지금 쓰는 키: `memos.refresh_token` · `memos.mock_token` (store/auth.ts).
  - `@react-native-async-storage/async-storage 2.2.0` 있음, 그러나 `frontend/src`에서 import 0건(미사용).
  - SecureStore는 값 크기 제한(약 2KB)이 있어 테마·안내 본 상태 같은 일반 값은 AsyncStorage가 맞다 → 결정 필요 표에 올림.

### 묶음 1: 로그인 · 온보딩 · 첫 시작

#### 표 A 데이터

| 화면 | mock 출처(파일·상수/함수) | 필드 | 백엔드(파일·스키마.필드) | 판정 | 메모 |
|---|---|---|---|---|---|
| 인트로 | fe/ui/screens/auth/Auth.mock.ts `mockIntroPages` | key · title · description | — | 그대로 | 고정 문구. 서버 불필요 |
| 약관 | Auth.mock.ts `mockTerms` | key · label · required · document | — | 그대로 | 항목 목록은 고정 문구 |
| 약관 | Auth.mock.ts `legalDocument` (AuthLegal.ts `LEGAL`) | title · html | — | 그대로 | 고정 문서. 버전 관리 필요하면 표 C |
| 약관 | Auth.mock.ts `emptyTermChecks` / `checkedTerms` | age · service · invest (동의 여부) | — (be 전체에 terms·consent·agree 없음, alembic 도 없음) | 없음 | 표 C-1 |
| 로그인 | fe/app/login.tsx `params.recent` | recent_provider (최근 로그인 수단) | be/auth/routes.py `TokenResponse.user.providers[].current` (be/auth/service.py `_public_user`) | 확인 필요 | 지금은 URL 값만. 기기 저장(프론트)으로 충분한지 결정 필요 |
| 로그인·공통 | fe/store/auth.ts `User` (fe/types/models.ts `User`) | id · name · bio · avatar_url · email · providers | be/auth/service.py `_public_user` → id · name · bio · avatar_url · email · providers | 그대로 | |
| 로그인·공통 | fe/types/models.ts `AuthToken` | access_token · refresh_token · token_type · expires_in · user | be/auth/routes.py `TokenResponse` | 그대로 | |
| 종목 고르기 | fe/ui/screens/onboarding/Onboarding.mock.ts `mockOnboardingStocks`(웹) · `mockAppPopularStocks`(앱) | stock_code | be/stocks/schemas.py `StockMasterResponse.code` | 이름만 다름(→code) | |
| 종목 고르기 | 〃 | name · market | `StockMasterResponse.name` · `.market` | 그대로 | 스키마 market 은 KONEX 포함, DB `0001sql market_type` 은 KOSPI·KOSDAQ 만 → 실제로 KONEX 는 안 옴(0단계 수정) |
| 종목 고르기 | 〃 | category (반도체·금융 …) | — (`StockMasterResponse` 에 없음. DB `0001sql stocks.sector` 는 `sector_type`=general·financial 두 값뿐이라 업종이 아님) | 없음 | 0단계 수정(전: 확인 필요 · 0012 는 은행·보험 재무 칸이라 업종과 무관). 표 C-6 |
| 종목 고르기 | 〃 | logo · logo_bg · logo_ink | — | 계산 필요(프론트) | 이름 첫 글자 + 색 규칙. 회사별 색이면 표 C |
| 종목 고르기 | `mockAppPopularStocks` (12개, 원본 login.html 순서) | '많이 찾는 종목' 목록·순위 | — (popular·search_count 없음) | 없음 | 표 C-2. 웹은 `mockOnboardingStocks` 18개로 출처가 다름 |
| 종목 고르기 | fe/app/onboarding/pick.tsx `selected` | {code: holding\|watching} | be/stocks/schemas.py `StockCreateRequest.code` · `.status` | 이름만 다름(→code) | 지금은 URL query 로만 넘김, 서버 저장 없음 |
| 종목 고르기(홈 방식) | pick.tsx `onChooseHome(mode)` | home_mode: template\|custom | be/account/schemas.py `HomeLayout.mode` (unset\|template\|custom) | 그대로 | `unset` 은 신규 판별 보조 신호로도 쓸 수 있음 |
| 첫 홈(앱) | fe/ui/screens/home/Home.mock.ts `mockHomeData.user_name` | user_name | be/auth/service.py `_public_user.name` | 이름만 다름(→name) | |
| 첫 홈(앱) | Onboarding.mock.ts `mockFirstHomeStocks` | stock_code · name · status | be/stocks/schemas.py `MyStockResponse.code` · `.name` · `.status` | 이름만 다름(stock_code→code) | 쿼리 문자열 → `GET /stocks` 로 교체 |
| 첫 홈(앱) | `mockFirstHomeStocks` | memo_count | — (`MyStockResponse` 에 없음) | 계산 필요(프론트 또는 백엔드) | 프론트면 종목마다 `GET /stocks/{code}/board` 길이. 백엔드 집계 칸이면 표 C-4, 담당자 상의 |
| 첫 홈(앱) | `mockFirstHomeStocks` | ai_count | be/board/schemas.py `MemoResponse.ai_linked` | 계산 필요(프론트 또는 백엔드) | board 목록에서 ai_linked=true 수. memo_count 와 같은 결정 |
| 첫 홈(앱) | Onboarding.mock.ts `mockFirstHomeNameOverride` | NAVER→'네이버' 표시 이름 | `StockMasterResponse.name` | 확인 필요 | 종목 마스터 이름을 그대로 쓸지 결정 |
| 첫 홈(웹) | fe/app/(main)/index.tsx `firstStocks` (`mockOnboardingStocks` 필터, 없으면 앞 3개) | 종목 목록 | be/stocks/routes.py `GET /stocks` `MyStockResponse` | 이름만 다름(stock_code→code) | '없으면 앞 3개' 대체 규칙은 연결 시 삭제 |
| 첫 메모 요약(앱) | fe/app/(main)/index.native.tsx `firstMemo` (URL first_code·first_title·first_body·first_ai) | stock_code · title · body · ai | be/board/schemas.py `MemoResponse.stock_code` · `.title` · `.body` · `.ai_linked` | 이름만 다름(ai→ai_linked) | 지금 URL 로만 전달. 저장 응답 `id` 로 다시 읽게 바꿀 것 |
| 첫 메모 요약(앱) | index.native.tsx `chips` ← fe/ui/screens/memo/MemoDetail.mock.ts `mockExtract` | chips (가격 조건·공시뉴스 키워드) | be/board/schemas.py `MemoResponse.analysis` (dict) · `.price_conditions` | 확인 필요 | analysis 안 구조가 스키마에 정의 안 됨(dict). be/board/analysis.py 확인 필요 |
| 첫 메모 요약(앱) | index.native.tsx `firstMemo.stock_name` | stock_name | `MyStockResponse.name` | 계산 필요(프론트) | 내 종목 목록에서 code 로 찾기 |

#### 표 B 동작

| 화면 | 동작 | 프론트 위치(파일·함수) | 엔드포인트(METHOD 경로·파일) | 판정 | 메모 |
|---|---|---|---|---|---|
| 로그인 | 소셜 로그인 시작 (kakao·naver·google) | fe/app/login.tsx `social` → fe/lib/oauth.ts `startSocialLogin` | GET /auth/{provider}/start · be/auth/routes.py | 그대로 | be/auth/providers.py 에 google·kakao·naver. apple 없음 |
| 로그인 | 소셜 콜백(웹) | fe/app/auth/callback.tsx → store/auth.ts `completeWebLogin` | GET /auth/{provider}/callback → GET /auth/me · be/auth/routes.py | 그대로 | |
| 로그인 | 앱 code 교환 | fe/lib/oauth.ts → fe/api/real.ts `exchangeMobileAuth` → store/auth.ts `acceptSession` | POST /auth/mobile/exchange · be/auth/routes.py `mobile_exchange` | 그대로 | |
| 로그인 | mock 로그인 | store/auth.ts `mockSignIn` (`env.useMockAuth`) | — | 그대로 | 연결 후 개발용으로만 유지 |
| 자동 로그인 | 앱 시작 시 세션 복구 | store/auth.ts `bootstrap` → `refresh` | POST /auth/refresh · be/auth/routes.py `refresh` | 그대로 | 앱: SecureStore refresh_token, 웹: 쿠키 |
| 자동 로그인 | 401 시 토큰 갱신 | fe/api/http.ts `setRefreshHandler` | POST /auth/refresh | 그대로 | |
| 로그아웃(약관 '취소') | 약관 화면에서 나가기 | fe/app/terms.tsx → store/auth.ts `signOut` | POST /auth/logout · be/auth/routes.py `logout` | 그대로 | |
| 로그인 후 | 신규 사용자 판별 → 약관·온보딩 / 기존 → 홈 | fe/app/login.tsx `continueToTerms` (로그인하면 항상 /terms) | GET /stocks · be/stocks/routes.py `list_my_stocks` | 계산 필요(프론트) | 지금은 판별 없음. 내 종목 0개 → /terms, 1개 이상 → /. 자동 로그인(bootstrap) 경로에도 같은 판별 필요 |
| 약관 | 동의 저장 | fe/app/terms.tsx `onContinue` (화면 이동만) | — | 없음 | 표 C-1. 동의 안 하고 앱 재시작 시 다시 약관을 띄울 근거 없음 |
| 종목 고르기 | 종목 검색 | fe/app/onboarding/pick.tsx `onQueryChange` (mock 목록 필터) | GET /stocks/search?q= · be/stocks/routes.py `search_stocks` | 그대로 | 계약상 최대 8개. (묶음 2 확인) be/stocks/repository.py `search_kospi`·`get_kospi` 가 `market = 'KOSPI'` 만 → KOSDAQ 종목은 검색·추가 불가. 담당자 상의 |
| 종목 고르기 | '많이 찾는 종목' 불러오기 | pick.tsx `stocks` (`mockAppPopularStocks`/`mockOnboardingStocks`) | — | 없음 | 표 C-2 |
| 종목 고르기 | 선택 종목 저장(보유·관심) | pick.tsx `finish` (URL `selected` 로만 넘김) | POST /stocks (종목마다 1번) · be/stocks/routes.py · `StockCreateRequest` | 그대로 | 여러 개 한 번에 저장하는 API 없음 → 표 C-3(선택) |
| 종목 고르기 | 홈 방식 선택(템플릿·직접) | pick.tsx `onChooseHome` | PUT /home/layout · be/account/routes.py · `HomeLayout` | 그대로 | template 선택 시 기본 widgets 는 be/account/defaults.py 확인 필요 |
| 종목 고르기 | '건너뛰기' | pick.tsx `onSkip` | — | 그대로 | 종목 0개면 다음 로그인 때 다시 온보딩 → 의도인지 결정 필요 |
| 첫 홈 | 종목 골라 첫 메모 쓰기 | fe/app/(main)/index.native.tsx → `/memo/new?from_onboarding=1` | — | 그대로 | 화면 이동만 |
| 첫 메모 | 저장 | fe/app/(detail)/memo/new.tsx `onSave` (URL 로 홈 복귀) | POST /stocks/{code}/memos · be/board/routes.py · `MemoCreate`(title·body·ai_linked) | 이름만 다름(ai→ai_linked) | 지금 서버 저장 없음. AI 켜기는 create 의 ai_linked=true 로 한 번에 가능 |
| 첫 메모 | AI 연결 켜기·끄기 | fe/app/(detail)/memo/link.tsx | PUT /memos/{id}/ai-link · be/board/routes.py · `AiLinkPatch.enabled` | 그대로 | 응답 `analysis` 로 요약 칩 채움 |
| 첫 홈 | 메모 수·AI 연결 수 표시 | Onboarding.mock.ts `mockFirstHomeStocks` | GET /stocks + GET /stocks/{code}/board · be/stocks · be/board | 계산 필요(프론트) | 종목 수만큼 호출. 많아지면 표 C-4 |
| 첫 홈(웹) | 가이드·코치 시작 | fe/app/(main)/index.tsx `startCoach` (store/coach.ts) | — | 확인 필요 | 가이드 본 여부를 서버에 남길지 결정 필요(지금은 URL `onboarding` 값) |

#### 표 C 새로 만들 것

| 항목 | 종류(엔드포인트·DB칸·표·프론트) | DB 변경(Y/N) | 메모 |
|---|---|---|---|
| C-1 약관 동의 저장 | DB칸(users.terms_agreed_at · terms_version 등) 또는 표(user_consents) + 엔드포인트(POST /me/consents, `/auth/me` 응답에 동의 여부) | Y | 담당자 상의 (be/auth · be/account) |
| C-2 '많이 찾는 종목' | 엔드포인트(GET /stocks/popular) + 집계 출처(조회 로그 또는 고정 목록) | 확인 필요(고정 목록이면 N) | 담당자 상의. 출처 결정 전까지 프론트 고정 목록 유지 |
| C-3 온보딩 종목 한 번에 저장 | 엔드포인트(POST /stocks/bulk) | N | 선택. 없으면 POST /stocks 반복 |
| C-4 종목별 메모 수·AI 연결 수 | `MyStockResponse` 칸 추가(memo_count · ai_linked_count) | N (집계) | 선택. 담당자 상의 (be/stocks) |
| C-5 신규 사용자 판별 함수 | 프론트(store/auth.ts 또는 login 후 공통 함수: GET /stocks 길이 0 → /terms) | N | 약관 동의(C-1) 생기면 '동의 안 함 → /terms'를 먼저 본다 |
| C-6 종목 업종·로고 | 프론트(로고 규칙) + DB칸 `stocks.industry`(가칭) + `StockMasterResponse.category` | Y (업종을 보여 줄 경우) | 0단계 수정: `stocks.sector` 는 general·financial 뿐이라 재사용 불가. 업종 출처(KRX 업종 분류 등) 담당자 상의. 시연은 프론트 고정값으로 가능 |

### 묶음 2: 보드 · 메모 · AI 연결 · 근거

공통 사실 (아래 표의 근거):
- 화면은 아직 `api.*`를 쓰지 않는다. 보드·메모 화면은 `*.mock.ts`를 직접 import. 연결용 코드 `fe/api/board.ts` `createRealBoardApi`·`fe/hooks/queries.ts` (`useBoard`·`useCreateBoardItem`·`useSetAiLink`·`useMemoTimeline` …)는 있지만 화면에서 import 0건(`hooks/queries`를 쓰는 곳은 features/home/widgets/MarketWidgets.tsx · features/settings/SettingsModal.tsx 두 곳뿐).
- `fe/api/types.ts` `Api`에는 보드 순서(board-order)·종목 순서(stocks/order)·확인 질문(confirmations)·질문 답(answers) 함수가 없다 → 표 C-7.
- DB: `0001sql memos`(kind=note·checklist·reference, title, content, color, is_pinned, ai_linked, ai_linked_at, deleted_at) + `0019 memos.position` · `0001sql memo_revisions`(+`0005 revision_no`, 저장 때 트리거 `capture_memo_revision`이 자동 생성) · `0001sql checklist_items`(label, is_done, sort_order) · `0001sql memo_links`(+`0004 link_type`·`is_file`) · `0001sql tracking_items`(+`0019 topic`·`target_symbol`) · `0001sql tracking_updates`(+`0004 memo_revision_id`·`price_state`·`details`, `0005 observed_trade_date`) · `0001sql update_sources`(news_id · disclosure_rcept_no · quote) · `0001sql user_stocks` + `0021 position`.
- 0004 제약 `ck_memos_ai_only_note`: AI 연결은 일반 메모(note)만.

#### 표 A 데이터

| 화면 | mock 출처(파일·상수/함수) | 필드 | 백엔드(파일·스키마.필드) | 판정 | 메모 |
|---|---|---|---|---|---|
| 보드 | fe/ui/screens/board/MemoBoard.mock.ts `mockBoardMemos` (fe/types/models.ts `Memo`) | id · kind · stock_code · title · position · created_at · updated_at | be/board/schemas.py `BoardBase` · `MemoResponse.kind`(="memo") | 그대로 | DB kind `note` → 응답 `memo` 변환은 be/board/service.py `_response` |
| 보드 | 〃 | body · tags · color · pinned · ai_linked · ai_linked_at | `MemoResponse.body` · `.tags` · `.color` · `.pinned` · `.ai_linked` · `.ai_linked_at` | 그대로 | DB 는 content · is_pinned · memo_tags. 화면은 tags 미사용 |
| 보드 | 〃 | price_conditions[] (id · direction · price · tracking · status · reached_at) | `MemoResponse.price_conditions` ← be/board/tracking.py `price_conditions` | 그대로 | 스키마는 `list`(형 없음)지만 tracking.py 가 같은 6개 키로 채움 |
| 보드 | 〃 | unread_updates | `MemoResponse.unread_updates` ← tracking.py `unread_updates` | 그대로 | |
| 보드 | — | analysis | `MemoResponse.analysis` (생성·수정·ai-link·confirmations 응답에만) | 그대로 | fe `Memo` 타입·`normalizeBoardItem` 에 analysis 없음 → 버려짐. 표 C-8 |
| 보드 | MemoBoard.mock.ts `mockBoardChecklist` | id · kind · title · position · created_at · updated_at · items[id·text·done] · pinned | be/board/schemas.py `ChecklistResponse` · `ChecklistItemResponse` | 그대로 | DB checklist_items.label·is_done → text·done 변환(be/board/repository.py) |
| 보드 | MemoBoard.types.ts `checklist: Checklist \| null` (종목마다 하나) | 체크리스트 개수 | `GET /stocks/{code}/board` 는 체크리스트 여러 개 가능 | 확인 필요 | 화면은 1개만 그림. 2개 이상일 때 규칙 결정 필요 |
| 보드(웹) | MemoBoard.mock.ts `mockBoardOrder` (`'cl'` + 메모 id) | 카드 순서 | `BoardBase.position` · `BoardOrderPut.ids`(int) | 이름만 다름(→position · ids) | 웹 순서 키 `'cl'` → 체크리스트 실제 id 로 바꿔야 함 |
| 보드(웹) | fe/app/(main)/stocks/[code].tsx `customized` | orderCustomized ('꾹 눌러 끌면' 안내 여부) | — | 없음 | 서버 칸 없음. 기기 저장으로 충분 → 결정 필요(기기 저장 범위) |
| 보드 | MemoBoard.types.ts `aiSpent` | AI 사용량 소진 | be/credits `GET /me/usage` `paused` | 이름만 다름(→paused) | 묶음 4 에서 자세히 |
| 보드 | MemoBoard.types.ts `BoardFilter` all·ai·new | 거르기 | `MemoResponse.ai_linked` · `.unread_updates` | 계산 필요(프론트) | |
| 메모 상세 | fe/ui/screens/memo/MemoDetail.mock.ts `mockVersions` (`MemoVersion`) | version · title · body · saved_at | be/updates/service.py `memo_timeline` entries[kind=memo_created·memo_edit].version (`revision_no`·title·content·created_at) | 계산 필요(프론트) | 수정 이력 전용 API 없음. 타임라인에서 뽑아 최신순 정렬 |
| 메모 상세 | MemoDetail.mock.ts `mockFeed` (`MemoFeedItem`) | id · headline · summary · url · memo_version | timeline entries[kind=update].update (be/updates/service.py `_ai_update`) `.id` · `.headline` · `.summary` · `.url` · `.memo_version` | 그대로 | |
| 메모 상세 | 〃 | kind 뉴스·공시·주가 | `_ai_update.type` news·disclosure·price | 이름만 다름(→type) | 값 바꾸기 표 필요. 질문 답(answer)은 news·disclosure 로 바뀌어 옴(`card_type` 에 원래 값) |
| 메모 상세 | 〃 | at (소식 날짜) | `_ai_update.published_at` (가격 카드는 observed_trade_date) | 이름만 다름(→published_at) | |
| 메모 상세 | 〃 | unread | `_ai_update.read` | 이름만 다름(→!read) | |
| 메모 상세 | 〃 | source ('한국경제 · 2026. 10. 15. 08:40') | `_ai_update.source` + `.published_at` | 계산 필요(프론트) | 가격 카드 source 는 "KRX"(mock 은 'KIS') |
| 메모 상세 | 〃 | article_title (뉴스) · report (공시 보고서 이름) | `_ai_update.title` (대표 근거 제목) · `sources[].title` | 이름만 다름(→title) | |
| 메모 상세 | 〃 | quote (공시 원문 일부) | `_ai_update.sources[].quote` ← DB update_sources.quote | 이름만 다름(→sources[].quote) | |
| 메모 상세 | 〃 | quote_mark (밑줄 칠 부분) | — | 없음 | quote 안 밑줄 위치 칸 없음. 화면에서 밑줄 없이 보이기 or `card`(details) 키 확인 → 담당자 상의 |
| 메모 상세 | 〃 | provider ('한국경제 · 네이버 뉴스') | `sources[].source` (매체명만, news_sources.name) | 확인 필요 | '네이버 뉴스' 같은 제공 경로 칸 없음 |
| 메모 상세 | 〃 | price.close | `_ai_update.price.observed_value` | 이름만 다름(→price.observed_value) | |
| 메모 상세 | 〃 | price.cond · price.direction | `MemoResponse.price_conditions[id = update.item.id].price` · `.direction` | 계산 필요(프론트) | `_ai_update.item` 에 price_threshold 없음 → 메모의 price_conditions 와 item.id 로 맞춤 |
| 메모 상세 | 〃 | price.gap ('+6,800원 (+4.5%)') · '조건까지 ±N%' | — (close·cond 로 계산) | 계산 필요(프론트) | fe/ui/screens/memo/EvidenceContent.tsx `toCond` 가 gap 문자열에서 % 를 뽑음 → 숫자로 받게 바꾸는 편이 안전 |
| 메모 상세 | 〃 | price.tone near·reached | `_ai_update.price.state` (DB 0004 `price_state` near·away·reached) | 확인 필요 | 팀 11.09 결정은 2가지. 백엔드 away 가 아직 오는지 담당자 상의 |
| 메모 상세 | 〃 | price.closes · from · to (근거 차트) | — (카드에 없음) | 계산 필요(프론트) | `GET /stocks/{code}/candles` 로 그려야 하나 range(1W·1M…) 만 받고 '이 날짜까지'는 못 받음 → 확인 필요. 표 C-9 |
| 메모 상세 | 〃 | 'MM.DD 종가 기준' (EvidenceContent.tsx `mmdd(f.at)`) | `_ai_update.price.observed_trade_date` | 계산 필요(프론트) | |
| 메모 상세 | MemoDetail.mock.ts `mockTrackItems` (`AiTrackItem`) | kind price·fact · label | timeline `.tracking_items[]` type·description (be/updates/service.py) / `analysis.items[]` (be/board/service.py `_item_out` id·type·description·price_threshold·status) | 이름만 다름(type→kind, description→label) | type: price_below·price_above→price, topic→fact. **ask(질문)** 도 섞여 옴 → 걸러야 함 |
| 메모 상세 | 〃 | price · direction 이하·미만·이상 | `analysis.items[].price_threshold` · type price_below·price_above | 이름만 다름(→price_threshold) | 화면 문구 '미만·이하' 중 무엇인지 기준 없음(백엔드는 below·above 뿐) |
| 메모 상세 | 〃 | quote (메모에서 찾은 문장) | — (`_item_out`·timeline 에 문장 없음) | 없음 | analysis.py 내부 `sentence_index` 는 응답에서 빠짐. 담당자 상의 |
| 메모 상세 | MemoDetail.mock.ts `mockLastChecked` ('11.18 장 마감 후') | lastChecked | timeline `.tracking_items[].last_checked_at` | 계산 필요(프론트) | 가장 늦은 값 → 문장 |
| 메모 상세 | MemoDetail.mock.ts `mockDetailStockName` | stockName | be/stocks `MyStockResponse.name` | 이름만 다름(→name) | 내 종목 목록에서 code 로 |
| 메모 상세 | MemoDetail.mock.ts `mockToday` | 저장 시각 | `MemoResponse.updated_at` | 이름만 다름(→updated_at) | |
| AI 연결 창 | MemoDetail.mock.ts `mockExtract` | 새 메모 추적 항목 미리보기 | `analysis.items` (POST /stocks/{code}/memos 응답, ai_linked=true 일 때) | 이름만 다름(→analysis.items) | 미리보기만 하는 API 없음 → 흐름 차이(표 B 참고) |
| AI 연결 창 | MemoDetail.types.ts `AiLinkState` loading·items·empty·error | 상태 | `analysis.status` done·failed·skipped·unchanged·confirmed + `items` 길이 · `out_of_scope` | 계산 필요(프론트) | failed 의 `error`(llm_unavailable 등) 문구 매핑 필요 |
| AI 연결 창 | — | 확인 질문 | `analysis.confirmations[]` (question · options[].option_id) | 없음(프론트) | 화면에 확인 질문 UI 가 없다. 표 C-10 |
| AI 끄기 시트 | fe/app/(main)/stocks/[code].native.tsx `AiOffSheet itemCount={2}` | 추적 항목 수 | timeline `.tracking_items` 길이 | 계산 필요(프론트) | 지금 2 로 고정 |
| 근거 상세 | fe/ui/screens/updates/Updates.mock.ts `feedOf`·`findMemo`·`versionsOf` | 소식 · 메모 · 버전 | timeline (위와 같음) · `GET /board-items/{id}` | 계산 필요(프론트) | Updates.mock 은 묶음 3 에서 다시 봄 |
| 근거 상세 | Updates.mock.ts `versionsOf` + `item.memo_version` | 소식이 붙을 때의 메모 | timeline entries[kind=update].memo_snapshot (version·title·body·saved_at) | 그대로 | be/updates/service.py `memo_timeline` |
| 내 종목 | fe/ui/screens/stocks/MyStocks.mock.ts `mockMyStocks` (MyStocks.types.ts `MyStock`) | stock_code · name · market · status | be/stocks/schemas.py `MyStockResponse.code` · `.name` · `.market` · `.status` | 이름만 다름(stock_code→code) | |
| 내 종목 | 〃 | new_count | `MyStockResponse.unread_updates` | 이름만 다름(→unread_updates) | be/stocks/repository.py `list_user_stocks` 가 AI 켠 메모의 읽지 않은 카드만 셈 |
| 내 종목 | 〃 | memo_count · ai_count | — | 계산 필요(프론트 또는 백엔드) | 묶음 1 C-4 와 같음 |
| 내 종목 | 〃 | price · change_pct · as_of | 묶음 3 `GET /stocks/{code}/quote` | 계산 필요(프론트) | 종목 수만큼 호출 |
| 내 종목 | 〃 | logo · logo_bg · logo_ink | — | 계산 필요(프론트) | 묶음 1 C-6 |
| 내 종목 | 〃 | ai_ready (시범 종목) | — | 없음 | '시범 종목' 기준 칸 없음. 결정 필요 |
| 내 종목 | 〃 | 순서 | `MyStockResponse.position` (0021) · 목록이 position 순 | 그대로 | |
| 내 종목 | MyStocks.mock.ts `mockUniverse` (`StockCandidate`) | 검색 후보 · sector · price | `GET /stocks/search` `StockMasterResponse` (code·name·market) | 이름만 다름(stock_code→code) | sector 없음(C-6), price 는 quote. KOSPI 만 |
| 내 종목 | MyStocks.mock.ts `mockMyStocksData.popular` | 많이 찾는 종목 | — | 없음 | 묶음 1 C-2 와 같음 |
| 사이드바(웹) | fe/ui/layout/web/WebShell.mock.ts `mockSideStocks` (`SideStock`) | stock_code · name · status · logo | `GET /stocks` `MyStockResponse` | 이름만 다름(stock_code→code) | logo 는 C-6 |
| 사이드바(웹) | WebShell.mock.ts `mockPopular` · `mockRecentSearches` | 검색 창 많이 찾는 · 최근 검색 | — | 없음 | 많이 찾는 = C-2, 최근 검색 = 기기 저장(결정 필요) |

#### 표 B 동작

| 화면 | 동작 | 프론트 위치(파일·함수) | 엔드포인트(METHOD 경로·파일) | 판정 | 메모 |
|---|---|---|---|---|---|
| 보드 | 보드 불러오기 | fe/app/(main)/stocks/[code].tsx `BoardTab` · [code].native.tsx (mock state) | GET /stocks/{code}/board · be/board/routes.py | 그대로 | `fe/api/board.ts listBoard`·`hooks/queries.ts useBoard` 있음, 화면 미연결 |
| 보드 | 새 메모 저장 | [code].tsx `WebNewMemoDialog.onSave` · fe/app/(detail)/memo/new.tsx `onSave` | POST /stocks/{code}/memos · `MemoCreate`(title·body·tags·color·ai_linked·pinned) | 그대로 | 앱 new.tsx 는 color 를 안 넘김(기본 yellow) |
| 보드 | 메모 수정 저장 | fe/app/(detail)/memo/[id].tsx `onSave` · [code].tsx `WebMemoDialog.onSave` | PATCH /board-items/{id} · `BoardItemPatch` | 그대로 | 제목·본문이 바뀌면 다시 분석(응답 analysis). 버전은 DB 트리거가 만듦 |
| 보드 | 색 바꾸기 | `onChangeColor` (보드 여러 개 · 상세 하나) | PATCH /board-items/{id} `color` | 그대로 | 여러 개면 N번 호출 |
| 보드 | 고정(테이프) · 풀기 | `onPin(ids)` · 상세 `onTogglePin` | PATCH /board-items/{id} `pinned` | 그대로 | 서버가 순서도 바꿈(고정하면 맨 앞, be/board/service.py `_place`) → 응답 뒤 목록 다시 읽기 |
| 보드 | 체크리스트 고정 | `onTogglePin` · fe/app/(detail)/checklist/[id].tsx `onTogglePin` | PATCH /board-items/{id} `pinned` | 그대로 | 2026-11-20 체크리스트도 허용 |
| 보드 | 삭제 | `onDelete(ids)` · 상세 `onDelete` | DELETE /board-items/{id} · be/board/routes.py | 그대로 | 소프트 삭제(memos.deleted_at) → 휴지통. 여러 개면 N번 |
| 보드 | 삭제 되돌리기 | `onUndoDelete(ids)` | POST /trash/memo-{id}/restore · be/trash/routes.py | 계산 필요(프론트) | 휴지통 id = `memo-{메모 id}` (be/trash/service.py `parse_id`) |
| 보드 | 복사 | `onCopy` (지금 빈 함수) | — | 없음 | 복사 API 없음. 프론트에서 POST memos 로 같은 내용 새로 만들기 가능(AI 연결 여부 결정 필요) |
| 보드 | 끌어서 순서 바꾸기(웹) | [code].tsx `onReorder` → `setOrder` | PUT /stocks/{code}/board-order · `BoardOrderPut.ids` | 그대로 | `Api` 에 함수 없음(C-7). 앱은 `onReorder={() => {}}` |
| 보드 | 카드 하나 옮기기 | — | PATCH /board-items/{id} `position` | 그대로 | 앱 끌기에 쓸 수 있음 |
| 체크리스트 | 새로 만들기 | checklist/[id].tsx (id='new') `onDone` (지금 안내만) | POST /stocks/{code}/checklists · `ChecklistCreate`(title·items) | 그대로 | |
| 체크리스트 | 항목 체크 | 보드 `onToggleChecklistItem` · checklist/[id].tsx `onToggleItem` | PATCH /checklists/{id}/items/{item_id} · `ChecklistItemPatch`(text·done) | 그대로 | `fe/api/board.ts setBoardChecklistItem` 있음 |
| 체크리스트 | 이름 · 항목 추가 · 항목 삭제 | checklist/[id].tsx `onChangeTitle` · `onAddItem` · `onDeleteItem` | PATCH /board-items/{id} `title` · `items`(전체 교체) | 그대로 | 항목 추가·삭제는 items 배열 전체를 보냄. 새 항목은 id 없이 |
| 참고자료 | 만들기 · 수정 | — (화면 없음, fe/ui 에 reference 0건) | POST /stocks/{code}/references · PATCH /board-items/{id} `links` | 그대로 | 프론트 화면 없음 → 프론트 미사용 |
| 메모 상세 | 상세 열기 | memo/[id].tsx `findMemo(id)` | GET /board-items/{id} | 그대로 | |
| 메모 상세 | AI 업데이트 탭(타임라인) | memo/[id].tsx `feedOf` | GET /memos/{id}/timeline · be/updates/routes.py | 그대로 | `fe/api/real.ts getMemoTimeline` 있음 |
| 메모 상세 | 소식 읽음 | memo/[id].tsx `onSeenUpdates` (4초 뒤 mock) | POST /ai-updates/{id}/read · be/updates/routes.py | 그대로 | 읽지 않은 카드마다 1번(일괄 읽음 API 없음) |
| 메모 상세 | 수정 이력 | fe/app/(detail)/memo/history.tsx `versionsOf` | GET /memos/{id}/timeline (memo_created·memo_edit) | 계산 필요(프론트) | |
| 메모 상세 | 원문 열기 | `onOpenSource` (지금 안내만) | — (url 은 카드에 있음: 뉴스 news_articles.url · 공시 `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=`) | 그대로 | 앱 안 브라우저는 `expo-web-browser`(package.json 있음) |
| 근거 상세 | 근거 열기 | fe/app/(detail)/memo/evidence.tsx | GET /memos/{id}/timeline 에서 소식 id 로 찾기 | 계산 필요(프론트) | 소식 한 건 조회 API 없음 |
| AI 연결 | 기존 메모 AI 켜기 | memo/link.tsx (mock 1.2초 → 항목 보여 주고 '확인') | PUT /memos/{id}/ai-link `{enabled:true}` · `AiLinkPatch` | 확인 필요 | 흐름 차이: 화면은 '분석 → 항목 보고 확인 → 켜기', 백엔드는 PUT 한 번에 켜기+분석. 화면 '일반 메모로 두기' 를 누르면 PUT false 로 되돌려야 함 → 결정 필요 |
| AI 연결 | 새 메모 AI 켜고 저장 | memo/new.tsx → memo/link.tsx(id='new') · [code].tsx `startConnect` | POST /stocks/{code}/memos `ai_linked:true` (응답 analysis) | 확인 필요 | 위와 같은 흐름 차이. 지금 link 화면은 id='new' 로 메모 id 없이 열림 → 저장 응답 id 를 넘겨야 함 |
| AI 연결 | AI 끄기 | [code].native.tsx `AiOffSheet.onConfirm` · memo/[id].tsx `onDisconnectAi` | PUT /memos/{id}/ai-link `{enabled:false}` | 그대로 | 항목은 지우지 않고 paused (be/board/service.py `set_ai_link`) |
| AI 연결 | 분석 실패 다시 시도 | link.tsx `onRetry` | — | 확인 필요 | 서버 재분석은 '메모를 다시 저장할 때만'(be/board/service.py 머리말). AI 끄고 켜면 `changed_since_analysis` 가 False 라 재분석 안 될 수 있음 → 담당자 상의 |
| AI 연결 | 확인 질문 답하기 | — (UI 없음) | POST /memos/{id}/confirmations · `ConfirmationAnswer.option_id` · 409(메모 바뀜)·422 | 없음(프론트) | C-10 |
| 추적 항목 | 주제(topic) 저장 | — | DB `0019 tracking_items.topic` | 확인 필요 | backend/app 에 topic 칸을 쓰는 코드 없음(be/board/tracking.py `create_item` 에 없음). 수시공시 카드 맞추기용이라 프론트 영향 없음. 담당자 상의 |
| 내 종목 | 목록 | fe/app/(main)/stocks/index*.tsx (`mockMyStocksData`) | GET /stocks · be/stocks/routes.py `list_my_stocks` | 그대로 | `hooks/queries.ts useMyStocks` 있음 |
| 내 종목 | 추가(보유·관심) | `onAdd(code, hold)` · fe/app/(main)/_layout.tsx `WebAddStockDialog` | POST /stocks `StockCreateRequest` | 그대로 | 삭제했던 종목은 되살림(be/stocks/repository.py `upsert_user_stock`) |
| 내 종목 | 보유 ↔ 관심 옮기기 | `onMove(codes, hold)` · 사이드바 메뉴 | PATCH /stocks/{code} `StockUpdateRequest.status` | 그대로 | 여러 개면 N번 |
| 내 종목 | 빼기 | `onRemove(codes)` · 사이드바 '내 종목에서 빼기' | DELETE /stocks/{code} | 그대로 | 소프트 삭제 → 휴지통 `stock-{code}` |
| 내 종목 | 빼기·옮기기 되돌리기 | `onRestore(snapshot)` | POST /trash/stock-{code}/restore · PATCH /stocks/{code} | 계산 필요(프론트) | |
| 내 종목 | 태그 | — | PATCH /stocks/{code} `tags` | 그대로 | 백엔드는 빈 목록 말고는 422(`UnsupportedStockTagsError`). 화면도 안 씀 |
| 사이드바(웹) | 종목 순서 끌기 | fe/app/(main)/_layout.tsx `onReorderStocks` → `setSideStocks` | PUT /stocks/order · `StockOrderRequest.codes` | 그대로 | `Api` 에 함수 없음(C-7) |
| 내 종목(앱) | 묶음 안 순서 | MyStocks.types.ts `onReorder(codes)` | PUT /stocks/order | 그대로 | 보유·관심 두 묶음이어도 전체 순서 하나로 보냄 |
| 내 종목 | 추가 뒤 메모 쓰기 | `onWriteMemo` | — | 그대로 | 화면 이동만 |

#### 표 C 새로 만들 것

| 항목 | 종류(엔드포인트·DB칸·표·프론트) | DB 변경(Y/N) | 메모 |
|---|---|---|---|
| C-7 프론트 API 함수 추가 | 프론트(`fe/api/types.ts Api`·real.ts·mock): reorderBoard(PUT board-order) · reorderStocks(PUT stocks/order) · confirmMemo(POST confirmations) · listMemoAnswers(GET answers) | N | 백엔드는 있음 |
| C-8 analysis 받기 | 프론트(`Memo` 응답에 analysis 를 버리지 않게, `normalizeBoardItem`) | N | AI 연결 창·확인 질문이 이 값을 씀 |
| C-9 근거 차트 기간 | 엔드포인트(candles 에 `to=날짜` 또는 가격 카드에 종가 목록) | N | 담당자 상의. 시연은 range=1M 잘라 쓰기로 대체 가능 |
| C-10 확인 질문 화면 | 프론트(AI 연결 창에 confirmations 질문·선택지) | N | 백엔드 있음 |
| C-11 AI 연결 미리보기 흐름 | 프론트 흐름 변경(저장=켜기, '일반 메모로 두기'=끄기) 또는 엔드포인트(분석만 하는 POST /memos/analyze) | N | 결정 필요 |
| C-12 추적 문장(quote) 응답 | 엔드포인트 응답 칸(analysis.items[].sentence 등) | N | 담당자 상의 (be/board/service.py `_item_out`) |
| C-13 KOSDAQ 검색 | 백엔드 쿼리(be/stocks/repository.py `search_kospi`·`get_kospi`) | N | 담당자 상의. 시범 범위가 KOSPI 만이면 그대로 |

### 묶음 3: 기업정보 · 홈 · 업데이트

공통 사실:
- 기업정보·홈·업데이트 화면도 mock 직접 import. `hooks/queries.ts` `useQuote`·`useCandles`·`useProfile`·`useFinancials`·`useMarketOverview`·`useNews`·`useUpdates` 는 있지만 화면 미사용.
- **11/21 dev 병합 반영** (c6da2d0, PR #56·#57): 기업정보 탭만 실제 API 로 바뀜. fe/ui/screens/company/useCompanyInfo.ts `useCompanyInfo(code)` 가 `useProfile`·`useQuote`·`useFinancials`·`useCandles`(1W·1M·3M·1Y)·`useMyStocks` 를 묶어 `toCompanyData` 로 화면 props 를 만든다(mock 모드는 같은 함수의 mock 응답, fe/api/mock/financials.ts `mockFinancials`). [code].tsx·[code].native.tsx 의 기업정보 탭이 이것을 씀. 보드 탭 머리는 아직 `mockBoardStock`. 백엔드 `GET /stocks/{code}/financials` 응답은 `annual`·`stability` → `quarters`(분기 12개, 억원)·`health`·`financial`·`preparing` 으로 바뀜(be/marketdata/service.py `financials`, repository.py `financial_profile`·`quarterly_financials`). 아래 기업정보 행은 이 코드 기준으로 다시 판정했다.
- `fe/features/home/widgets/MarketWidgets.tsx`(macro 지표·`useCalendar`·`useNews` 사용)는 어느 화면에서도 import 되지 않는다(옛 화면, 미사용).
- DB: `0001sql prices_daily`(+`0004 trading_value`·`0011 volume`) · `0010 adjusted_prices_daily` · `0011 stock_fundamentals_snapshot`(per·pbr·eps·bps·w52·market_cap·listed_shares) · `0001sql financials`·`financials_fin`(+`0012` 금융 칸, `stocks.fin_type`) · `0016 financials_quarterly`·`financials_fin_quarterly` · `0017 financial_metrics` · `0001sql market_indices`·`economic_indicators`(source ECOS·FRED)·`economic_observations`·`commodity_prices_daily` · `0001sql market_events`(+`0004 user_id`·`kind` market·earnings·user) · `0001sql news_articles`·`news_stocks`.

#### 표 A 데이터

| 화면 | mock 출처(파일·상수/함수) | 필드 | 백엔드(파일·스키마.필드) | 판정 | 메모 |
|---|---|---|---|---|---|
| 종목 머리(보드·기업정보) | fe/ui/screens/board/MemoBoard.mock.ts `mockBoardStock` (fe/ui/shared/StockHead.types.ts) | stock_code · name · market · status | be/stocks `MyStockResponse.code` · `.name` · `.market` · `.status` | 이름만 다름(stock_code→code) | |
| 종목 머리 | 〃 | price · change · change_pct | be/marketdata/service.py `quote` → price · change · change_pct | 그대로 | 원시 종가(prices_daily) |
| 종목 머리 | 〃 | as_of ('MM.DD') | `quote.as_of` (ISO, 15:30 KST) | 계산 필요(프론트) | 'MM.DD 종가 기준' 표시 |
| 종목 머리 | 〃 | closes (작은 선) | `quote.spark` (최근 24개 종가) | 이름만 다름(→spark) | mock 은 10~16개 |
| 종목 머리 | 〃 | logo · logo_bg · logo_ink | — | 계산 필요(프론트) | 묶음 1 C-6. 11/21 dev 병합 반영: 기업정보 탭은 useCompanyInfo.ts `fallbackLogo`(이름 첫 글자 + 코드로 고른 색)로 이미 계산. 보드 탭은 아직 mock |
| 기업정보 | fe/ui/screens/company/CompanyInfo.mock.ts `profile()` (models.ts `StockProfile`) | code · name · market · overview · prev_close · open · high · low · volume · trading_value · per · pbr · eps · bps · market_cap · shares_outstanding · week52_low · week52_high | be/marketdata/service.py `profile` 같은 18개 키 | 그대로 | overview 없으면 '기업 개요를 준비 중이에요.' (`DEFAULT_OVERVIEW_TEXT`). market_cap·shares 는 null 가능(프론트 타입은 number). 11/21 dev 병합 반영: per·pbr·eps·bps 는 KIS 값 그대로(직전 사업연도), KIS 가 0 을 주면 null(`_kis`). 프론트 타입도 number\|null. `useProfile` 로 연결됨 |
| 기업정보 | companyData.mock.ts `quoteSK`·`quoteKB` | div_yield · foreign_pct | — | 없음 | 화면 props(`StockProfile`)에도 없음 → 화면이 안 쓰면 무시. 확인 필요. 11/21 dev 병합 반영: company/*.tsx 에서 grep 0건 → 화면이 안 씀(버려도 됨) |
| 기업정보 | CompanyInfo.mock.ts `quote_as_of` | 시세 기준 시각 | `quote.as_of` | 이름만 다름(→as_of) | 11/21 dev 병합 반영: `toCompanyData` 가 quote.as_of(없으면 1M 마지막 날)로 채움 |
| 기업정보 | CompanyInfo.mock.ts `candleSet` (companyData.mock.ts `candlesSK`·`candlesKB`) | 1W·1M·3M 일봉 | be/marketdata/service.py `candles` (`RANGE_SIZES` 5·22·64) | 그대로 | 기본 수정주가(`adjusted=true`, adjusted_prices_daily), `adjusted=false` 면 원시. 11/21 dev 병합 반영: `useCandles` 4기간 미리 받음 |
| 기업정보 | 〃 | 1Y **주봉** (CompanyInfo.types.ts 주석) | `candles` 1Y = **일봉 250개** | 계산 필요(프론트) | 11/21 dev 병합 반영: useCompanyInfo.ts `weekly()` 가 월요일 시작 주봉으로 묶음(구현됨). 백엔드 interval 추가 불필요 |
| 기업정보 | CompanyInfo.mock.ts `quarters` (CompanyInfo.types.ts `CompanyQuarter` 12개) | q · label · revenue · op · net · op_margin · net_margin · roe (억원·%) | be/marketdata/service.py `financials.quarters[]` (period_end · q · label · revenue · op · net · op_margin · net_margin · roe, 억원) | 그대로 | 11/21 dev 병합 반영(이전 판정: 없음). 분기 단독 최대 12개, 오래된→최근, 라벨은 달력 분기('26.3Q'). `period_end` 는 `toCompanyData` 가 떼어 냄. roa 는 화면 타입·용어(`TermKey`)에서 빠짐(팀 결정 ③). 자본잠식 분기 roe null. 우선주는 본주 재무(`source_code`). C-14 끝 |
| 기업정보 | CompanyInfo.mock.ts `health` (`CompanyHealth`) | debt · current · quick · interest · reserve | `financials.health.debt` · `.current` · `.quick` · `.interest` · `.reserve` | 그대로 | 11/21 dev 병합 반영(이전 판정: 이름만 다름). financial_metrics 최신 기간. 금융사는 current·quick·interest null |
| 기업정보 | CompanyInfo.mock.ts `health_as_of` ('YYYY-MM-DD') | 기준 분기 말 | `financials.health_as_of` (ISO 날짜, null 가능) · `.basis` 문장 | 그대로 | 11/21 dev 병합 반영(이전 판정: 계산 필요). null 이면 `toCompanyData` 가 마지막 분기 period_end 로 채움 |
| 기업정보 | CompanyInfo.mock.ts `financial` (금융업 여부) | true·false | `financials.financial` (+ `.sector` · `.fin_type`, DB `stocks.sector`·`fin_type`) | 그대로 | 11/21 dev 병합 반영(이전 판정: 없음). profile 이 아니라 financials 응답에 들어감. DB 변경 없음. C-15 끝 |
| 기업정보(KB금융) | finKB.quarters (revenue·op null, net 만) | 금융업 실적 | `financials.quarters` — 금융사면 revenue·op_margin·net_margin null, op·net 은 보냄 (be/marketdata/service.py `_quarter`) | 그대로 | 11/21 dev 병합 반영(이전 판정: 확인 필요). 응답 모양은 화면 '매출 —' 와 맞음. `financials_quarterly` 만 읽고 `financials_fin*`(순이자이익 등)은 여전히 안 읽음(팀 결정). mock `finKB` 는 op null, 실제는 op 값 있음 → mock 과 화면 값이 다를 수 있음. 금융사 분기 행이 DB 에 실제로 있는지는 DB 미접속이라 확인 못 함 |
| 기업정보 | CompanyInfo.types.ts `preparing` (시범 종목 밖) | 준비 중 | `financials.preparing`(분기 재무 0개, 404 대신) · 모르는 종목·시세 없음은 profile·candles 404 | 계산 필요(프론트) | 11/21 dev 병합 반영: `useCompanyInfo` 가 `!fin \|\| fin.preparing` → preparing, profile·1M candles 실패 → mock 틀 + 종목코드 + preparing (구현됨) |
| 홈 | fe/ui/screens/home/Home.mock.ts `mockHomeData.user_name` | user_name | be/auth/service.py `_public_user.name` | 이름만 다름(→name) | |
| 홈 | `mockHomeData.counts` | holding · watching | GET /stocks `MyStockResponse.status` | 계산 필요(프론트) | |
| 홈 | `mockHomeData.counts` | ai_memos | be/stats/routes.py `ai_stats.linked_memos` | 이름만 다름(→linked_memos) | |
| 홈 | `mockHomeData.updates` (`HomeUpdateRow`) | stock_code · name · status · new_count | GET /stocks `MyStockResponse` (code · name · status · unread_updates) | 이름만 다름(→code · unread_updates) | |
| 홈 | 〃 | latest {kind · title · memo_title · memo_color} | be/updates/service.py `summary` (stock_code · stock_name · new_count · memos[memo_id·title·color·updates[]]) | 계산 필요(프론트) | summary 는 읽지 않은 카드가 있는 종목만. new_count 0 인 종목의 latest(mock 삼성전자)는 GET /updates?stock_code= 로 따로 |
| 홈 | homeData.mock.ts `HOME_INDICES` (`MarketIndex`) | key kospi·kosdaq·usd | be/marketdata/service.py `INDICES` key KOSPI·KOSDAQ·USDKRW | 이름만 다름(→KOSPI·KOSDAQ·USDKRW) | |
| 홈 | 〃 | name · value · change · pct | `overview.indices[].label` · `.value` · `.change` · `.change_pct` | 이름만 다름(name→label, pct→change_pct) | sub('KOSPI 지수')는 프론트 고정 문구 |
| 홈 | 〃 | as_of (지수별 YYYY-MM-DD) | `overview.as_of` (전체 하나, 가장 늦은 날 15:30) | 계산 필요(프론트) | 지수별 기준일 없음 |
| 홈 | 〃 | closes (250개) | `overview.indices[].series['1Y']` (250) · 1D 2 · 1W 5 · 1M 22 | 이름만 다름(→series) | |
| 홈 | homeData.mock.ts `HOME_DAYS` | days (closes 날짜) | — (series 는 값만) | 없음 | 차트 날짜 축·'MM.DD 기준'에 필요 → 표 C-16 |
| 홈 · 지수 자세히 | fe/app/(detail)/market/[key].tsx (`mockHomeData.market`) | 지수 하나 | `overview.indices[]` | 이름만 다름(위와 같음) | |
| 홈(매크로) | — (화면 없음) | 기준금리·국고채 3년·미 국채 10년·금·WTI | `overview.macro[]` key · label · value · unit · change | 그대로 | 지금 화면 어디에도 매크로 지표가 없다(MarketWidgets 미사용). 프론트 미사용 |
| 홈 | homeData.mock.ts `HOME_NEWS` (`HomeNewsItem`) | id · title · url | be/marketdata/service.py `headlines` id · title · url | 그대로 | |
| 홈 | 〃 | src · at | `headlines.source` · `.published_at` | 이름만 다름(→source · published_at) | 추가 값 summary · stock_codes |
| 홈 | homeData.mock.ts `HOME_NEWS_DAY_TOTAL` | 기준일 뉴스 수 | — (headlines limit 최대 50) | 없음 | 개수 API 없음 → 결정 필요(문구 빼기 or 칸 추가) |
| 홈 | `mockHomeData.now` | 지금 ('N시간 전') | — | 계산 필요(프론트) | 기기 시각 |
| 홈 | `mockHomeData.checklists` (종목별 `Checklist`) | 체크리스트 위젯 | be/home/service.py `list_checklist` (`HomeChecklistItem` id · checklist_id · text · done · stock_code · stock_name, 평평한 목록) | 계산 필요(프론트) | 종목별로 묶기 |
| 홈 | `mockHomeData.stocks` (`HomeStock`) | stock_code · name | GET /stocks | 이름만 다름(→code) | |
| 홈 | `mockHomeData.widgets` · Home.mock.ts `mockHomeDefaultWidgets` (`HomeWidget` market·updates·news·check) | 켠 위젯·순서 | be/account/schemas.py `HomeLayout.widgets[]` (`WidgetInstance` id·type·span, type 13가지) | 이름만 다름(check→checklist) | 프론트 위젯 4종 ⊂ 백엔드 13종. span 값을 프론트가 안 씀 → 고정값 |
| 홈(웹 맞춤) | Home.mock.ts `mockCustomBoard` (`CustomItem` id·x·y·w·h) | 맞춤 홈 배치(24px 격자) | `WidgetInstance` 는 span 만(좌표 없음) · `CustomWidget` 'schedule' 은 백엔드 'calendar' | 없음 | x·y·w·h 저장 칸 없음 → 표 C-17. DB `0001sql user_settings.home_layout`(jsonb)이라 모양만 바꾸면 DB 변경 없음 |
| 홈(웹 맞춤) | Home.mock.ts `mockHomeSchedule` (homeData.mock.ts `HOME_SCHEDULE`) | 증시 일정 | — (`/calendar` 라우트 없음, fe/api/index.ts `MOCK_ONLY`) | 없음 | DB `market_events`(+0004 user_id·kind) 는 있음 → 엔드포인트만. 표 C-18 |
| 홈(앱 검색) | Home.mock.ts `mockHomeSearch` recent · popular · all | 최근 · 많이 찾는 · 전체 | all ← GET /stocks/search · popular ← 없음(C-2) · recent ← 없음 | 확인 필요 | recent 는 기기 저장(결정 필요) |
| 홈 | 앱 머리 '알림'(종) · fe/ui/layout/web/WebShell.mock.ts `mockUnreadNotifs` | 종 숫자 | — | 없음 | 알림함 API 없음(묶음 6). 시연은 `MyStockResponse.unread_updates` 합으로 대신할지 결정 필요 |
| 업데이트 | fe/ui/screens/updates/Updates.mock.ts `mockUpdateItems` (`UpdateItem` = MemoFeedItem + 4칸) | MemoFeedItem 칸 | GET /updates → be/updates/service.py `market_updates` (= `_ai_update` 모양) | 이름만 다름 | 칸별 판정은 묶음 2 메모 상세 `mockFeed` 줄과 같음 |
| 업데이트 | 〃 | stock_code · memo_id · memo_title | `_ai_update.stock_code` · `.memo_id` · `.memo_title` | 그대로 | |
| 업데이트 | 〃 | memo_color | — (`_ai_update` 에 없음, CARD_SQL 은 m.color 를 읽지만 응답에 안 넣음) | 없음 | 담당자 상의(be/updates/service.py `_ai_update` 에 color 한 줄) |
| 업데이트 | Updates.mock.ts `mockUpdateStocks` (`UpdateStock`) | stock_code · name · market · status | GET /stocks | 이름만 다름(→code) | 내 종목 순서(position) |
| 업데이트 | 〃 | ai_ready | — | 없음 | 묶음 2 와 같음 |
| 업데이트 | Updates.mock.ts `mockUpdatesNow` | now | — | 계산 필요(프론트) | |
| 업데이트 | Updates.mock.ts `mockOtherMemos`·`mockOtherVersions`·`mockOtherFeed`·`findMemo`·`feedOf`·`versionsOf` | 다른 종목 메모·소식 | GET /board-items/{id} · GET /memos/{id}/timeline | 계산 필요(프론트) | |
| 질문 답 | — (화면 없음) | 질문 · 상태 · 답 | be/answers/routes.py `memo_answers` (id · question · asked_at · status pending·answered·no_answer · answer{headline·summary·text·calculations·sources·answered_at·read}) | 그대로 | 프론트에 화면·타입·API 함수 모두 없음(C-7). 타임라인에서는 answer 카드가 news·disclosure 로 섞여 보임 |

#### 표 B 동작

| 화면 | 동작 | 프론트 위치(파일·함수) | 엔드포인트(METHOD 경로·파일) | 판정 | 메모 |
|---|---|---|---|---|---|
| 종목 머리 | 시세 | [code].tsx · [code].native.tsx (`mockBoardStock`) | GET /stocks/{code}/quote · be/marketdata/routes.py | 그대로 | `hooks/queries.ts useQuote` 60초마다 다시 읽음 — 종가 하루 1번이라 과함(프론트에서 조절). 11/21 dev 병합 반영: 기업정보 탭 머리는 `useQuote` 연결됨, 보드 탭은 아직 `mockBoardStock` |
| 기업정보 | 차트 기간 바꾸기 | fe/ui/screens/company/*/CompanyInfo.tsx (candles 4개 미리 받음) | GET /stocks/{code}/candles?range=1W·1M·3M·1Y&adjusted= | 그대로 | 11/21 dev 병합 반영: `useCompanyInfo` 가 4번 미리 호출(연결됨) |
| 기업정보 | 투자정보 | 〃 | GET /stocks/{code}/profile | 그대로 | 11/21 dev 병합 반영: `useProfile` 연결됨 |
| 기업정보 | 분기 실적 · 건전성 | 〃 | GET /stocks/{code}/financials | 그대로 | 11/21 dev 병합 반영(이전 판정: 확인 필요): 분기 12개·건전성·금융사 규칙 모두 응답에 있음, `useFinancials` 연결됨 |
| 기업정보 | 넛지(주간보고서) | `onNudge` | — | 그대로 | 화면 이동만(묶음 4) |
| 홈 | 시장 지수 | fe/app/(main)/index.tsx · index.native.tsx (`mockHomeData.market`) | GET /market/overview · be/marketdata/routes.py | 그대로 | 실패 시 위젯만 오류(`onRetryMarket`) |
| 홈 | 지수 자세히(앱) | `onOpenMarket` → fe/app/(detail)/market/[key].tsx | GET /market/overview | 그대로 | days 없음(C-16) |
| 홈 | 뉴스 | `HOME_NEWS` | GET /news/headlines?limit= · be/marketdata/routes.py | 그대로 | 종목과 연결된 기사만(news_stocks) |
| 홈 | 뉴스 열기 | `onOpenNews` → `Linking.openURL` | — | 그대로 | |
| 홈 | 업데이트 위젯 | `mockHomeData.updates` | GET /ai-updates/summary · GET /stocks | 계산 필요(프론트) | |
| 홈 | 체크리스트 위젯 체크 | `onToggleCheck(code, itemId)` | PATCH /checklists/{id}/items/{item_id} · be/board/routes.py | 그대로 | checklist_id 는 GET /checklist-items 값 |
| 홈 | 체크리스트 위젯 항목 추가 | `onAddCheck(code, text)` | POST /checklist-items `{stock_code, text}` · be/home/routes.py | 그대로 | 체크리스트가 없으면 서버가 만듦 |
| 홈 | 위젯 켜기·순서 저장 | `onChangeWidgets` → `setWidgets` | PUT /home/layout · be/account/routes.py | 이름만 다름(check→checklist) | 위젯마다 id·span 필요 |
| 홈(웹 맞춤) | 위젯 배치 저장 | `onChangeBoard` → `setBoard` | — | 없음 | C-17 |
| 홈(웹 맞춤) | 달력 일정 · 내 일정 추가 | `schedule` | GET·POST /calendar (없음) | 없음 | C-18 |
| 홈 | 첫 시작 가이드로 | `onGoStart` → /onboarding/pick | — | 그대로 | |
| 홈 | 가격 조건 위젯 | — (지금 홈 위젯 4종에 없음) | GET /price-conditions · PATCH /memos/{id}/price-conditions/{cid} · be/home/routes.py | 그대로 | 프론트 화면 없음 → 프론트 미사용 |
| 홈 | 고정한 메모 위젯 | — (위젯 없음) | GET /memos/pinned · be/board/routes.py | 그대로 | 프론트 미사용 |
| 홈 | 종(알림) 누르기 | 앱 `router.push('/my-inbox')` | — | 없음 | 묶음 6 알림함 |
| 업데이트 | 목록 · 종목 고르기 | fe/app/(main)/updates/index*.tsx · [code]*.tsx (`mockUpdateItems`) | GET /updates?stock_code=&limit= · be/updates/routes.py | 그대로 | 최근 30일, 같은 근거는 한 줄로 합침(서버) |
| 업데이트 | 읽음 표시 | `onMarkRead(ids, true)` | POST /ai-updates/{id}/read | 그대로 | 건마다 1번 |
| 업데이트 | 안 읽음으로 되돌리기 | `onMarkRead(ids, false)` | — | 없음 | 서버는 읽음만. 결정 필요(기능 빼기 or 엔드포인트) |
| 업데이트 | 모두 읽음(앱) | `onReadAll` | — (일괄 API 없음) | 계산 필요(프론트) | 건마다 POST. 많으면 표 C-19 |
| 업데이트 | 근거 자세히 | `onOpenEvidence` → /memo/evidence · 웹 /stocks/{code}?memo=&ev= | GET /memos/{id}/timeline | 계산 필요(프론트) | 묶음 2 와 같음 |
| 업데이트 | 원문 열기 | `onOpenSource` → `Linking.openURL(u.url)` | — | 그대로 | 가격 카드는 url null |
| 업데이트 | 넛지(오늘 소식 라디오) | `onNudge` | — | 그대로 | 묶음 4 |
| 질문 답 | 질문 답 보기 | — | GET /memos/{id}/answers · be/answers/routes.py | 그대로 | 프론트 미사용(C-7·C-20) |

#### 표 C 새로 만들 것

| 항목 | 종류(엔드포인트·DB칸·표·프론트) | DB 변경(Y/N) | 메모 |
|---|---|---|---|
| C-14 분기 재무 | 엔드포인트(GET /stocks/{code}/financials 에 quarterly[] 추가 또는 새 경로) | N | **11/21 dev 병합 반영: 끝(PR #56)**. financials 응답이 `quarters[]` 12개로 바뀜. roa 는 보내지 않기로 팀 결정(화면에서도 뺌) |
| C-15 금융업 여부 | 엔드포인트 응답 칸(profile 에 sector·fin_type) | N | **11/21 dev 병합 반영: 끝(PR #56)**. profile 이 아니라 financials 응답에 `financial`·`sector`·`fin_type` |
| C-16 지수 날짜 | 엔드포인트 응답 칸(overview.indices[].days 또는 series 를 {date,value}) | N | 담당자 상의 |
| C-17 맞춤 홈 배치 | 엔드포인트 스키마(`WidgetInstance` 에 x·y·w·h, 'schedule' 종류) | N | user_settings.home_layout jsonb 그대로. 담당자 상의 |
| C-18 달력 | 엔드포인트 GET·POST /calendar | N | market_events 표 있음. 일정 데이터 채우는 작업 별도 |
| C-19 모두 읽음 | 엔드포인트 POST /ai-updates/read-all (선택) | N | |
| C-20 질문 답 화면 | 프론트(메모 상세 'AI 업데이트' 탭에 질문·답) | N | 백엔드 있음 |
| C-21 업데이트 메모 색 | 엔드포인트 응답 칸(`_ai_update.memo_color`) | N | 담당자 상의 |

### 묶음 4: 스튜디오

공통 사실:
- 백엔드에 스튜디오 라우트 없음(be/main.py include_router 12개 중 없음). backend/pipelines 에도 오디오·보고서·퀴즈·실험실 생성 코드 없음(`grep studio_items·audio_assets·tts·quiz` 0건, `pipelines/economic/ecos.py`·`fred.py` 는 지표 수집만).
- DB 는 있음: `0019 studio_items`(kind report·audio·lab, trigger auto·request, status queued·generating·ready·failed, title, period_start·end, symbols[], content jsonb, sources jsonb, error, credits_used, created_at, ready_at, **expires_at = now()+30일**, 자동 생성은 (user, kind, period_start) 하나) · `0019 audio_assets`(storage_path, mime_type, bytes, duration_sec, provider, voice, text_hash, play_position_sec) · `0019 user_settings.auto_audio`(기본 false)·`auto_report`(기본 true) · `0019 credit_grants`·`credit_ledger`(reason 에 report·audio·lab 있음) · `0019 plan_limits.monthly_credits`.
- 크레딧: be/credits/ledger.py `spend`·`usage`·`grant_purchase`, 규칙 configs/credits.yaml (report 5 · audio 5 · lab 3 · card 1 · answer 1 · price_condition 0, 월 기본 free 30 · pro 300, 산 크레딧 365일). API 는 `GET /me/usage` 하나. 차감은 매일 실행(be/credits/daily.py `charge_run`)의 카드·답만, 스튜디오 차감 호출 없음. 산 크레딧 넣기는 관리자 명령(be/credits/admin.py)뿐.
- 화면 상태는 `fe/store/studioPlayer.ts` (메모리만, mock 타이머 · 소리 없음).
- 프론트 package.json 에 소리 재생(expo-audio·expo-av 등)·알림(expo-notifications) 패키지 없음.

#### 표 A 데이터

| 화면 | mock 출처(파일·상수/함수) | 필드 | 백엔드(파일·스키마.필드) | 판정 | 메모 |
|---|---|---|---|---|---|
| 스튜디오 홈 | fe/ui/screens/studio/Studio.mock.ts `mockStudioFeatures` | key · title · desc | — | 그대로 | 고정 문구 |
| 스튜디오 홈 | Studio.mock.ts `mockMade` · store/studioPlayer.ts `made` (Studio.types.ts `MadeItem`) | id · kind · title | — (API 없음. DB `0019 studio_items.id` · `.kind` · `.title`) | 없음 | 표 C-22 |
| 스튜디오 홈 | 〃 | left ('N일 뒤 삭제') | DB `studio_items.expires_at` | 없음 | API 생기면 계산 필요(프론트) |
| 스튜디오 홈 | 〃 | sub · meta · foot (종목 수·기간 글) | DB `studio_items.symbols` · `period_start`·`period_end` | 없음 | API 생기면 계산 필요(프론트) |
| 스튜디오 홈 | 〃 | dur (오디오 길이) | DB `0019 audio_assets.duration_sec` | 없음 | |
| 스튜디오 홈 | 〃 | codes · market (보고서) · lab{code·dirs} | DB `studio_items.symbols` · `content`(jsonb) | 없음 | content 모양 정해야 함(결정 필요) |
| 스튜디오 홈 | fe/ui/screens/my/My.mock.ts `mockMyUsage.usage_pct` | 사용량 % | be/credits/ledger.py `Usage.usage_percent` (GET /me/usage) | 이름만 다름(→usage_percent) | |
| 스튜디오 홈 | `mockMyUsage.usage_refill` ('12월 1일') · `usage_renew` ('11.30') | 갱신일 | `Usage.renews_at` · `renew_label`('11.30 갱신') | 계산 필요(프론트) | |
| 스튜디오 홈 | `mockMyUsage.plan_name` ('무료 플랜') | 플랜 이름 | — (`/auth/me`·`/me/usage` 응답에 없음. DB `0001sql users.plan` free·pro) | 없음 | 응답 칸 추가(DB 변경 없음). 프론트 플랜은 무료·PLUS·PRO 3개, DB enum 은 free·pro 2개 → 결정 필요 |
| 스튜디오 홈 | Studio.mock.ts `mockStudioCounts` · fe/ui/layout/web/WebShell.mock.ts `mockStudioHead` | stock_count · ai_memo_count | be/stats/routes.py `ai_stats.linked_memos` · GET /stocks 길이 (또는 `data_stats.stocks`) | 이름만 다름(→linked_memos · stocks) | WebShell `usagePct` 는 /me/usage |
| 오디오 만들기 | Studio.mock.ts `mockAudioStocks` (`AudioStock` news[전날·3일·7일]) | 종목 · 기간별 새 소식 수 · 보유/관심 | GET /stocks (code·name·status) · GET /updates?stock_code= | 계산 필요(프론트) | 기간별 개수 API 없음. /updates 를 날짜로 세기(최근 30일까지) |
| 오디오 만들기 | `mockAudioPeriods` · `mockLastClose` | 전날·최근 3일·최근 7일 · 직전 거래일 | `quote.as_of` | 계산 필요(프론트) | |
| 오디오 만들기 | `mockAudioGen` steps · result_title | 단계 글 | DB `studio_items.status` | 없음 | 단계별 진행률 칸 없음(queued·generating·ready·failed 만) → 결정 필요 |
| 플레이어 | `mockAudioEpisode` hosts · dur · chapters · script · sources · market_source · memo_link | 대본 · 챕터 · 출처 · 연결 메모 | DB `studio_items.content`·`sources` · `audio_assets` | 없음 | 생성기(LLM 대본 + TTS) 없음. 외부 API: LLM, TTS(제공사 미정). 새 패키지: 서버 TTS SDK, 앱 재생(expo-audio 등) |
| 플레이어 | studioPlayer.ts `t` (재생 위치) | 이어 듣기 | DB `audio_assets.play_position_sec` | 없음 | |
| 주간보고서 | Studio.mock.ts `mockReport` · `mockReportStocks` (`ReportStock`·`ReportItem`) | 주·기간·시장·흐름·종목별 등락·이야기·소식·메모·볼 것·출처 | DB `studio_items(kind='report').content`·`sources` | 없음 | 생성기 없음. 시세(prices_daily)·공시·뉴스는 DB 에 있음, 문장은 LLM. 금지 문구 규칙 검사 필요 |
| 주간보고서 | `mockReport.market` (코스피·코스닥·원/달러 주간) | 주간 지수 | `overview.indices[].series['1W']` | 계산 필요 | 생성기가 쓰거나 프론트 계산 |
| 퀴즈 | Studio.mock.ts `mockQuiz` | label · q · options · answer · exp · concept · src | — | 없음 | API·DB·생성기 모두 없음. 출제는 KRX 거래 데이터(prices_daily trade_value 등) + LLM 문장. 표 C-24 |
| 퀴즈 | `mockQuiz.streak` · `week` | 연속 기록 · 이번 주 참여 | — | 없음 | 하루 1회 제출 기록 표 필요(C-24) |
| 실험실 | Studio.mock.ts `mockLabVars` (name · now · def · mid) | 변수 4개 · 지금 값 | `overview.macro[]` (BASE_RATE · US10Y · WTI) · `overview.indices[USDKRW]` | 이름만 다름(→macro[].value 등) | 'now' 문장은 계산 필요(프론트). ECOS·FRED 수집은 있음(pipelines/economic) |
| 실험실 | `mockLabStocks` (fx_strong · memo · memo_text) | 종목 · 달러 매출 비중 큼 · 연결 메모 | GET /stocks · 메모는 GET /stocks/{code}/board | 계산 필요(프론트) | fx_strong 근거(사업보고서 환율 민감도) 칸 없음 → 생성기 몫 |
| 실험실 | `mockLabLeaves(i, fxStrong)` (`LabLeaf` t · ev · why · base · note · check) | 영향 경로 | DB `studio_items(kind='lab').content` | 없음 | 생성기 없음. 공시 민감도는 disclosure_chunks 검색 + LLM. 예측 금지 문구 규칙 |
| 실험실 | `mockLabDirs` · `mockLabNote` · `mockLabDisclaimer` | 고정 문구 | — | 그대로 | |
| 충전 | My.mock.ts `mockCreditPacks` · `mockCreditDefault` · `mockPayMethods` | 상품 · 기본 · 결제 수단 | — (be/credits/ledger.py `grant_purchase` 만, 결제 연동 없음) | 없음 | 가격 미정. 결제 대행 외부 API 필요. 표 C-25 |
| 설정 | — (화면에 토글 없음) | 자동 오디오 · 자동 보고서 | DB `0019 user_settings.auto_audio`·`auto_report` | 없음 | GET·PATCH /settings 응답에 없음(be/account/service.py 매핑 표에 없음), 화면에도 없음. C-23 |

#### 표 B 동작

| 화면 | 동작 | 프론트 위치(파일·함수) | 엔드포인트(METHOD 경로·파일) | 판정 | 메모 |
|---|---|---|---|---|---|
| 스튜디오 홈 | 만든 항목 목록(30일) | fe/app/(main)/studio/index.tsx · 웹 fe/app/(main)/_layout.tsx (`useStudioPlayer().made`) | — | 없음 | C-22 GET /studio/items. 30일 지난 항목 정리 작업도 없음 |
| 스튜디오 홈 | 사용량 보기 | `usage_pct`(My.mock) · 웹 `WebUsageSheet` | GET /me/usage · be/credits/routes.py | 그대로 | 호출 때 이번 달 기본량 지급·만료 처리(서버) |
| 오디오 | 만들기 | studio/index.tsx `AudioSheet.onMake` → `useStudioPlayer.startAudio` · 웹 `WebAudioPopup` | — | 없음 | C-22 POST /studio/audio. 외부 API: LLM · TTS. 크레딧 audio 5 차감(`ledger.spend`) |
| 오디오 | 만드는 중 · 실패 · 다시 시도 | fe/app/(detail)/studio-gen.tsx (`job`·`retry`) | — | 없음 | 상태 조회 GET /studio/items/{id} (폴링) |
| 오디오 | 재생 · 넘기기 · 속도 | fe/app/(detail)/studio-player.tsx · 웹 `WebPlayer` (mock 타이머) | — (파일 주소) | 없음 | 오디오 파일 제공 경로(정적 파일·서명 URL) 필요. 앱 재생 패키지 필요 |
| 오디오 | 이어 듣기 위치 저장 | studioPlayer.ts `seek`·`leavePlayer` | — | 없음 | `audio_assets.play_position_sec` PATCH |
| 오디오 | 연결 메모 열기 | studio-player.tsx `onOpenMemo` (000660 고정) | — | 계산 필요(프론트) | content 의 memo 정보로 |
| 주간보고서 | 만들기 | studio/index.tsx `ReportSheet.onMake` → `startReport` · 웹 `WebReportPopup` | — | 없음 | C-22 POST /studio/report. LLM. 크레딧 report 5 |
| 주간보고서 | 자동 생성 | — | — | 없음 | `auto_report` 기본 true 인데 생성기·스케줄 없음. `uq_studio_items_auto_period` 로 주마다 1개 |
| 주간보고서 | 보기 | fe/app/(detail)/studio-report.tsx · fe/app/(main)/report.tsx | — | 없음 | GET /studio/items/{id} |
| 주간보고서 | '볼 것' 추가(메모로) | studio-report.tsx `onWatch` (안내만) | POST /stocks/{code}/memos (ai_linked) | 계산 필요(프론트) | 문구 '추가하면 AI 연결도 켜져요' → ai_linked=true 로 저장 |
| 퀴즈 | 문제 받기 | fe/app/(detail)/studio-quiz.tsx (`mockQuiz`) | — | 없음 | C-24 GET /studio/quiz/today. 무료(크레딧 0) |
| 퀴즈 | 제출 · 하루 1회 · 연속 기록 | `submitQuiz` (화면 상태만) | — | 없음 | C-24 POST /studio/quiz/{id}/answer |
| 실험실 | 조건 고르기 · 실행 | fe/app/(detail)/studio-lab.tsx `onRun` → `addLab` (크레딧 차감 없음) | — | 없음 | C-22 POST /studio/lab. LLM + 공시 검색. 크레딧 lab 3 |
| 실험실 | 결과 보기 · 다시 | studio-lab-result.tsx | — | 없음 | |
| 충전 | 크레딧 사기 | fe/app/(detail)/studio-charge.tsx `onPay` · 웹 `WebChargePopup` (안내만) | — | 없음 | C-25 결제. 지금은 be/credits/admin.py 명령으로만 넣을 수 있음 |
| 스튜디오 | 사용량 다 씀 → 만들기 막기 | 웹 _layout.tsx `studioFeat` (`usageSpent`) | GET /me/usage `paused` | 이름만 다름(→paused) | 퀴즈는 제외(무료) |
| 스튜디오 | 완료 알림 | studioPlayer.ts `showToast` (화면 안 토스트) · My.mock.ts `mockInbox` kind='studio' | — | 없음 | 알림함 없음(묶음 6). 푸시는 expo-notifications 없음 |
| 설정 | 자동 오디오·보고서 켜기 | — | — | 없음 | C-23 |

#### 표 C 새로 만들 것

| 항목 | 종류(엔드포인트·DB칸·표·프론트) | DB 변경(Y/N) | 메모 |
|---|---|---|---|
| C-22 스튜디오 결과물 API | 엔드포인트 GET /studio/items · GET /studio/items/{id} · POST /studio/{audio\|report\|lab} · DELETE · 30일 정리 작업 | N (0019 표 있음) | 생성기(LLM·TTS)는 별도. content·sources 모양 결정 필요. 크레딧 `ledger.spend` 호출 |
| C-23 자동 생성 설정 | 엔드포인트 응답 칸(`Settings.studio.auto_audio·auto_report`, be/account/service.py 매핑) + 프론트 설정 토글 | N (0019 칸 있음) | 스케줄 작업 별도 |
| C-24 퀴즈 | 표(quiz_questions · quiz_answers) + 엔드포인트 2개 | Y | 하루 1회 = (user, quiz_date) 유일. 연속 기록은 계산 |
| C-25 결제·충전 | 엔드포인트(결제 확인 → `grant_purchase`) + 외부 결제 대행 | N (credit_grants.payment_ref 있음) | 가격·대행사 미정. 시연 범위 밖 후보 |
| C-26 오디오 파일 제공 | 엔드포인트(파일 내려받기·스트리밍) + 서버 저장 위치 | N | audio_assets.storage_path. 앱 재생 패키지 설치 필요 |
| C-27 플랜 이름 | 엔드포인트 응답 칸(`/auth/me` 또는 `/me/usage` 에 plan) | N (users.plan 있음) | 3단계(PLUS) 쓰려면 enum 추가 → Y |
| C-28 스튜디오 단계 진행 | DB칸(studio_items.progress 등) 또는 화면 단계 표시 빼기 | Y(칸 추가 시) | 결정 필요 |

### 묶음 5: 투자 기록

공통 사실:
- 화면은 `fe/store/journal.ts` `useJournal`(zustand, 메모리만)을 씀. `fe/types/models.ts JournalEntry`·`hooks/queries.ts useJournal/useCreateJournal/useUpdateJournal/useDeleteJournal`·`fe/api/real.ts listJournal…` 는 있지만 화면은 `fe/ui/screens/journal/Journal.types.ts` 의 **다른 `JournalEntry`·`JBlock`** 을 씀(이름이 같아 헷갈림 주의).
- 백엔드: be/journal/routes.py (GET·POST /journal, PATCH·DELETE /journal/{id}) · be/journal/schemas.py `JournalCreate`·`JournalPatch`·블록 5종 (`extra="forbid"`) · be/journal/service.py `entry` · be/journal/markdown.py `blocks_to_markdown`(blocks → body Markdown, 한 방향).
- DB: `0001sql journal_entries`(title, body, kind, status, **is_pinned**, folder_id, parent_id, created_at, updated_at, deleted_at) + `0020 blocks`(jsonb) + `0019 source_memo_id` · `0001sql journal_entry_stocks` · `journal_folders`.

#### 표 A 데이터

| 화면 | mock 출처(파일·상수/함수) | 필드 | 백엔드(파일·스키마.필드) | 판정 | 메모 |
|---|---|---|---|---|---|
| 목록·기록 | fe/ui/screens/journal/Journal.mock.ts `mockJournal` (Journal.types.ts `JournalEntry`) | id | be/journal/service.py `entry.id` | 그대로 | |
| 목록·기록 | 〃 | title (첫 줄, journalParts.ts `titleOf`) | `entry.title` · `JournalCreate.title` | 계산 필요(프론트) | 화면은 blocks[0](s='title') 가 제목. 보낼 때 title 칸으로 떼고, 받을 때 title 을 첫 줄로 다시 붙이기 |
| 목록·기록 | 〃 | blocks[] `JBlock` {s, text, check?, l?, b?, i?, u?, x?} | `entry.blocks[]` `TextBlock`·`ChecklistBlock`·`TableBlock`·`AttachmentBlock` {id, type, text, highlight?, checked} | 계산 필요(프론트) | 변환표 필요(아래 줄들). 백엔드 블록은 id 필수 → 프론트가 만들어야 함 |
| 기록 | 〃 | s='body' | `TextBlock.type='paragraph'` | 이름만 다름(→paragraph) | |
| 기록 | 〃 | s='head' | `TextBlock.type='heading'` | 이름만 다름(→heading) | |
| 기록 | 〃 | s='sub' (작은 제목) | — | 없음 | heading 하나뿐. 담당자 상의(level 칸) 또는 heading 으로 합치기 |
| 기록 | 〃 | check (true·false) | `ChecklistBlock.type='checklist'` · `.checked` | 이름만 다름(→checklist·checked) | |
| 기록 | 〃 | l (dot·dash·num·quote 목록) | — | 없음 | `extra="forbid"` 라 보내면 422. 표 C-29 |
| 기록 | 〃 | b · i · u · x (굵게·기울임·밑줄·취소선) | — (`highlight` 만) | 없음 | 보내면 422. 표 C-29 |
| 기록(웹) | Journal.types.ts `html` (웹 편집기 글자 일부 서식) | 본문 HTML | — | 없음 | 서버 저장 칸 없음 → 새로 열면 서식 사라짐. 결정 필요 |
| 기록 | — | table · attachment 블록 | `TableBlock`(rows) · `AttachmentBlock`(name·url) | 계산 필요(프론트) | 화면에 표·첨부 줄 없음 → 받은 블록을 고쳐 쓸 때 **지우지 말고 그대로 다시 보내기**(보관) |
| 목록·기록 | 〃 | date · web_date · full · group (날짜 글자·묶음) | `entry.created_at` · `entry.updated_at` | 계산 필요(프론트) | Journal.mock.ts 주석도 같은 계획. 화면은 '고친 날' 기준(saveApp 이 고치면 날짜를 지금으로) → updated_at |
| 기록 | Journal.mock.ts `mockJournalNow` | 지금 | 응답 `updated_at` | 이름만 다름(→updated_at) | 저장 응답 값을 씀 |
| 목록 | 〃 | pinned | — (응답·`JournalPatch` 에 없음. DB `0001sql journal_entries.is_pinned` 있음) | 없음 | 표 C-30 (DB 변경 없음) |
| 목록 | — | stock_code · stock_name | `entry.stock_code` · `.stock_name` (journal_entry_stocks 첫 번째) | 그대로 | 화면에 종목 칸 없음 → 프론트 미사용 |
| 목록 | — | source_memo_id (결론 → 기록) | — (응답에 없음. DB `0019 journal_entries.source_memo_id`, be/journal/repository.py 는 비워 둠) | 없음 | 결론 내기 API(`/memos/{id}/conclude`)는 fe/api/index.ts `MOCK_ONLY`. 화면 위젯도 없음 |
| 목록 | journalParts.ts `preview` · `firstSentence` | 미리보기 | `entry.blocks` | 계산 필요(프론트) | 백엔드 `body`(Markdown)는 응답에 없음 |
| 목록 | (목록 길이) | 개수 | GET /journal 길이 (최대 500, be/journal/repository.py `list limit`) · be/stats `data_stats.journals` | 계산 필요(프론트) | |
| 목록 | Journal.mock.ts `mockJournalGroupOrder` · `mockJournalRecentCount` · `mockJournalLoadMs` | 묶음 순서 · 최근 3개 · 뼈대 시간 | — | 그대로 | 고정 값. LoadMs 는 연결 뒤 '불러오는 동안'으로 |

#### 표 B 동작 (store/journal.ts 함수 전부)

| 화면 | 동작 | 프론트 위치(파일·함수) | 엔드포인트(METHOD 경로·파일) | 판정 | 메모 |
|---|---|---|---|---|---|
| 목록 | 불러오기 | store/journal.ts 초기값 `entries: mockJournal` | GET /journal · be/journal/routes.py `list_journal` | 그대로 | 0020 전 DB 면 `_not_ready`(503) |
| 목록 | 정렬 | 화면: 새 기록·고친 기록을 맨 위로(`saveApp`) | 서버: `ORDER BY created_at DESC` (be/journal/repository.py `list`) | 계산 필요(프론트) | 서버는 만든 순, 화면은 고친 순 → 프론트에서 updated_at 으로 다시 정렬(또는 담당자 상의) |
| 목록 | `reset(empty)` | store/journal.ts (`__DEV__` 캡처용) | — | 그대로 | 개발용 |
| 목록·기록 | `pin(ids, on)` 고정 | store/journal.ts `pin` · fe/app/(detail)/journal/[id].tsx `onPin` | — | 없음 | C-30 |
| 목록 | `trash(ids)` 휴지통으로 | store/journal.ts `trash` · [id].tsx `onTrash` | DELETE /journal/{id} · be/journal/routes.py | 그대로 | 소프트 삭제 → /trash `journal-{id}`. 여러 개면 N번 |
| 목록 | `restore(list)` 되돌리기 | store/journal.ts `restore` (옮기기 전 목록 통째로) | POST /trash/journal-{id}/restore · be/trash/routes.py | 계산 필요(프론트) | 지운 id 마다 복원 호출 |
| 기록(앱) | `saveApp(id, blocks)` 나갈 때 저장 | store/journal.ts `saveApp` · [id].tsx `onBack`·`onNew` | 새 기록 POST /journal · 고친 기록 PATCH /journal/{id} `JournalPatch`(title·blocks) | 그대로 | 빈 기록은 안 보냄(화면 규칙 유지). 블록 변환 필요 |
| 기록(웹) | `addWeb()` 새 기록 바로 만들기 | store/journal.ts `addWeb` · web/Journal.tsx `onNew` | POST /journal (빈 title·빈 blocks 허용) | 그대로 | |
| 기록(웹) | `updateWeb(id, p)` 쓰는 대로 반영 | store/journal.ts `updateWeb` | PATCH /journal/{id} | 계산 필요(프론트) | 글자마다 보내지 않게 모아 보내기(디바운스) |
| 기록(웹) | `dropEmpty(id)` 빈 새 기록 지우기 | store/journal.ts `dropEmpty` | DELETE /journal/{id} | 확인 필요 | DELETE 는 휴지통으로 감 → 빈 기록이 휴지통에 쌓임. 서버에 '영구 삭제'(DELETE /trash/journal-{id})를 이어 부르거나, 첫 글자 칠 때 POST 하기 → 결정 필요 |
| 목록 | `setFlash` 저장 알림·반짝임 | store/journal.ts `setFlash` | — | 그대로 | 화면 상태 |
| 목록 | 검색 | journalParts.ts `searchJournal` | — | 그대로 | 프론트 검색(서버 불필요) |
| 기록 | 공유 | 앱 Note.tsx · Journal.tsx SelBar '공유' (안내만) · 웹 `copyJ` (클립보드) | — | 그대로 | 서버 불필요. 앱은 RN 내장 `Share` 로 가능(새 패키지 없음) |
| 기록 | 사진 넣기 | 웹 Journal.tsx 도구 막대 '사진' (안내만) | POST /files (없음, fe/api/index.ts `MOCK_ONLY uploadFile`) | 없음 | 서버 필요. 받은 주소로 `AttachmentBlock`. 표 C-31. 앱 사진 고르기는 expo-image-picker 없음(`expo-document-picker` 는 있음) |
| 목록 | 받아쓰기 | 앱 Journal.tsx '받아쓰기' (안내만) | — | 그대로 | 서버 불필요(기기 키보드 음성 입력). 직접 녹음·변환이면 외부 STT 필요 → 결정 필요 |
| 목록 | 알림(종) | fe/app/(main)/journal.native.tsx 머리 '알림' (안내만) | — | 없음 | 묶음 6 알림함 |
| 기록 | 내용 복사 | 앱 Note.tsx (안내만) · 웹 `copyJ` | — | 그대로 | 서버 불필요. 앱 클립보드는 expo-clipboard 없음 → 설치 필요 |
| 기록 | 기록 안에서 찾기 | 앱 Note.tsx (안내만) · 웹 journalEditor.web.tsx `FindBar` | — | 그대로 | 서버 불필요 |
| 기록 | 종목 연결 | — (화면 없음) | `JournalCreate.stock_code` · `JournalPatch.stock_code`(null 이면 해제) | 그대로 | 프론트 미사용 |

#### 표 C 새로 만들 것

| 항목 | 종류(엔드포인트·DB칸·표·프론트) | DB 변경(Y/N) | 메모 |
|---|---|---|---|
| C-29 기록 서식 | 엔드포인트 스키마(`TextBlock` 에 list·marks·level 칸, `extra` 허용) | N (blocks jsonb) | 담당자 상의. 안 하면 프론트가 서식을 버리고 보냄(422 피하기) |
| C-30 기록 고정 | 엔드포인트 칸(`entry.pinned` 응답 · `JournalPatch.pinned`) | N (is_pinned 있음) | 담당자 상의 |
| C-31 파일 올리기 | 엔드포인트 POST /files + 저장 위치 | N | 참고자료·기록 사진 같이 씀. 시연 범위 밖 후보 |
| C-32 블록 변환 함수 | 프론트(JBlock ↔ JournalBlock, title 분리, id 만들기, table·attachment 보관) | N | |

### 묶음 6: MY · 설정 · 휴지통 · 알림함 · 피드백

공통 사실:
- 앱은 fe/app/(detail)/my*.tsx, 웹은 fe/app/(main)/_layout.tsx 의 `WebSettings`·`WebTrash`·`WebInbox`·`WebFeedback`. 상태는 `fe/store/myMock.ts` `useMyMock`(프로필·다크·알림 설정·휴지통·읽음), `fe/store/theme.ts`, `fe/store/coach.ts`, `fe/store/nudge.ts` — 모두 메모리만.
- `fe/features/settings/SettingsModal.tsx`(GET·PATCH /settings, /ai/stats, /data/stats, /me/usage, MCP 를 쓰던 옛 설정 창)는 어디서도 import 되지 않음(미사용). UI v2 화면에는 세부 알림·AI 출처·민감도·MCP 설정이 없다(fe/ui 에서 `mcp`·`sensitivity`·`quiet` grep 0건).
- 백엔드 설정은 be/account/service.py `FIELD_MAP` 26칸(user_settings 20 · mcp_settings 6). `auto_audio`·`auto_report`·`home_template` 은 매핑 없음.

#### 표 A 데이터

| 화면 | mock 출처(파일·상수/함수) | 필드 | 백엔드(파일·스키마.필드) | 판정 | 메모 |
|---|---|---|---|---|---|
| MY·프로필 | fe/ui/screens/my/My.mock.ts `mockMyProfile` (My.types.ts `MyProfile`) · fe/ui/layout/web/WebShell.mock.ts `mockSideProfile` | name | be/auth/service.py `_public_user.name` (GET /auth/me · GET·PATCH /me) | 그대로 | |
| MY·프로필 | 〃 | intro (한 줄 소개) · `mockSideProfile.job` | `_public_user.bio` · be/account/schemas.py `ProfilePatch.bio`(100자) | 이름만 다름(→bio) | |
| MY·프로필 | 〃 | email | `_public_user.email` | 그대로 | |
| MY·프로필 | 〃 | provider (지금 로그인 수단) | `_public_user.providers[].current` | 확인 필요 | `current` 는 로그인 응답에서만 true. GET /auth/me·/me 는 be/auth/repository.py `get_user` → `list_identities(current_provider 없음)` 이라 **모두 false** → 최근 로그인 수단은 기기 저장 필요(결정 필요) |
| MY·프로필 | `mockSideProfile.photoUrl` | 사진 | `_public_user.avatar_url` (DB `0004 users.avatar_url`) | 그대로 | 읽기만 됨. 올리기·지우기 API 없음(C-31·C-33) |
| MY | My.mock.ts `mockMyUsage` usage_pct · usage_renew · plan_name | 사용량·갱신일·플랜 | GET /me/usage `usage_percent` · `renew_label` / plan 없음 | 이름만 다름(→usage_percent·renew_label) | plan_name 은 묶음 4 C-27 |
| MY | `version` (app.json) | 버전 | — | 그대로 | expo-constants |
| MY | store/theme.ts `dark` · store/myMock.ts `dark` (두 곳) | 다크 모드 | be/account `Settings.theme` system·light·dark (DB user_settings.theme) | 이름만 다름(dark→theme) | 서버 저장할지 기기 저장할지 결정 필요. 상태가 두 군데라 하나로 |
| 알림 설정 | store/myMock.ts `noti` (`NotiSettings` ai · studio) | AI 소식 알림 | `Settings.notifications.disclosure`·`news`·`price_condition` (DB notify_disclosure·notify_news·notify_price_condition) | 확인 필요 | 화면 1칸 ↔ 서버 3칸. 셋을 같이 켜고 끄기로 할지 결정 필요 |
| 알림 설정 | 〃 | 스튜디오 완료 알림 | — | 없음 | user_settings 에 칸 없음 → 표 C-34 |
| 사용법 안내 | store/coach.ts `seen` | 본 상태 | — | 없음 | 기기 저장 or 서버 칸(결정 필요) |
| 넛지 | store/nudge.ts `off` | 닫은 넛지 | — | 없음 | 기기 저장 or 서버 칸(결정 필요) |
| 로그인 | fe/app/login.tsx `params.recent` | 최근 로그인 수단 | — (위 provider 줄) | 없음 | 기기 저장(fe/lib/storage.ts 또는 AsyncStorage) |
| 사용량 | My.mock.ts `mockTracked` (`TrackedStock`·`TrackedMemo` title · chips) | 종목별 AI 연결 메모 · 추적 항목 칩 | GET /stocks + GET /stocks/{code}/board (ai_linked) + GET /memos/{id}/timeline `.tracking_items[].description` | 계산 필요(프론트) | 종목 수 × 메모 수만큼 호출 → 많아지면 표 C-35. 칩 '가격 조건 · 종가 150,000원 이하' 는 price_conditions 로 |
| 사용량 | 〃 | 메모 id | — (mock 에 id 없음, `onOpenMemo(code, title)`) | 계산 필요(프론트) | 연결하면 메모 id 를 가지고 열기 |
| 데이터 · 탈퇴 | My.mock.ts `mockWithdrawCounts` (memo · journal · stock · ai) | 개수 | be/stats/routes.py `data_stats` memos · journals · stocks + `ai_stats.linked_memos` | 이름만 다름(→memos·journals·stocks·linked_memos) | data_stats.memos 는 kind='note' 만(체크리스트 제외) |
| 플랜 | My.mock.ts `mockPlans` · `mockPlanCompare` · `mockPlanNotes` · `mockPlanDefault` | 무료·PLUS·PRO | DB `plan_type` free·pro · configs/credits.yaml monthly | 확인 필요 | 3단계 ↔ 2단계. 가격 미정. 묶음 4 C-27 |
| 휴지통 | My.mock.ts `mockTrash` · store/myMock.ts `trash` (`TrashItem`) | id | be/trash/service.py `list[].id` (`memo-{id}`·`journal-{id}`·`stock-{code}`) | 그대로 | 화면 id 와 모양이 다름(t1…) — 서버 값을 그대로 쓰면 됨 |
| 휴지통 | 〃 | kind 메모·투자 기록·종목 | `list[].kind` memo·checklist·reference·journal·stock | 이름만 다름(→kind) | 화면에 체크리스트·참고자료 종류 없음 → 값 바꾸기 표 필요 |
| 휴지통 | 〃 | title | `list[].title` | 그대로 | |
| 휴지통 | 〃 | sub ('SK하이닉스 · 메모') | `list[].context` ('SK하이닉스 / 메모') | 이름만 다름(→context) | 구분자 '/' vs '·' |
| 휴지통 | 〃 | ago ('2시간 전') | `list[].deleted_at` | 계산 필요(프론트) | |
| 휴지통 | 〃 | stock_code | — (be/trash/repository.py 는 symbol 을 읽지만 응답에 안 넣음) | 없음 | 담당자 상의(복원 후 보드 열기에 필요) |
| 알림함 | My.mock.ts `mockInbox` (`InboxItem` id · kind ai·studio · day · title · sub · when · stock_code) · `mockInboxUnread` | 알림 목록 · 안 읽음 | — (API·표 없음) | 없음 | 표 C-36. AI 소식은 tracking_updates 로 대신 만들 수 있음(결정 필요) |
| 알림함 | WebShell.mock.ts `mockUnreadNotifs` | 종 숫자 | — | 없음 | 묶음 3 과 같음 |
| 피드백 | My.mock.ts `mockReportKinds` · `mockStarLabels` | 오류 종류 · 별점 글 | be/stats/routes.py `FeedbackPayload.categories` · `.rating` | 이름만 다름(→categories·rating) | 종류 글은 고정 |
| 피드백 | My.types.ts `FeedbackDraft` mode · star · text · where · kinds · detail | 보낼 내용 | `FeedbackPayload` kind general·bug · rating · screen · categories · message | 이름만 다름(mode→kind, star→rating, where→screen, kinds→categories) | text·detail 두 칸 → message 하나로 합치기(계산 필요, 프론트) |
| 도움말 · 정보 | My.mock.ts `mockFaq` · `mockDataSources` · `mockOss` · fe/ui/screens/auth/AuthLegal.ts | 고정 문서 | — | 그대로 | |
| 탈퇴 | My.types.ts `WITHDRAW_REASONS` | 탈퇴 이유 | — | 없음 | 저장 칸 없음(C-37) |

#### 표 B 동작

| 화면 | 동작 | 프론트 위치(파일·함수) | 엔드포인트(METHOD 경로·파일) | 판정 | 메모 |
|---|---|---|---|---|---|
| 프로필 | 로그아웃 | fe/app/(detail)/my-profile.tsx `onLogout` · 웹 _layout.tsx `logout` → store/auth.ts `signOut` | POST /auth/logout · be/auth/routes.py | 그대로 | 이미 연결됨(mock 인증이 아니면) |
| 프로필 | 이름 · 한 줄 소개 저장 | my-profile.tsx `onChange` → `useMyMock.setProfile` · 웹 `onChangeProfile` | PATCH /me `ProfilePatch`(name ≤40 · bio ≤100) · be/account/routes.py | 이름만 다름(intro→bio) | `fe/api/real.ts updateMe`·`hooks/queries.ts useUpdateMe` 있음. 저장 뒤 store/auth `setUser` |
| 프로필 | 사진 바꾸기 · 지우기 | `onPhoto` · `onPhotoDelete` (안내만) | — | 없음 | C-31(파일 올리기) + C-33(avatar_url 바꾸기) |
| 프로필 | 소셜 계정 연결 | 앱 `onLink` (토스트만 '계정을 연결했어요') | — | 없음 | 로그인한 사용자에 두 번째 소셜을 붙이는 API 없음(be/auth/repository.py `get_or_create_user` 는 로그인용). 표 C-38. 지금 토스트는 거짓 성공 문구 → 빼거나 안내로 |
| MY | 다크 모드 | fe/app/(detail)/my.tsx `onToggleDark` → store/theme.ts | PATCH /settings `theme` (선택) | 확인 필요 | 결정 필요(기기 vs 서버) |
| 알림 설정 | AI · 스튜디오 알림 켜기 | fe/app/(detail)/my-noti.tsx `onChange` · 웹 `onNoti` | PATCH /settings `notifications.*` | 확인 필요 | 위 표 A 참고 |
| 사용량 | 사용량 · 추적 현황 | fe/app/(detail)/my-usage.tsx (`mockMyUsage`·`mockTracked`) | GET /me/usage · GET /stocks · board · timeline | 계산 필요(프론트) | |
| 사용량 | 추적 메모 → 메모 열기 | `onOpenMemo(code, title)` → /stocks/{code} (보드만 엶) | — | 계산 필요(프론트) | 메모 id 로 /memo/{id} (앱) · /stocks/{code}?memo= (웹) |
| 플랜 | 플랜 시작(결제) | fe/app/(detail)/my-plans.tsx `onStart` (안내만) | — | 없음 | 묶음 4 C-25 |
| 데이터 | 개수 | fe/app/(detail)/my-data.tsx (`mockWithdrawCounts`) | GET /data/stats · GET /ai/stats · be/stats/routes.py | 그대로 | `hooks/queries.ts useDataStats`·`useAiStats` 있음 |
| 데이터 | 내보내기(웹) | 웹 `onExport` (안내만) | POST /data/export (없음, fe/api/index.ts `MOCK_ONLY exportData`) | 없음 | 표 C-39 |
| 데이터 | 전체 삭제 | `onWipe` (안내만) | DELETE /data (없음, `MOCK_ONLY deleteAllData`) | 없음 | 표 C-39 |
| 탈퇴 | 탈퇴 | fe/app/(detail)/my-withdraw.tsx `onConfirm` · 웹 `onWithdraw` (안내만) | — | 없음 | DB `users.deleted_at` 칸은 있음(be/account/service.py `get_me` 가 deleted_at 이면 404). 표 C-37 |
| 휴지통 | 목록 | fe/app/(detail)/my-trash.tsx · 웹 `WebTrash` (`useMyMock.trash`) | GET /trash · be/trash/routes.py | 그대로 | 메모·체크리스트·참고자료·투자 기록·종목 함께, 지운 시각 최신순 |
| 휴지통 | 복원 | `onRestore(item)` | POST /trash/{id}/restore | 그대로 | 메모 복원 시 종목도 되살림(be/trash/repository.py `restore_memo`) |
| 휴지통 | 복원 되돌리기 | `onUndo(item)` → `undoRestore` | memo: DELETE /board-items/{id} · journal: DELETE /journal/{id} · stock: DELETE /stocks/{code} | 계산 필요(프론트) | 종류별로 다른 삭제를 다시 부름 |
| 휴지통 | 영구 삭제 | `onPurge(item)` (안내만) | DELETE /trash/{id} · 409(AI 추적 사용 기록이 있는 메모) | 그대로 | 409 문구 화면에 필요 |
| 휴지통 | 비우기 | `onPurge(null)` (안내만) | — (일괄 API 없음) | 계산 필요(프론트) | 항목마다 DELETE. 409 난 항목은 남김 |
| 알림함 | 목록 · 열기 | fe/app/(detail)/my-inbox.tsx · 웹 `WebInbox` (`mockInbox`) | — | 없음 | C-36 |
| 알림함 | 읽음 · 모두 읽음 | `read(id)` · `readAll` | — | 없음 | C-36 |
| 피드백 | 보내기 | fe/app/(detail)/my-feedback.tsx `onSend` · 웹 `WebFeedback.onSend` (안내만) | POST /feedback `FeedbackPayload` · be/stats/routes.py (204) | 이름만 다름 | `hooks/queries.ts useSendFeedback` 있음 |
| 도움말 | 사용법 다시 보기 | my-help.tsx `onReplayGuide` → store/coach.ts `replay` | — | 그대로 | |
| 정보 | 약관·개인정보·투자 안내·오픈소스 | my-doc.tsx | — | 그대로 | 고정 문서 |

#### 표 C 새로 만들 것

| 항목 | 종류(엔드포인트·DB칸·표·프론트) | DB 변경(Y/N) | 메모 |
|---|---|---|---|
| C-33 프로필 사진 | 엔드포인트(PATCH /me avatar_url 또는 POST /me/avatar) | N (users.avatar_url 있음) | C-31 파일 올리기 필요 |
| C-34 스튜디오 알림 설정 | DB칸(user_settings.notify_studio) + Settings 매핑 | Y | |
| C-35 추적 현황 묶음 응답 | 엔드포인트(GET /me/tracking: 종목별 AI 메모·항목) | N | 선택. 호출 수 줄이기 |
| C-36 알림함 | 표(notifications: user_id · kind · title · sub · ref · read_at · created_at) + 엔드포인트(GET /notifications · POST read · read-all) + 만드는 쪽(매일 실행·스튜디오 완료) | Y | 담당자 상의. 시연 대안: AI 소식은 tracking_updates 를 알림처럼 보여 주기(DB 변경 없음) |
| C-37 탈퇴 | 엔드포인트(DELETE /me: users.deleted_at · 세션 끊기 · 데이터 정리) + 이유 저장(feedbacks kind='withdraw' 재사용 가능) | N | 담당자 상의. 개인정보 삭제 기준 결정 필요 |
| C-38 소셜 계정 연결 | 엔드포인트(GET /auth/{provider}/link/start 등) | N (auth_identities 있음) | 시연 범위 밖 후보 |
| C-39 내보내기 · 전체 삭제 | 엔드포인트 POST /data/export · DELETE /data | N | 시연 범위 밖 후보 |
| C-40 기기 저장 모음 | 프론트(AsyncStorage: 최근 로그인 수단 · 사용법 본 상태 · 닫은 넛지 · 다크 · 최근 검색 · 보드 순서 안내) | N | 결정 필요(서버로 올릴 것과 나누기) |
| C-41 휴지통 종목 코드 | 엔드포인트 응답 칸(`TrashItem.stock_code`) | N | 담당자 상의 |

### 합본

#### 가장 큰 사실 (연결 순서에 영향)

- **화면이 `api.*` 를 거의 안 쓴다.** 화면 파일은 `*.mock.ts`·mock store 를 직접 import 한다. `fe/api/index.ts` 의 `EXPO_PUBLIC_USE_REAL_STOCKS`·`USE_REAL_BOARD`·`USE_MOCK=false` 스위치를 켜도 바뀌는 곳은 로그인(store/auth.ts) 뿐이다. 연결 = 화면마다 mock import 를 `hooks/queries.ts` 로 바꾸는 작업이다. (11/21 dev 병합 반영: 기업정보 탭이 `useCompanyInfo` 로 이 작업을 처음 끝냄 → 다른 화면도 같은 틀(화면별 hook + `toXxxData` 변환)을 따르면 된다.)
- `fe/types/models.ts`·`fe/api/*`(계약 쪽 타입)과 화면 타입(`ui/screens/**/*.types.ts`)이 따로 있다. 필드 이름(stock_code↔code 등)·모양(JBlock↔JournalBlock 등)을 바꾸는 변환 층이 필요하다.

#### 판정 개수 (표 A + 표 B, 자동 집계)

| 묶음 | 그대로 | 이름만 다름 | 계산 필요 | 없음 | 확인 필요 | 합 |
|---|---|---|---|---|---|---|
| 1 로그인·온보딩 | 20 | 7 | 6 | 5 | 4 | 42 |
| 2 보드·메모·AI 연결 | 35 | 17 | 18 | 9 | 7 | 86 |
| 3 기업정보·홈·업데이트 (11/21 dev 병합 반영, 이전 25·17·15·14·3) | 31 | 16 | 14 | 12 | 1 | 74 |
| 4 스튜디오 | 3 | 4 | 7 | 30 | 0 | 44 |
| 5 투자 기록 | 15 | 4 | 9 | 9 | 1 | 38 |
| 6 MY·설정·휴지통·알림함 | 14 | 10 | 7 | 16 | 5 | 52 |
| 누락 표(아래) | 26 | 1 | 12 | 8 | 5 | 52 |
| **합** | **144** | **59** | **73** | **89** | **23** | **388** |

#### 누락 표 (묶음 1~6 표에 이름이 한 번도 안 나온 화면·mock 값)

뽑은 방법: `ui/screens/**` 파일 이름 · `*.mock.ts` 와 `store/*.ts` 의 export 이름 · `app/**` 라우트 경로를 이 절 본문과 grep 으로 대조. 아래 표를 넣은 뒤 다시 돌려 누락 0 확인.

| 구분 | 파일 · 이름 | 무엇 | 백엔드 · 엔드포인트 | 판정 | 메모 |
|---|---|---|---|---|---|
| mock | fe/ui/layout/app/BottomTabBar.mock.ts `mockTabBadges` (fe/app/(main)/_layout.native.tsx) | 앱 탭 '업데이트' 숫자 5 | GET /stocks `MyStockResponse.unread_updates` 합 | 계산 필요(프론트) | |
| mock | fe/ui/screens/home/Home.mock.ts `mockHomeNow` | 홈 '지금' | — | 계산 필요(프론트) | 기기 시각(`mockHomeData.now` 와 같은 값) |
| mock | fe/ui/screens/memo/MemoDetail.mock.ts `mockMemoById` (fe/app/(detail)/memo/link.tsx) | 메모 하나 찾기 | GET /board-items/{id} `MemoResponse` | 그대로 | |
| mock | fe/ui/screens/board/MemoBoard.mock.ts `mockEmptyStock` | 빈 보드 종목(KB금융) | GET /stocks/{code}/board 빈 배열 + quote | 그대로 | |
| mock | fe/ui/screens/company/CompanyInfo.mock.ts `mockCompanySK` · `mockCompanyKB` · `mockCompanyByCode` | 기업정보 한 화면 값 묶음 | quote + profile + candles(4기간) + financials | 계산 필요(프론트) | 11/21 dev 병합 반영: useCompanyInfo.ts `toCompanyData` 로 구현됨. `mockCompanyByCode` 는 이제 '준비 중' 화면 틀로만 씀. C-14·C-15 끝 |
| mock | fe/ui/screens/company/companyData.mock.ts `CandleRow` · `finSK` (`health_prev` 포함) | 원시 캔들 줄 · SK 분기·건전성 | candles · financials | 계산 필요(프론트) | `health_prev`(이전 분기 건전성)는 화면에서 안 씀(grep 0건) → 버려도 됨 |
| mock | fe/ui/screens/my/My.mock.ts `PlanInfo` | 플랜 타입 | DB `plan_type` free·pro | 확인 필요 | 묶음 6 플랜 줄 |
| store | fe/store/auth.ts `useAuth` | 로그인 상태 | 묶음 1 표 B (refresh·logout·me) | 그대로 | |
| store | fe/store/coach.ts `useCoach` | 사용법 안내 단계 · 본 상태 | — | 없음 | C-40 |
| store | fe/store/journal.ts `JournalFlashIn` · `JournalFlash` | 저장 알림 · 반짝임 | — | 그대로 | 화면 상태 |
| store | fe/store/nudge.ts `NudgeId` · `useNudgeStore` · `useNudge` | 넛지 닫힘 | — | 없음 | C-40 |
| store | fe/store/studioPlayer.ts `StepState` · `GenJob` · `WebStudioView` | 만들기 작업·화면 상태 | DB `studio_items.status` | 없음 | C-22 · C-28 |
| store | fe/store/studioPlayer.ts `fmt` · `chapterAt` · `lineAt` | 재생 시각 · 챕터 · 대본 줄 | — | 계산 필요(프론트) | 결과물 content 의 chapters·script 로 |
| store | fe/store/theme.ts `useTheme` | 다크 | `Settings.theme` | 이름만 다름(→theme) | store/myMock.ts `dark` 와 중복 |
| store | fe/store/ui.ts `SettingsSection` · `ModalState` · `useUI` | 탭바 숨김 · 토스트 · 옛 모달 | — | 그대로 | 모달은 옛 셸용, 쓰는 곳 없음(정리 대상) |
| 화면 | fe/ui/screens/auth/AuthGlyphs.tsx · IntroArtwork.tsx · app/IntroArtwork.tsx · LegalDocumentView.tsx · web/authKeyboard.web.ts | 그림 · 문서 보기 · 키보드 | — | 그대로 | 서버 불필요 |
| 타입 | fe/ui/screens/auth/Auth.types.ts · onboarding/Onboarding.types.ts · onboarding/FirstHome.types.ts | 타입 | 묶음 1 표 A | 그대로 | 필드는 묶음 1 |
| 화면 | fe/ui/screens/onboarding/web/OnboardingFlow.tsx · app/OnboardingFlow.tsx · app/FirstMemo.tsx | 종목 고르기 · 첫 메모 | 묶음 1 표 B (onboarding/pick.tsx · memo/new.tsx) | 그대로 | |
| 화면 | fe/ui/screens/home/web/CustomHome.tsx | 맞춤 홈 격자 | — | 없음 | C-17 |
| 화면 | fe/ui/screens/home/web/HomeWidgets.tsx · app/HomeWidgets.tsx | 홈 위젯 | 묶음 3 | 그대로 | |
| 화면 | fe/ui/screens/home/app/MarketDetail.tsx | 지수 자세히 | GET /market/overview | 그대로 | days 없음(C-16) |
| 화면 | fe/ui/screens/home/app/NewsBrowser.tsx | 앱 안 뉴스 브라우저(뼈대 뒤 제목만) | — | 그대로 | 서버 불필요. 실제 페이지는 expo-web-browser(있음) 또는 react-native-webview(없음, 설치 필요) |
| 타입 | fe/ui/screens/home/Home.types.ts | 타입 | 묶음 3 표 A | 그대로 | |
| 계산 | fe/ui/screens/home/homeFormat.ts (`ago`·`mmdd`·`spark`·`webSeries`·`rangeLabels`) | 홈 숫자·날짜·차트 | overview | 계산 필요(프론트) | `rangeLabels` 는 days 가 있어야 함(C-16) |
| 부품 | fe/ui/screens/home/web/homeDom.web.tsx · board/web/boardDom.web.tsx · stocks/web/stocksDom.web.tsx · stocks/app/stockGlyphs.tsx · journal/app/journalGlyphs.tsx · my/web/inboxKeys.web.ts · my/web/parts.tsx · my/app/parts.tsx · memo/web/parts.tsx | DOM · 그림 · 공용 부품 | — | 그대로 | 서버 불필요 |
| 타입 | fe/ui/screens/board/Checklist.types.ts | 체크리스트 화면 props | 묶음 2 | 그대로 | |
| 계산 | fe/ui/screens/memo/memoTimeline.ts `buildTimeline` (`TimelineRow`) | AI 업데이트 탭 줄 만들기 | GET /memos/{id}/timeline entries | 계산 필요(프론트) | 서버 entries(memo_created·memo_edit·ai_linked·update)를 rev·ai·feed 로. 서버가 이미 최신순 정렬 |
| 화면 | fe/ui/screens/memo/HistoryContent.tsx | 수정 이력 | timeline | 계산 필요(프론트) | 묶음 2 |
| 화면 | fe/ui/screens/memo/web/ConnectDialog.tsx | 웹 AI 연결 창 | PUT /memos/{id}/ai-link · POST memos | 확인 필요 | 흐름 차이(C-11) |
| 화면 | fe/ui/screens/memo/app/MemoMoreSheet.tsx | 색 · 고정 · 복사 · 삭제 메뉴 | 묶음 2 표 B | 그대로 | 복사는 API 없음 |
| 화면 | fe/ui/screens/stocks/app/AddStockSheet.tsx | 앱 종목 추가 시트 | GET /stocks/search · POST /stocks | 확인 필요 | '많이 찾는' 없음(C-2), KOSPI 만(C-13) |
| 계산 | fe/ui/screens/company/companyFormat.ts (`yoyAt`·`healthScore`·`TERMS`) | 전년 대비 · 건전성 점수 · 용어 | financials | 계산 필요(프론트) | 11/21 dev 병합 반영: 분기 12개가 와서 전년 대비 계산 가능. `TERMS` 에서 roa 빠짐, EPS·BPS 설명은 '직전 사업연도 · 한국투자증권' |
| 화면 | fe/ui/screens/company/app/CompanyCharts.tsx | 기업정보 차트 | candles | 그대로 | |
| 타입 | fe/ui/screens/updates/Updates.types.ts | 타입 | 묶음 3 | 그대로 | |
| 계산 | fe/ui/screens/updates/updatesFormat.ts (`ago`·`dayGroup`·`unreadOf`) | 시간 · 날짜 묶음 · 안 읽음 수 | GET /updates | 계산 필요(프론트) | |
| 계산 | fe/ui/screens/studio/labParts.ts (`labGroups`·`labTitle`) | 실험 결과 묶기 | — | 없음 | C-22 |
| 계산 | fe/ui/screens/studio/reportParts.tsx (`reportSummary`·차트) | 보고서 요약 문장 · 주간 차트 | — | 없음 | C-22. 요약 문장을 프론트가 만드는 부분은 생성기와 역할이 겹침 → 결정 필요 |
| 화면 | fe/ui/screens/studio/web/QuizLab.tsx · web/StudioHome.tsx · app/StudioHome.tsx · app/LabResult.tsx · app/MiniPlayer.tsx | 스튜디오 화면 | 묶음 4 | 없음 | API 없음 |
| 화면 | fe/ui/screens/my/web/Help.tsx · app/Help.tsx | 도움말 | — | 그대로 | |
| 화면 | fe/ui/screens/my/web/SettingsTabs.tsx | 웹 설정 탭(알림·사용량·플랜·데이터·정보) | 묶음 6 | 확인 필요 | 알림 1칸↔3칸 등 |
| 라우트 | fe/app/ui-v2-check.tsx | 부품 확인 화면(`__DEV__`, 삭제 예정) | — | 그대로 | |
| 라우트 | fe/app/+not-found.tsx | 없는 주소 | — | 그대로 | |
| 라우트 | fe/app/intro.tsx | 인트로(`mockIntroPages`) | — | 그대로 | |
| 라우트 | fe/app/(main)/_layout.native.tsx | 앱 탭 · 로그인 확인 · `mockTabBadges` | GET /stocks | 계산 필요(프론트) | |
| 라우트 | fe/app/(main)/help.tsx | 웹 도움말(`mockFaq`) | — | 그대로 | |
| 라우트 | fe/app/(main)/journal.tsx | 웹 투자 기록 | GET·POST·PATCH·DELETE /journal | 계산 필요(프론트) | 블록 변환(C-32) |
| 라우트 | fe/app/(main)/stocks/index.tsx · fe/app/(main)/stocks/index.native.tsx | 내 종목 | GET /stocks · 묶음 2 | 그대로 | |
| 라우트 | fe/app/(main)/stocks/_layout.tsx · fe/app/(main)/stocks/_layout.native.tsx · fe/app/(main)/updates/_layout.tsx · fe/app/(main)/updates/_layout.native.tsx · fe/app/(detail)/_layout.tsx | 화면 쌓기 | — | 그대로 | |
| 라우트 | fe/app/(main)/updates/index.tsx · fe/app/(main)/updates/index.native.tsx · fe/app/(main)/updates/[code].tsx · fe/app/(main)/updates/[code].native.tsx | 업데이트 · 종목 업데이트 | GET /updates | 그대로 | |
| 라우트 | fe/app/(detail)/my-info.tsx · fe/app/(detail)/my-doc.tsx · fe/app/(detail)/my-help.tsx | 정보 · 문서 · 도움말 | — | 그대로 | |
| 라우트 | fe/app/(detail)/studio-lab-result.tsx | 실험 결과 | — | 없음 | C-22 |
| 화면 | fe/features/home/widgets/MarketWidgets.tsx · fe/features/settings/SettingsModal.tsx · fe/features/board/BoardCards.tsx · fe/features/company/glossary.ts | 옛 화면·부품 | (hooks/queries 사용) | 확인 필요 | `features/` 는 대상 밖이지만 참고: MarketWidgets·SettingsModal 은 import 0건(미사용). 지울지 결정 필요 |

#### 프론트 미사용 엔드포인트

전체 60개(backend/app 라우터 12개 + main.py health 2개, `grep @router.` 기준. 이 문서 1절은 같은 목록을 60개로 셈).

(가) 프론트 어디에도 대응이 없음 (api 함수 · 화면 둘 다 없음) — **5개**

| METHOD 경로 | 파일 | 메모 |
|---|---|---|
| POST /api/v1/memos/{memo_id}/confirmations | be/board/routes.py | C-7 · C-10 |
| GET /api/v1/memos/{memo_id}/answers | be/answers/routes.py | C-7 · C-20 |
| GET /api/v1/me | be/account/routes.py | 프론트는 GET /auth/me 를 씀(같은 User 모양). 중복 |
| GET /health | be/main.py | 운영 점검용 |
| GET /health/db | be/main.py | 운영 점검용 |

(나) api 함수는 있으나 화면 대응이 없음 — **8개**

| METHOD 경로 | 파일 | 프론트 함수 | 메모 |
|---|---|---|---|
| GET /api/v1/stocks/{code} | be/stocks/routes.py | `getStock` | |
| GET /api/v1/memos/pinned | be/board/routes.py | `listPinnedMemos` | 고정 메모 위젯 없음 |
| POST /api/v1/stocks/{code}/references | be/board/routes.py | `createReference` | 참고자료 화면 없음 |
| GET /api/v1/stocks/{code}/ai-updates | be/updates/routes.py | `listStockAiUpdates` | |
| GET /api/v1/price-conditions | be/home/routes.py | `listPriceConditions` | 가격 조건 위젯 없음 |
| PATCH /api/v1/memos/{memo_id}/price-conditions/{condition_id} | be/home/routes.py | `setPriceConditionTracking` | 〃 |
| GET /api/v1/settings | be/account/routes.py | `getSettings` | UI v2 는 theme·알림 일부만(확인 필요). 세부 알림·AI·MCP 화면 없음 |
| PATCH /api/v1/settings | be/account/routes.py | `updateSettings` | 〃 |

참고 — (다) 화면 동작은 있는데 api 함수가 없음: PUT /api/v1/stocks/order · PUT /api/v1/stocks/{code}/board-order (C-7). (라) 프론트 함수만 있고 백엔드가 없음(fe/api/index.ts `MOCK_ONLY`): GET·POST /calendar · GET /insights/memo-backtest · /insights/compare-memos · /insights/conclude-candidates · POST /memos/{id}/conclude · POST /files · POST /data/export · DELETE /data · DELETE /mcp/apps/{id}. 그 밖에 GET /market/overview 의 `macro` 부분은 화면이 안 씀.

#### 표 C 합본 (중복 제거)

'11/27 시연 필요' 는 내 판단이다: 기준 흐름 = docs/pr-ui-v2-draft.md '확인 방법' 흐름 중 소개 → 로그인 → 약관 → 종목 고르기 → 첫 메모 → 홈 · 보드 · 메모 · 기업정보 · 업데이트 · 투자 기록. 스튜디오·MY 는 mock 유지로 가정(결정 필요 표 15번).

| 항목 | 종류 | DB 변경 | 11/27 시연 필요(Y/N) | 선행 조건 | 담당자 상의 |
|---|---|---|---|---|---|
| 화면 → hooks/queries 바꾸기 (가장 큰 일) | 프론트 | N | Y | 아래 C-7·C-8·변환 층 | N |
| C-5 신규 사용자 판별 | 프론트 | N | Y | GET /stocks 연결 | N |
| C-7 프론트 API 함수 4개(board-order · stocks/order · confirmations · answers) | 프론트 | N | Y | — | N |
| C-8 analysis 받기 | 프론트 | N | Y | — | N |
| C-11 AI 연결 흐름(미리보기 없음) | 프론트(또는 분석 전용 엔드포인트) | N | Y | 결정 필요 7번 | Y (엔드포인트 안이면) |
| C-32 투자 기록 블록 변환 | 프론트 | N | Y | — | N |
| C-40 기기 저장 모음(최근 로그인 · 안내 본 상태 · 넛지 · 다크 · 최근 검색 · 보드 순서 안내) | 프론트(AsyncStorage 이미 설치) | N | Y | 결정 필요 5번 | N |
| C-14 분기 재무 | 엔드포인트 | N | Y | — | 11/21 dev 병합 반영: 끝(PR #56) |
| C-15 금융업 여부(financials 에 financial·sector·fin_type) | 응답 칸 | N | Y | — | 11/21 dev 병합 반영: 끝(PR #56) |
| C-16 지수 날짜 | 응답 칸 | N | Y | — | Y |
| C-10 확인 질문 화면 | 프론트 | N | N | C-7 · C-8 | N |
| C-20 질문 답 화면 | 프론트 | N | N | C-7 | N |
| C-1 약관 동의 저장 | DB칸 또는 표 + 엔드포인트 | Y | N | 결정 필요 1번 | Y |
| C-2 '많이 찾는 종목' | 엔드포인트 + 출처 | 출처 따라(고정 목록이면 N) | N | 결정 필요 2번 | Y |
| C-3 온보딩 종목 일괄 저장 | 엔드포인트 | N | N | — | Y |
| C-4 종목별 메모 수·AI 연결 수 | 응답 칸 | N | N | 결정 필요 3번 | Y |
| C-6 종목 업종 · 로고 | DB칸 + 응답 칸 + 프론트 | Y | N | 업종 출처 | Y |
| C-9 근거 차트 기간 | 엔드포인트 | N | N | — | Y |
| C-12 추적 문장(quote) 응답 | 응답 칸 | N | N | — | Y |
| C-13 KOSDAQ 검색 | 백엔드 쿼리 | N | N | 결정 필요 10번 | Y |
| C-17 맞춤 홈 배치 | 스키마 | N | N | — | Y |
| C-18 달력 | 엔드포인트 | N | N | 일정 데이터 채우기 | Y |
| C-19 모두 읽음 | 엔드포인트 | N | N | — | Y |
| C-21 업데이트 메모 색 | 응답 칸 | N | N | — | Y |
| C-22 · C-26 스튜디오 결과물 API · 생성기 · 오디오 파일 | 엔드포인트 + 작업 + 외부 API(LLM·TTS) + 앱 재생 패키지 | N (0019 표 있음) | N | 결정 필요 15번 | Y |
| C-28 스튜디오 단계 진행 | DB칸 | Y(칸 추가 시) | N | C-22 | Y |
| C-23 자동 생성 설정 | 응답 칸 + 설정 토글 | N | N | C-22 | Y |
| C-24 퀴즈 | 표 + 엔드포인트 + 생성기 | Y | N | — | Y |
| C-25 결제 · 충전 | 엔드포인트 + 외부 결제 | N | N | 가격 · 대행사 | Y |
| C-27 플랜 이름(· PLUS 단계) | 응답 칸(+ enum 값) | PLUS 쓰면 Y | N | 결정 필요 16번 | Y |
| C-29 기록 서식 | 스키마 | N | N | 결정 필요 17번 | Y |
| C-30 기록 고정 | 응답 칸 · patch 칸 | N | N | — | Y |
| C-31 · C-33 파일 올리기 · 프로필 사진 | 엔드포인트 + 저장 위치 | N | N | 저장 위치 | Y |
| C-34 스튜디오 알림 설정 | DB칸 | Y | N | C-36 | Y |
| C-35 추적 현황 묶음 응답 | 엔드포인트 | N | N | — | Y |
| C-36 알림함 | 표 + 엔드포인트 + 만드는 작업 | Y | N | 결정 필요 22번 | Y |
| C-37 탈퇴 | 엔드포인트 | N | N | 삭제 기준 | Y |
| C-38 소셜 계정 연결 | 엔드포인트 | N | N | — | Y |
| C-39 내보내기 · 전체 삭제 | 엔드포인트 | N | N | — | Y |
| C-41 휴지통 종목 코드 | 응답 칸 | N | N | — | Y |

DB 변경 항목을 마이그레이션 하나(0022 후보)로 묶을 수 있는지:
- 대상: C-1 약관(users 칸 또는 user_consents 표) · C-6 `stocks.industry` · C-24 quiz 표 2개 · C-34 `user_settings.notify_studio` · C-36 notifications 표, 조건부 C-27 `plan_type` 값 추가 · C-28 `studio_items.progress`.
- 지금 head 는 `0021_user_stocks_position`(가지 없음, 0006 두 개는 `511517f9874b` 에서 이미 합쳐짐). 모두 새 표이거나 NULL 허용·기본값 칸이라 기존 데이터를 안 바꾼다 → **0022 하나로 묶을 수 있다.**
- 단 enum 값 추가(C-27)는 0019 처럼 `autocommit_block` 에서 먼저 실행해야 한다(0019 `ENUM_SQL` 방식). 같은 파일 안에서 가능.
- 시연(11/27)에 필요한 DB 변경은 없다(위 표에서 DB 변경 Y 항목은 모두 시연 N).

#### 11:45 빠른 조사 표(2절)에서 판정이 바뀐 것만

| 항목 | 11:45 판정 | 전수 검사 판정 | 근거 |
|---|---|---|---|
| 종목 | 있음·그대로 | 있음·보강 | 검색·조회가 KOSPI 만(be/stocks/repository.py `search_kospi`·`get_kospi`), 업종·로고·많이 찾는 종목 없음 |
| AI 연결 | 있음·그대로 | 있음·흐름 결정 필요 | 분석 미리보기 없음(PUT 한 번에 켜기+분석), 추적 문장 없음, 확인 질문 화면·함수 없음 |
| 업데이트 타임라인 | 있음·그대로 | 있음·보강 | 조건가는 메모 price_conditions 와 맞춰야 함, quote_mark·provider·근거 차트 기간 없음, 메모 색 없음 |
| 지수·매크로 | 있음·보강 (매크로 지표 없음) | 있음·보강 (지수 날짜 없음) | 매크로 5개는 `overview.macro` 에 있음(be/marketdata/service.py `MACROS`). 모자란 것은 지수 series 의 날짜 |
| 재무 | 있음·그대로 | 있음·보강 → **11/21 dev 병합 반영: 있음·그대로** | 병합 전: 연간만, 분기·ROA·금융업 여부 없음. 병합 후: 분기 12개·금융사 규칙·preparing 응답, ROA 는 팀 결정으로 뺌. financials_fin 은 여전히 안 읽음(팀 결정) |
| 투자 기록 (blocks) | 있음·그대로 | 있음·보강 | 고정·서식·작은 제목 없음, 정렬 기준 다름, 화면 블록 모양과 다름 |
| 사용자 설정 (user_settings) | 있음·그대로 | 있음·보강 | 화면 알림 1칸 ↔ 서버 3칸, 스튜디오 알림 칸 없음, auto_audio·auto_report 매핑 없음 |

(빠른 조사에 없던 '없음' 항목: 홈 달력 API · 퀴즈 · 파일 올리기 · 분기 재무 · 소셜 계정 연결 · 알림함 표)

#### 결정 필요

| # | 무엇 | 선택지 | 나온 곳 |
|---|---|---|---|
| 1 | 약관 동의 저장 방식 | users 칸(terms_agreed_at·terms_version) / user_consents 표(항목별·버전별) / 저장 안 함 | 묶음 1 C-1 |
| 2 | '많이 찾는 종목' 출처 | 고정 목록(웹·앱 하나로 통일) / 조회 집계 | 묶음 1 C-2 · 묶음 2·3 |
| 3 | 메모 수·AI 연결 수 계산 위치 | 프론트(종목마다 board 호출) / `MyStockResponse` 칸 추가 | 묶음 1 C-4 · 묶음 2 |
| 4 | 건너뛰기 뒤 재온보딩 | 종목 0개면 매번 온보딩 / 한 번 끝나면 다시 안 띄움(서버 또는 기기에 '온보딩 끝' 저장) | 묶음 1 |
| 5 | 기기 저장 범위 | 최근 로그인 · 안내 본 상태 · 넛지 · 다크 · 최근 검색 · 보드 순서 안내 중 무엇을 기기(AsyncStorage)로, 무엇을 서버로 | 묶음 1 · 6 C-40 |
| 6 | NAVER 표기 | 종목 마스터 이름 그대로 / '네이버' 바꿔 보이기 유지 | 묶음 1 |
| 7 | AI 연결 흐름 | 저장=켜기, '일반 메모로 두기'=끄기 / 분석만 하는 엔드포인트 추가 | 묶음 2 C-11 |
| 8 | 체크리스트 종목당 개수 | 화면처럼 1개로 제한 / 여러 개 그리기 | 묶음 2 |
| 9 | '시범 종목'(ai_ready · preparing) 기준 | 서버 칸 / 시세 404 로 판단 / 고정 목록 | 묶음 2 · 3 |
| 10 | KOSDAQ 포함 | 검색·추가에 KOSDAQ 넣기 / KOSPI 만 유지 | 묶음 2 C-13 |
| 11 | 가격 소식 'away' | 백엔드가 away 를 더 안 만들기 / 화면에 away 모양 추가 | 묶음 2 |
| 12 | 메모 복사 | 같은 내용 새 메모(AI 연결 끔·켬) / 기능 빼기 | 묶음 2 |
| 13 | 업데이트 '안 읽음으로' | 기능 빼기 / 엔드포인트 추가 | 묶음 3 |
| 14 | 홈 '하루 뉴스 수' · 종 숫자 | 문구 빼기 / 칸 추가 · 종 숫자 = unread_updates 합으로 대신 | 묶음 3 |
| 15 | 스튜디오 시연 범위 | 전부 mock 유지 / 일부(보고서 등) 생성기 연결 · content 모양 · 단계 진행 표시 | 묶음 4 C-22 · C-28 |
| 16 | 플랜 단계와 가격 | 무료·PLUS·PRO(enum 추가) / free·pro 두 개 | 묶음 4 · 6 C-27 |
| 17 | 투자 기록 서식 | 목록·굵게 등 서버 저장(C-29) / 보낼 때 버리기, 웹 HTML 저장 여부, 작은 제목(sub) 처리 | 묶음 5 |
| 18 | 빈 새 기록(웹) | 첫 글자 칠 때 POST / 바로 만들고 지울 때 영구 삭제까지 | 묶음 5 |
| 19 | 투자 기록 정렬 | 고친 순(화면) / 만든 순(서버) | 묶음 5 |
| 20 | 알림 설정 매핑 | 'AI 소식' 1칸 = 서버 3칸 같이 켜고 끄기 / 화면을 3칸으로 · 스튜디오 알림 칸 추가(C-34) | 묶음 6 |
| 21 | 다크 모드 저장 위치 | 서버 `theme` / 기기 | 묶음 6 |
| 22 | 알림함 | 새 표(C-36) / 시연은 tracking_updates 를 알림처럼 | 묶음 6 |
| 23 | 받아쓰기 | 기기 키보드 음성 입력(서버 불필요) / 녹음 + STT(외부 API) | 묶음 5 |
| 24 | 옛 코드 정리 | features/ MarketWidgets·SettingsModal, store/ui `modal` 지우기 / 남기기 | 누락 표 |
| 25 | 프로필 '계정을 연결했어요' 토스트 | 빼기 / '아직 연결되지 않았어요' 안내로 | 묶음 6 |
| 26 | 기존 연결 순서 ①~④ 원문 | 저장소(docs·frontend/docs grep)에서 못 찾음 → 아래 수정안이 원문과 맞는지 확인 | 합본 |

#### 연결 순서 수정안 (기존 ①~④ 기준, 바뀐 것만)

기존 ①~④ 원문은 저장소에서 찾지 못했다(결정 필요 26). 아래는 `fe/api/index.ts` 의 단계 스위치(인증·종목 → 보드 → 전체)를 ①~④ 로 보고, 이번 검사로 **바뀐 점만** 적은 것이다.

| 단계 | 바뀐 점 |
|---|---|
| ① 인증 · 종목 | 스위치만으로 화면이 안 바뀜 → 온보딩·내 종목·사이드바 화면의 mock import 를 `useMyStocks` 등으로 바꾸는 작업 포함. 신규 판별(C-5) · 온보딩 종목 저장(POST /stocks 반복) 추가. KOSDAQ 범위(결정 10) 먼저 정하기 |
| ② 보드 · 메모 · AI 연결 | C-7(API 함수) · C-8(analysis) · AI 연결 흐름 결정(결정 7)이 **선행**. 체크리스트 1개 규칙(결정 8) |
| ③ 업데이트 · 기업정보 · 홈 | 백엔드 보강 3개(C-14 분기 재무 · C-15 금융업 여부 · C-16 지수 날짜)를 담당자와 먼저 맞춰야 화면이 mock 과 같아짐. 업데이트 피드는 ② 타임라인 변환을 같이 씀. **11/21 dev 병합 반영: 기업정보 탭은 연결 끝(C-14·C-15 포함). 남은 것은 C-16 지수 날짜와 홈·업데이트 화면** |
| ④ 투자 기록 · MY · 휴지통 | 투자 기록은 블록 변환(C-32) 선행. 휴지통은 ②·④ 삭제가 다 붙은 뒤. **스튜디오는 ④ 뒤 별도 단계**(백엔드 API 없음) |

## 연결 1단계: 주가·지수·거시 (2026-11-21)

기업정보 탭(팀원 `useCompanyInfo`)을 뺀 화면의 시세·지수·거시 칸. 틀은 기업정보와 같음: 화면마다 hook 하나 + 변환 함수 하나, `USE_MOCK=true` 면 지금처럼 mock(API 를 부르지 않음).

### 백엔드 (be/app/marketdata, 읽기 전용 SQL)

| 엔드포인트 | 무엇 | 메모 |
|---|---|---|
| GET /api/v1/quotes?codes=A,B (새) | 여러 종목 시세 한 번에 `{quotes: Quote[], missing: 코드[]}` | 최대 50개, 요청 순서, 중복 제거. 원시 종가(prices_daily)만 |
| GET /api/v1/stocks/{code}/quote (고침) | `trade_date` 추가 | 한 종목 응답 = /quotes 의 한 줄 |
| GET /api/v1/market/overview (고침, C-16) | `indices[].trade_date` · `indices[].dates`(series['1Y'] 와 같은 길이) | 원/달러는 관측일 집합이 지수와 다름 → 프론트 `alignTo` 로 지수 날짜 축에 맞춤 |
| GET /api/v1/market/macro (새) | 지표별 최신값·직전값·관측일·출처·시계열 코드 `{indicators, missing, as_of}` | economic_observations(ECOS 환율·기준금리·국고채 3·10·30년, FRED 미국채 2·10·30년·WTI) + commodity_prices_daily(KRX 금 99.99K) |

### 화면별

| 화면 · 칸 | hook · 변환 | 판정 | 메모 |
|---|---|---|---|
| 홈(웹·앱) 시장 지수 3개 · 날짜 축 · 뉴스 기준일 | ui/screens/home/useHomeMarket.ts `useHomeMarket` · `toHomeMarket` | 그대로(연결됨) | 받기 전 빈 배열, 실패하면 위젯 '불러오지 못함' |
| 앱 지수 자세히 | 〃 | 그대로(연결됨) | |
| 홈 거시 위젯 | — | 없음 | UI v2 홈에 거시 위젯이 없음(옛 features/home MarketWidgets 는 미사용) |
| 보드 탭 종목 머리(웹·앱) 가격·등락·작은 선·'MM.DD 종가 기준' | ui/screens/board/useBoardStock.ts `useBoardStock` · `toBoardStock` (useQuote · useStock · useMyStocks · fallbackLogo 재사용) | 그대로(연결됨) | 시세 없으면 `PriceNoteHead`(숫자 대신 미연결 안내). 메모·체크리스트는 아직 mock |
| 내 종목(웹·앱) 목록 · 추가 후보 가격·등락·기준일 | ui/screens/stocks/useStockPrices.ts `useStockPrices` · `withQuotes` (useQuotes) | 그대로(연결됨) | GET /quotes 한 번. 없는 종목 '—', 하나도 없으면 '시세 데이터가 아직 연결되지 않았어요'. 종목 구성·메모 수는 mock |
| 웹 사이드바 종목 | — | 해당 없음 | 가격 칸 없음 |
| 온보딩 · 앱 홈 검색 종목 | — | 해당 없음 | 가격 칸 없음 |
| 스튜디오 실험실(웹·앱) 변수 4개 '지금 값' | ui/screens/studio/useLabVars.ts `useLabVars` · `toLabVars` (useMacro) | 그대로(연결됨) | 'MM.DD 기준 …' 관측값만. 없으면 '데이터가 아직 연결되지 않았어요' |
| 메모·근거 '조건까지 ±N%' · 업데이트 가격 소식 | — | 안 됨 | 근거 카드 자체가 업데이트 피드(mock)의 과거 값. 업데이트·타임라인 연결 단계에서 |
| 스튜디오 오디오 '직전 거래일' · 주간보고서 지수 | — | 안 됨 | 생성기 없음(묶음 4) |

### 담당자 상의

- be/marketdata/service.py `profile`: market_cap 이 없으면 `close × shares` 로 계산함(역산). 원천값만 쓰려면 null 로 (기업정보 담당).
- 로컬 실행: 루트 .env 에 `AUTH_*` 가 없어 실제 백엔드의 인증 API 가 모두 500 (`AuthConfigurationError`). 실제 모드 웹 로그인 확인에는 인증 설정이 필요.
