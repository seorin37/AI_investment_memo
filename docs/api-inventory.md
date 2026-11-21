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
| 종목 고르기 | 종목 검색 | fe/app/onboarding/pick.tsx `onQueryChange` (mock 목록 필터) | GET /stocks/search?q= · be/stocks/routes.py `search_stocks` | 그대로 | 계약상 최대 8개 |
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
