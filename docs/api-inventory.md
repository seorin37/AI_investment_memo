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
| 보드 | MemoBoard.mock.ts `mockBoardStock` · `mockEmptyStock` | 종목 머리(이름·상태·가격·차트) | 묶음 3 (quote·candles) | — | 묶음 3 표 A 에 적음 |
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
- `fe/features/home/widgets/MarketWidgets.tsx`(macro 지표·`useCalendar`·`useNews` 사용)는 어느 화면에서도 import 되지 않는다(옛 화면, 미사용).
- DB: `0001sql prices_daily`(+`0004 trading_value`·`0011 volume`) · `0010 adjusted_prices_daily` · `0011 stock_fundamentals_snapshot`(per·pbr·eps·bps·w52·market_cap·listed_shares) · `0001sql financials`·`financials_fin`(+`0012` 금융 칸, `stocks.fin_type`) · `0016 financials_quarterly`·`financials_fin_quarterly` · `0017 financial_metrics` · `0001sql market_indices`·`economic_indicators`(source ECOS·FRED)·`economic_observations`·`commodity_prices_daily` · `0001sql market_events`(+`0004 user_id`·`kind` market·earnings·user) · `0001sql news_articles`·`news_stocks`.

#### 표 A 데이터

| 화면 | mock 출처(파일·상수/함수) | 필드 | 백엔드(파일·스키마.필드) | 판정 | 메모 |
|---|---|---|---|---|---|
| 종목 머리(보드·기업정보) | fe/ui/screens/board/MemoBoard.mock.ts `mockBoardStock` (fe/ui/shared/StockHead.types.ts) | stock_code · name · market · status | be/stocks `MyStockResponse.code` · `.name` · `.market` · `.status` | 이름만 다름(stock_code→code) | |
| 종목 머리 | 〃 | price · change · change_pct | be/marketdata/service.py `quote` → price · change · change_pct | 그대로 | 원시 종가(prices_daily) |
| 종목 머리 | 〃 | as_of ('MM.DD') | `quote.as_of` (ISO, 15:30 KST) | 계산 필요(프론트) | 'MM.DD 종가 기준' 표시 |
| 종목 머리 | 〃 | closes (작은 선) | `quote.spark` (최근 24개 종가) | 이름만 다름(→spark) | mock 은 10~16개 |
| 종목 머리 | 〃 | logo · logo_bg · logo_ink | — | 계산 필요(프론트) | 묶음 1 C-6 |
| 기업정보 | fe/ui/screens/company/CompanyInfo.mock.ts `profile()` (models.ts `StockProfile`) | code · name · market · overview · prev_close · open · high · low · volume · trading_value · per · pbr · eps · bps · market_cap · shares_outstanding · week52_low · week52_high | be/marketdata/service.py `profile` 같은 18개 키 | 그대로 | overview 없으면 '기업 개요를 준비 중이에요.' (`DEFAULT_OVERVIEW_TEXT`). market_cap·shares 는 null 가능(프론트 타입은 number) |
| 기업정보 | companyData.mock.ts `quoteSK`·`quoteKB` | div_yield · foreign_pct | — | 없음 | 화면 props(`StockProfile`)에도 없음 → 화면이 안 쓰면 무시. 확인 필요 |
| 기업정보 | CompanyInfo.mock.ts `quote_as_of` | 시세 기준 시각 | `quote.as_of` | 이름만 다름(→as_of) | |
| 기업정보 | CompanyInfo.mock.ts `candleSet` (companyData.mock.ts `candlesSK`·`candlesKB`) | 1W·1M·3M 일봉 | be/marketdata/service.py `candles` (`RANGE_SIZES` 5·22·64) | 그대로 | 기본 수정주가(`adjusted=true`, adjusted_prices_daily), `adjusted=false` 면 원시 |
| 기업정보 | 〃 | 1Y **주봉** (CompanyInfo.types.ts 주석) | `candles` 1Y = **일봉 250개** | 계산 필요(프론트) | 주 단위로 묶기. 또는 백엔드 interval 추가(담당자 상의) |
| 기업정보 | CompanyInfo.mock.ts `quarters` (CompanyInfo.types.ts `CompanyQuarter` 12개) | q · label · revenue · op · net · op_margin · net_margin · roe · roa (억원·%) | be/marketdata/service.py `financials.annual` (연간 7개: period · revenue · operating_income · net_income · operating_margin · net_margin · roe, 원 단위) | 없음 | **분기 API 없음**. DB 에는 `0016 financials_quarterly` 있음. roa 는 DB·API 모두 없음. 표 C-14 |
| 기업정보 | CompanyInfo.mock.ts `health` (`CompanyHealth`) | debt · current · quick · interest · reserve | `financials.stability.debt_ratio` · `.current_ratio` · `.quick_ratio` · `.interest_coverage` · `.reserve_ratio` | 이름만 다름(→*_ratio·interest_coverage) | financial_metrics 최신 기간 |
| 기업정보 | CompanyInfo.mock.ts `health_as_of` ('YYYY-MM-DD') | 기준 분기 말 | `financials.stability.as_of` ('YYYY-MM') · `.basis` 문장 | 계산 필요(프론트) | |
| 기업정보 | CompanyInfo.mock.ts `financial` (금융업 여부) | true·false | — (API 응답에 없음. DB `0001sql stocks.sector`='financial' · `0012 stocks.fin_type`) | 없음 | profile 응답에 sector·fin_type 추가(DB 변경 없음) → 표 C-15 |
| 기업정보(KB금융) | finKB.quarters (revenue·op null, net 만) | 금융업 실적 | `financials.annual` 은 `financials` 표만 읽음 (be/marketdata/repository.py `annual_financials`) | 확인 필요 | `financials_fin`·`financials_fin_quarterly`(순이자이익·수수료이익 등)는 API 가 읽지 않음. 금융업 화면 문구('매출 —')와 맞는지 담당자 상의 |
| 기업정보 | CompanyInfo.types.ts `preparing` (시범 종목 밖) | 준비 중 | quote·profile 404 (`PriceDataNotFoundError`·`StockNotFoundError`) | 계산 필요(프론트) | 404 → preparing |
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
| 종목 머리 | 시세 | [code].tsx · [code].native.tsx (`mockBoardStock`) | GET /stocks/{code}/quote · be/marketdata/routes.py | 그대로 | `hooks/queries.ts useQuote` 60초마다 다시 읽음 — 종가 하루 1번이라 과함(프론트에서 조절) |
| 기업정보 | 차트 기간 바꾸기 | fe/ui/screens/company/*/CompanyInfo.tsx (candles 4개 미리 받음) | GET /stocks/{code}/candles?range=1W·1M·3M·1Y&adjusted= | 그대로 | 4번 호출 or 고를 때 호출 |
| 기업정보 | 투자정보 | 〃 | GET /stocks/{code}/profile | 그대로 | |
| 기업정보 | 분기 실적 · 건전성 | 〃 | GET /stocks/{code}/financials | 확인 필요 | 건전성은 됨, 분기 표는 C-14 |
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
| C-14 분기 재무 | 엔드포인트(GET /stocks/{code}/financials 에 quarterly[] 추가 또는 새 경로) | N | DB `0016 financials_quarterly` 있음. roa 는 계산(net_income / 총자산) — 담당자 상의 |
| C-15 금융업 여부 | 엔드포인트 응답 칸(profile 에 sector·fin_type) | N | DB 칸 있음 |
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
