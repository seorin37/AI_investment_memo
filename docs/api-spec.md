# API 명세서

> **자동 생성 문서입니다.** 현황표의 `담당`·`비고` 칸만 손으로 고치고, 나머지는 아래 명령으로 다시 만드세요.
> 다시 만들어도 담당·비고는 (메서드, 경로)가 같은 행에서 그대로 옮겨집니다.
>
> ```bash
> # 1) worktree 에서 테스트 서버를 띄운다 (공개 서버 8010 이 아니라 8020)
> PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8020 --env-file <.env 경로>
> # 2) backend 폴더에서 생성
> python -m pipelines.devtools.api_gap --openapi-url http://127.0.0.1:8020/openapi.json --write-spec
> ```
>
> 입력: OpenAPI `http://127.0.0.1:8020/openapi.json` · 프론트 `frontend/src/api/{real,board,stocks,index,types}.ts` · `frontend/src/types/models.ts` · 라우트 소스 `backend/app/**/routes.py` · 생성기 `backend/pipelines/devtools/api_spec.py`

## 목차
1. [공통 규칙](#1-공통-규칙)
2. [현황표](#2-현황표)
3. [API별 상세](#3-api별-상세)

## 1. 공통 규칙

### 기본 주소
- 모든 API는 **`/api/v1`** 아래에 있다. 이 문서의 경로는 `/api/v1`을 뺀 나머지다 (`/stocks` = `/api/v1/stocks`).
- 웹(같은 주소 빌드, `npm run export:web:same-origin`): 상대 경로 `/api/v1`. 웹 빌드는 FastAPI가 `/api` 이외 경로에서 서빙한다.
- 앱·개발: `EXPO_PUBLIC_API_BASE_URL` (예: `https://<서버>/api/v1`, 안드로이드 에뮬레이터 `http://10.0.2.2:8000/api/v1`).

### 인증
| 클라이언트 | 로그인 | 요청 인증 | 갱신 |
|---|---|---|---|
| 웹 | `GET /auth/{provider}/start?client=web&return_to=<origin>/auth/callback` → 콜백이 쿠키를 심고 return_to 로 돌아감 | HttpOnly 쿠키 `memos_access` (15분) | `POST /auth/refresh` 본문 `{}` — 쿠키 `memos_refresh`(path `/api/v1/auth`, 14일) 사용 |
| 앱 | 같은 start 를 `client=mobile&code_challenge=` 로 열고, 받은 일회용 code 를 `POST /auth/mobile/exchange` (PKCE) | `Authorization: Bearer <access_token>` | `POST /auth/refresh` 본문 `{"refresh_token": ...}` |

- **CSRF (웹 쿠키 세션)**: POST·PUT·PATCH·DELETE 에 `memos_access`/`memos_refresh` 쿠키가 실리고 `Authorization` 헤더가 없으면, `X-CSRF-Token` 헤더가 `memos_csrf` 쿠키 값과 같아야 한다(double-submit). 다르면 `403 {"detail": "CSRF 검증에 실패했습니다."}`. 프론트 `http.ts`가 `document.cookie`에서 읽어 넣으므로 **웹은 API와 같은 주소에서 열어야 한다** (다른 주소면 쿠키를 못 읽어 403).
- `401`을 받으면 프론트(`http.ts`)가 `/auth/refresh`를 한 번 시도하고 원래 요청을 다시 보낸다.
- 인증이 필요한 API는 아래 상세의 `인증` 줄에 표시한다 (라우트가 `get_current_user`에 의존하는지로 판단).

### 에러 형식
- 모든 에러 본문은 `{"detail": "사람이 읽는 메시지"}`.
- 요청 검증 실패(422)는 FastAPI 기본 형식 `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` — 프론트는 첫 `msg`를 보여 준다.

| 코드 | 뜻 |
|---|---|
| 400 | 잘못된 요청 |
| 401 | 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) |
| 403 | 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 |
| 404 | 대상 없음 (다른 사용자 것 포함) |
| 409 | 지금 상태와 충돌 |
| 422 | 요청 검증 실패 (FastAPI 형식 detail 배열) |
| 503 | 서버 설정·의존 서비스 문제 |

### 응답 형식
- **기준은 `frontend/src/api/mock/`의 같은 함수가 돌려주는 모양과 필드 이름**이다 (타입: `frontend/src/types/models.ts`, `frontend/src/api/types.ts`의 `Api`).
- 백엔드는 그 필드를 모두 채우고, 필요하면 필드를 덧붙일 수 있다 (예: 뉴스 `summary`, AI 업데이트 `card`·`sources`). 필드를 빼거나 이름을 바꾸지 않는다.
- ID는 문자열, 시각은 ISO 8601 (`2026-11-20T09:00:00+09:00`), 날짜는 `YYYY-MM-DD`, 금액은 원 단위 숫자.
- 본문이 없는 성공은 `204 No Content` (프론트는 `undefined`로 받음).
- `상태 = mock`인 API는 백엔드가 없어서 `frontend/src/api/index.ts`의 `MOCK_ONLY` 목록으로 `USE_MOCK=false`에서도 mock 응답을 쓴다. 백엔드를 만들면 그 목록에서 함수 이름을 빼면 된다.

## 2. 현황표

상태: **구현됨** 51개 (프론트가 부르고 백엔드에 있음) · **mock** 10개 (백엔드 미구현 — frontend/src/api/index.ts MOCK_ONLY 로 USE_MOCK=false 에서도 mock 응답)

<!-- api-table:start (담당·비고 칸만 손으로 고치세요. 나머지 칸은 다시 생성하면 덮어씁니다) -->
| 영역 | 메서드 | 경로 | 프론트 함수 | 상태 | 담당 | 비고 |
|---|---|---|---|---|---|---|
| 인증 | POST | `/auth/logout` | logout (real.ts) | 구현됨 |  |  |
| 인증 | GET | `/auth/me` | me (real.ts) | 구현됨 |  |  |
| 인증 | POST | `/auth/mobile/exchange` | exchangeMobileAuth (real.ts) | 구현됨 |  |  |
| 인증 | POST | `/auth/refresh` | refreshAuth (real.ts) | 구현됨 |  |  |
| 인증 | GET | `/auth/{provider}/callback` |  | 백엔드만 있음 |  |  |
| 인증 | GET | `/auth/{provider}/start` |  | 백엔드만 있음 |  |  |
| 계정·설정 | GET | `/home/layout` | getHomeLayout (real.ts) | 구현됨 |  |  |
| 계정·설정 | PUT | `/home/layout` | saveHomeLayout (real.ts) | 구현됨 |  |  |
| 계정·설정 | GET | `/me` |  | 백엔드만 있음 |  |  |
| 계정·설정 | PATCH | `/me` | updateMe (real.ts) | 구현됨 |  |  |
| 계정·설정 | GET | `/settings` | getSettings (real.ts) | 구현됨 |  |  |
| 계정·설정 | PATCH | `/settings` | updateSettings (real.ts) | 구현됨 |  |  |
| 종목 | GET | `/stocks` | listMyStocks (stocks.ts) | 구현됨 |  |  |
| 종목 | POST | `/stocks` | addStock (stocks.ts) | 구현됨 |  |  |
| 종목 | PUT | `/stocks/order` |  | 백엔드만 있음 | 이민성 | 사이드바 내 종목 전체 순서 저장 (0021 user_stocks.position). 프론트 미연결: 웹 stocks[].order 대신 호출 필요 |
| 종목 | GET | `/stocks/search` | searchStocks (stocks.ts) | 구현됨 |  |  |
| 종목 | DELETE | `/stocks/{code}` | removeStock (stocks.ts) | 구현됨 |  |  |
| 종목 | GET | `/stocks/{code}` | getStock (stocks.ts) | 구현됨 |  |  |
| 종목 | PATCH | `/stocks/{code}` | updateStock (stocks.ts) | 구현됨 |  |  |
| 시세·뉴스·기업 | GET | `/market/overview` | getMarketOverview (real.ts) | 구현됨 |  |  |
| 시세·뉴스·기업 | GET | `/news/headlines` | listNews (real.ts) | 구현됨 |  |  |
| 시세·뉴스·기업 | GET | `/stocks/{code}/candles` | getCandles (real.ts) | 구현됨 |  |  |
| 시세·뉴스·기업 | GET | `/stocks/{code}/financials` | getFinancials (real.ts) | 구현됨 | 이민성 | 11-21 UI v2 모양: 분기 12개(억원)·건전성 5개·financial·preparing. 금융사 매출·이익률·유동·당좌·이자보상 null, 영업이익은 보냄. 우선주는 본주 재무 |
| 시세·뉴스·기업 | GET | `/stocks/{code}/profile` | getProfile (real.ts) | 구현됨 |  |  |
| 시세·뉴스·기업 | GET | `/stocks/{code}/quote` | getQuote (real.ts) | 구현됨 |  |  |
| 메모 보드 | DELETE | `/board-items/{memo_id}` | deleteBoardItem (board.ts) | 구현됨 |  |  |
| 메모 보드 | GET | `/board-items/{memo_id}` | getBoardItem (board.ts) | 구현됨 |  |  |
| 메모 보드 | PATCH | `/board-items/{memo_id}` | updateBoardItem (board.ts) | 구현됨 |  |  |
| 메모 보드 | PATCH | `/checklists/{memo_id}/items/{item_id}` | setBoardChecklistItem (board.ts) | 구현됨 |  |  |
| 메모 보드 | GET | `/memos/pinned` | listPinnedMemos (real.ts) | 구현됨 |  |  |
| 메모 보드 | POST | `/memos/{memoId}/conclude` | concludeMemo (real.ts) | mock |  |  |
| 메모 보드 | PUT | `/memos/{memo_id}/ai-link` | setAiLink (board.ts) | 구현됨 |  |  |
| 메모 보드 | GET | `/memos/{memo_id}/answers` |  | 백엔드만 있음 | 이민성 | 메모 질문 답 목록: pending·answered·no_answer + 답 본문·출처. 프론트 미연결 |
| 메모 보드 | POST | `/memos/{memo_id}/confirmations` |  | 백엔드만 있음 |  |  |
| 메모 보드 | GET | `/stocks/{code}/board` | listBoard (board.ts) | 구현됨 |  |  |
| 메모 보드 | PUT | `/stocks/{code}/board-order` |  | 백엔드만 있음 | 이민성 | 보드 카드 전체 순서 저장 (#48). 프론트 미연결: 웹 boards[code]·앱 끌기 화면에서 호출 필요 |
| 메모 보드 | POST | `/stocks/{code}/checklists` | createChecklist (board.ts) | 구현됨 |  |  |
| 메모 보드 | POST | `/stocks/{code}/memos` | createMemo (board.ts) | 구현됨 |  |  |
| 메모 보드 | POST | `/stocks/{code}/references` | createReference (board.ts) | 구현됨 |  |  |
| AI 업데이트 | GET | `/ai-updates/summary` | listMemoUpdateSummary (real.ts) | 구현됨 |  |  |
| AI 업데이트 | POST | `/ai-updates/{update_id}/read` | markAiUpdateRead (real.ts) | 구현됨 |  |  |
| AI 업데이트 | GET | `/memos/{memo_id}/timeline` | getMemoTimeline (real.ts) | 구현됨 |  |  |
| AI 업데이트 | GET | `/stocks/{code}/ai-updates` | listStockAiUpdates (real.ts) | 구현됨 |  |  |
| AI 업데이트 | GET | `/updates` | listUpdates (real.ts) | 구현됨 |  |  |
| 홈 위젯 | GET | `/checklist-items` | listHomeChecklist (real.ts) | 구현됨 |  |  |
| 홈 위젯 | POST | `/checklist-items` | addChecklistItem (real.ts) | 구현됨 |  |  |
| 홈 위젯 | PATCH | `/memos/{memo_id}/price-conditions/{condition_id}` | setPriceConditionTracking (real.ts) | 구현됨 |  |  |
| 홈 위젯 | GET | `/price-conditions` | listPriceConditions (real.ts) | 구현됨 |  |  |
| 휴지통 | GET | `/trash` | listTrash (real.ts) | 구현됨 |  |  |
| 휴지통 | DELETE | `/trash/{trash_id}` | purgeTrash (real.ts) | 구현됨 |  |  |
| 휴지통 | POST | `/trash/{trash_id}/restore` | restoreTrash (real.ts) | 구현됨 |  |  |
| 크레딧 | GET | `/me/usage` | getUsage (real.ts) | 구현됨 | 이민성 | 크레딧 사용량 (#49). 이번 달 기본량을 안 받았으면 이 호출에서 지급 |
| 투자 기록 | GET | `/journal` | listJournal (real.ts) | 구현됨 |  |  |
| 투자 기록 | POST | `/journal` | createJournal (real.ts) | 구현됨 |  |  |
| 투자 기록 | DELETE | `/journal/{entry_id}` | deleteJournal (real.ts) | 구현됨 |  |  |
| 투자 기록 | PATCH | `/journal/{entry_id}` | updateJournal (real.ts) | 구현됨 |  |  |
| 캘린더 | GET | `/calendar` | listCalendar (real.ts) | mock |  |  |
| 캘린더 | POST | `/calendar` | createCalendarEvent (real.ts) | mock |  |  |
| 인사이트 | GET | `/insights/compare-memos` | listCompareMemos (real.ts) | mock |  |  |
| 인사이트 | GET | `/insights/conclude-candidates` | listConcludeCandidates (real.ts) | mock |  |  |
| 인사이트 | GET | `/insights/memo-backtest` | listMemoBacktests (real.ts) | mock |  |  |
| AI 통계 | GET | `/ai/stats` | getAiStats (real.ts) | 구현됨 | 이민성 | AI 연결 메모·이번 달 AI 소식·연결 종목 수 |
| 데이터 | DELETE | `/data` | deleteAllData (real.ts) | mock |  |  |
| 데이터 | POST | `/data/export` | exportData (real.ts) | mock |  |  |
| 데이터 | GET | `/data/stats` | getDataStats (real.ts) | 구현됨 | 이민성 | 메모(note)·투자 기록·종목 수, 지운 것 제외 |
| 피드백 | POST | `/feedback` | sendFeedback (real.ts) | 구현됨 | 이민성 | feedbacks 테이블. 평점 1~5, 빈 내용 422 |
| MCP | DELETE | `/mcp/apps/{appId}` | disconnectMcpApp (real.ts) | mock |  |  |
| 파일 | POST | `/files` | uploadFile (real.ts) | mock |  |  |
<!-- api-table:end -->

## 3. API별 상세

### 인증

<a id="post--auth-logout"></a>
#### `POST /auth/logout`

- 상태: **구현됨**
- 인증: 불필요 · 구현: `backend/app/auth/routes.py` `logout`
- 프론트: `logout(refreshToken?: string): Promise<void>`
  - 호출: real.ts:21 `logout: (refreshToken) => http.post('/auth/logout', refreshToken ? { refresh_token: refreshToken } : undefined),`

**요청 본문** `RefreshRequest | null`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `refresh_token` | `string \| null` |  |  |

**응답** `204` 본문 없음

**에러**: `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--auth-me"></a>
#### `GET /auth/me`

- 상태: **구현됨**
- 프론트: `me(): Promise<User>`
  - 호출: real.ts:19 `me: () => http.get('/auth/me'),`

**응답** `200`

프론트 타입 (mock 기준) `User`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `name` | `string` | 예 |
| `bio` | `string` | 예 |
| `avatar_url` | `string \| null` | 예 |
| `email` | `string \| null` | 예 |
| `providers` | `{ provider: AuthProvider; email: string \| null; connected: boolean; current: boolean }[]` | 예 |

<details><summary>예시</summary>

```json
{
  "id": "string",
  "name": "string",
  "bio": "string",
  "avatar_url": "string",
  "email": "string",
  "providers": [
    {
      "provider": "kakao",
      "email": "string",
      "connected": false,
      "current": false
    }
  ]
}
```

</details>

<a id="post--auth-mobile-exchange"></a>
#### `POST /auth/mobile/exchange`

- 상태: **구현됨**
- 인증: 불필요 · 구현: `backend/app/auth/routes.py` `mobile_exchange`
- 프론트: `exchangeMobileAuth(code: string, codeVerifier: string): Promise<AuthToken>`
  - 호출: real.ts:18 `http.post('/auth/mobile/exchange', { code, code_verifier: codeVerifier }),`

**요청 본문** `MobileExchangeRequest` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `code` | `string` | 예 | 최소 길이 20, 최대 길이 256 |
| `code_verifier` | `string` | 예 | 최소 길이 43, 최대 길이 128 |

**응답** `200`

OpenAPI 응답 스키마 `TokenResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `access_token` | `string \| null` | 예 |  |
| `refresh_token` | `string \| null` |  |  |
| `token_type` | `string` |  | 기본 `"bearer"` |
| `expires_in` | `integer` | 예 |  |
| `user` | `object` | 예 |  |

프론트 타입 (mock 기준) `AuthToken`

| 필드 | 타입 | 필수 |
|---|---|---|
| `access_token` | `string \| null` | 예 |
| `refresh_token` | `string \| null` |  |
| `token_type` | `'bearer'` | 예 |
| `expires_in` | `number` | 예 |
| `user` | `User` | 예 |

<details><summary>예시</summary>

```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "expires_in": 0,
  "user": {
    "id": "string",
    "name": "string",
    "bio": "string",
    "avatar_url": "string",
    "email": "string",
    "providers": [
      {
        "provider": "…",
        "email": "…",
        "connected": "…",
        "current": "…"
      }
    ]
  }
}
```

</details>

**에러**: `422` 요청 검증 실패 (FastAPI 형식 detail 배열) · `503` 서버 설정·의존 서비스 문제

<a id="post--auth-refresh"></a>
#### `POST /auth/refresh`

- 상태: **구현됨**
- 인증: 불필요 · 구현: `backend/app/auth/routes.py` `refresh`
- 프론트: `refreshAuth(refreshToken?: string): Promise<AuthToken>`
  - 호출: real.ts:16 `refreshAuth: (refreshToken) => http.post('/auth/refresh', { refresh_token: refreshToken }),`

**요청 본문** `RefreshRequest` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `refresh_token` | `string \| null` |  |  |

**응답** `200`

OpenAPI 응답 스키마 `TokenResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `access_token` | `string \| null` | 예 |  |
| `refresh_token` | `string \| null` |  |  |
| `token_type` | `string` |  | 기본 `"bearer"` |
| `expires_in` | `integer` | 예 |  |
| `user` | `object` | 예 |  |

프론트 타입 (mock 기준) `AuthToken`

| 필드 | 타입 | 필수 |
|---|---|---|
| `access_token` | `string \| null` | 예 |
| `refresh_token` | `string \| null` |  |
| `token_type` | `'bearer'` | 예 |
| `expires_in` | `number` | 예 |
| `user` | `User` | 예 |

<details><summary>예시</summary>

```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "expires_in": 0,
  "user": {
    "id": "string",
    "name": "string",
    "bio": "string",
    "avatar_url": "string",
    "email": "string",
    "providers": [
      {
        "provider": "…",
        "email": "…",
        "connected": "…",
        "current": "…"
      }
    ]
  }
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열) · `503` 서버 설정·의존 서비스 문제

<a id="get--auth-provider-callback"></a>
#### `GET /auth/{provider}/callback`

- 상태: **백엔드만 있음**
- 인증: 불필요 · 구현: `backend/app/auth/routes.py` `oauth_callback`

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `provider` | 경로 | `string` | 예 |  |
| `state` | 쿼리 | `string` |  | 기본 `""` |
| `code` | 쿼리 | `string` |  | 기본 `""` |
| `error` | 쿼리 | `string \| null` |  |  |

**응답** `200`

**에러**: `422` 요청 검증 실패 (FastAPI 형식 detail 배열) · `503` 서버 설정·의존 서비스 문제

<a id="get--auth-provider-start"></a>
#### `GET /auth/{provider}/start`

- 상태: **백엔드만 있음**
- 인증: 불필요 · 구현: `backend/app/auth/routes.py` `start_oauth`

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `provider` | 경로 | `string` | 예 |  |
| `client` | 쿼리 | `string` | 예 | 형식 `^(web\|mobile)$` |
| `return_to` | 쿼리 | `string` | 예 |  |
| `code_challenge` | 쿼리 | `string \| null` |  |  |

**응답** `200`

**에러**: `422` 요청 검증 실패 (FastAPI 형식 detail 배열) · `503` 서버 설정·의존 서비스 문제

### 계정·설정

<a id="get--home-layout"></a>
#### `GET /home/layout`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/account/routes.py` `get_home_layout`
- 프론트: `getHomeLayout(): Promise<HomeLayout>`
  - 호출: real.ts:52 `getHomeLayout: () => http.get('/home/layout'),`

**응답** `200`

프론트 타입 (mock 기준) `HomeLayout`

| 필드 | 타입 | 필수 |
|---|---|---|
| `mode` | `'unset' \| 'template' \| 'custom'` | 예 |
| `widgets` | `WidgetInstance[]` | 예 |

<details><summary>예시</summary>

```json
{
  "mode": "unset",
  "widgets": [
    {
      "id": "string",
      "type": "market",
      "span": 1
    }
  ]
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

<a id="put--home-layout"></a>
#### `PUT /home/layout`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/account/routes.py` `save_home_layout`
- 프론트: `saveHomeLayout(layout: HomeLayout): Promise<HomeLayout>`
  - 호출: real.ts:53 `saveHomeLayout: (layout) => http.put('/home/layout', layout),`

**요청 본문** `HomeLayout` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `mode` | `"unset" \| "template" \| "custom"` | 예 |  |
| `widgets` | `WidgetInstance[]` | 예 | 최대 개수 40 |
| `widgets.id` | `string` | 예 | 최소 길이 1, 최대 길이 64 |
| `widgets.type` | `"market" \| "updates" \| "calendar" \| "news" \| "pinned_memos" \| "checklist" \| "quick_memo" \| "price_conditions" \| "recent_journal" \| "memo_updates" \| "memo_backtest" \| "compare_memo" \| "conclude_memo"` | 예 |  |
| `widgets.span` | `1 \| 2 \| 3 \| 4` | 예 |  |

**응답** `200`

프론트 타입 (mock 기준) `HomeLayout`

| 필드 | 타입 | 필수 |
|---|---|---|
| `mode` | `'unset' \| 'template' \| 'custom'` | 예 |
| `widgets` | `WidgetInstance[]` | 예 |

<details><summary>예시</summary>

```json
{
  "mode": "unset",
  "widgets": [
    {
      "id": "string",
      "type": "market",
      "span": 1
    }
  ]
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--me"></a>
#### `GET /me`

- 상태: **백엔드만 있음**
- 인증: 필요 · 구현: `backend/app/account/routes.py` `get_me`

**응답** `200`

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `404` 대상 없음 (다른 사용자 것 포함)

<a id="patch--me"></a>
#### `PATCH /me`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/account/routes.py` `update_me`
- 프론트: `updateMe(patch: Partial<Pick<User, 'name' | 'bio'>>): Promise<User>`
  - 호출: real.ts:20 `updateMe: (patch) => http.patch('/me', patch),`

**요청 본문** `ProfilePatch` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `name` | `string \| null` |  | 최대 길이 40 |
| `bio` | `string \| null` |  | 최대 길이 100 |

**응답** `200`

프론트 타입 (mock 기준) `User`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `name` | `string` | 예 |
| `bio` | `string` | 예 |
| `avatar_url` | `string \| null` | 예 |
| `email` | `string \| null` | 예 |
| `providers` | `{ provider: AuthProvider; email: string \| null; connected: boolean; current: boolean }[]` | 예 |

<details><summary>예시</summary>

```json
{
  "id": "string",
  "name": "string",
  "bio": "string",
  "avatar_url": "string",
  "email": "string",
  "providers": [
    {
      "provider": "kakao",
      "email": "string",
      "connected": false,
      "current": false
    }
  ]
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--settings"></a>
#### `GET /settings`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/account/routes.py` `get_settings`
- 프론트: `getSettings(): Promise<Settings>`
  - 호출: real.ts:76 `getSettings: () => http.get('/settings'),`

**응답** `200`

프론트 타입 (mock 기준) `Settings`

| 필드 | 타입 | 필수 |
|---|---|---|
| `theme` | `ThemePref` | 예 |
| `language` | `'ko'` | 예 |
| `updown_color` | `UpDownColor` | 예 |
| `notifications` | `{ disclosure: boolean; news: boolean; price_condition: boolean; price_spike: boolean; price_spike_threshold: 3 \| 5 \| 10; channels: { in_app: boolean; email: boolean; push: boolean }; frequency: 'realtime' \| 'hourly' \| 'daily'; quiet_hours: { enabled: boolean; from: string; to: string }; }` | 예 |
| `ai` | `{ default_link_new_memo: boolean; sources: { disclosure: boolean; news: boolean; price: boolean }; sensitivity: 'strict' \| 'balanced' \| 'broad'; }` | 예 |
| `mcp` | `{ enabled: boolean; server_url: string; scopes: { memo: boolean; journal: boolean; stock: boolean }; access: 'read' \| 'read_write'; only_ai_linked: boolean; apps: { id: string; name: string; access: 'read' \| 'read_write'; last_used_at: ISODate }[]; }` | 예 |

<details><summary>예시</summary>

```json
{
  "theme": "system",
  "language": "ko",
  "updown_color": "red_up",
  "notifications": {
    "disclosure": false,
    "news": false,
    "price_condition": false,
    "price_spike": false,
    "price_spike_threshold": 3,
    "channels": {
      "in_app": false,
      "email": false,
      "push": false
    },
    "frequency": "realtime",
    "quiet_hours": {
      "enabled": false,
      "from": "string",
      "to": "string"
    }
  },
  "ai": {
    "default_link_new_memo": false,
    "sources": {
      "disclosure": false,
      "news": false,
      "price": false
    },
    "sensitivity": "strict"
  },
  "mcp": {
    "enabled": false,
    "server_url": "string",
    "scopes": {
      "memo": false,
      "journal": false,
      "stock": false
    },
    "access": "read",
    "only_ai_linked": false,
    "apps": [
      {
        "id": "…",
        "name": "…",
        "access": "…",
        "last_used_at": "…"
      }
    ]
  }
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

<a id="patch--settings"></a>
#### `PATCH /settings`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/account/routes.py` `update_settings`
- 프론트: `updateSettings(patch: DeepPartial<Settings>): Promise<Settings>`
  - 호출: real.ts:77 `updateSettings: (patch) => http.patch('/settings', patch),`

**요청 본문** `SettingsPatch` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `theme` | `"system" \| "light" \| "dark" \| null` |  |  |
| `language` | `"ko" \| null` |  |  |
| `updown_color` | `"red_up" \| "green_up" \| null` |  |  |
| `notifications` | `NotificationsPatch \| null` |  |  |
| `notifications.disclosure` | `boolean \| null` |  |  |
| `notifications.news` | `boolean \| null` |  |  |
| `notifications.price_condition` | `boolean \| null` |  |  |
| `notifications.price_spike` | `boolean \| null` |  |  |
| `notifications.price_spike_threshold` | `3 \| 5 \| 10 \| null` |  |  |
| `notifications.channels` | `ChannelsPatch \| null` |  |  |
| `notifications.channels.in_app` | `boolean \| null` |  |  |
| `notifications.channels.email` | `boolean \| null` |  |  |
| `notifications.channels.push` | `boolean \| null` |  |  |
| `notifications.frequency` | `"realtime" \| "hourly" \| "daily" \| null` |  |  |
| `notifications.quiet_hours` | `QuietHoursPatch \| null` |  |  |
| `notifications.quiet_hours.enabled` | `boolean \| null` |  |  |
| `notifications.quiet_hours.from` | `string \| null` |  |  |
| `notifications.quiet_hours.to` | `string \| null` |  |  |
| `ai` | `AiPatch \| null` |  |  |
| `ai.default_link_new_memo` | `boolean \| null` |  |  |
| `ai.sources` | `AiSourcesPatch \| null` |  |  |
| `ai.sources.disclosure` | `boolean \| null` |  |  |
| `ai.sources.news` | `boolean \| null` |  |  |
| `ai.sources.price` | `boolean \| null` |  |  |
| `ai.sensitivity` | `"strict" \| "balanced" \| "broad" \| null` |  |  |
| `mcp` | `McpPatch \| null` |  |  |
| `mcp.enabled` | `boolean \| null` |  |  |
| `mcp.scopes` | `McpScopesPatch \| null` |  |  |
| `mcp.scopes.memo` | `boolean \| null` |  |  |
| `mcp.scopes.journal` | `boolean \| null` |  |  |
| `mcp.scopes.stock` | `boolean \| null` |  |  |
| `mcp.access` | `"read" \| "read_write" \| null` |  |  |
| `mcp.only_ai_linked` | `boolean \| null` |  |  |

**응답** `200`

프론트 타입 (mock 기준) `Settings`

| 필드 | 타입 | 필수 |
|---|---|---|
| `theme` | `ThemePref` | 예 |
| `language` | `'ko'` | 예 |
| `updown_color` | `UpDownColor` | 예 |
| `notifications` | `{ disclosure: boolean; news: boolean; price_condition: boolean; price_spike: boolean; price_spike_threshold: 3 \| 5 \| 10; channels: { in_app: boolean; email: boolean; push: boolean }; frequency: 'realtime' \| 'hourly' \| 'daily'; quiet_hours: { enabled: boolean; from: string; to: string }; }` | 예 |
| `ai` | `{ default_link_new_memo: boolean; sources: { disclosure: boolean; news: boolean; price: boolean }; sensitivity: 'strict' \| 'balanced' \| 'broad'; }` | 예 |
| `mcp` | `{ enabled: boolean; server_url: string; scopes: { memo: boolean; journal: boolean; stock: boolean }; access: 'read' \| 'read_write'; only_ai_linked: boolean; apps: { id: string; name: string; access: 'read' \| 'read_write'; last_used_at: ISODate }[]; }` | 예 |

<details><summary>예시</summary>

```json
{
  "theme": "system",
  "language": "ko",
  "updown_color": "red_up",
  "notifications": {
    "disclosure": false,
    "news": false,
    "price_condition": false,
    "price_spike": false,
    "price_spike_threshold": 3,
    "channels": {
      "in_app": false,
      "email": false,
      "push": false
    },
    "frequency": "realtime",
    "quiet_hours": {
      "enabled": false,
      "from": "string",
      "to": "string"
    }
  },
  "ai": {
    "default_link_new_memo": false,
    "sources": {
      "disclosure": false,
      "news": false,
      "price": false
    },
    "sensitivity": "strict"
  },
  "mcp": {
    "enabled": false,
    "server_url": "string",
    "scopes": {
      "memo": false,
      "journal": false,
      "stock": false
    },
    "access": "read",
    "only_ai_linked": false,
    "apps": [
      {
        "id": "…",
        "name": "…",
        "access": "…",
        "last_used_at": "…"
      }
    ]
  }
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

### 종목

<a id="get--stocks"></a>
#### `GET /stocks`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/stocks/routes.py` `list_my_stocks`
- 프론트: `listMyStocks(): Promise<MyStock[]>`
  - 호출: stocks.ts:36 `return (await http.get<MyStockWire[]>('/stocks')).map(mine);`

**응답** `200`

OpenAPI 응답 스키마 `MyStockResponse[]`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `code` | `string` | 예 |  |
| `name` | `string` | 예 |  |
| `market` | `"KOSPI" \| "KOSDAQ" \| "KONEX"` | 예 |  |
| `status` | `"holding" \| "watching"` | 예 |  |
| `tags` | `string[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `added_at` | `string(date-time)` | 예 |  |
| `position` | `integer` |  | 기본 `0` |

프론트 타입 (mock 기준) `MyStock[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `code` | `string` | 예 |
| `name` | `string` | 예 |
| `market` | `Market` | 예 |
| `status` | `StockStatus` | 예 |
| `tags` | `string[]` | 예 |
| `unread_updates` | `number` | 예 |
| `added_at` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "code": "string",
    "name": "string",
    "market": "KOSPI",
    "status": "holding",
    "tags": [
      "string"
    ],
    "unread_updates": 0,
    "added_at": "2026-11-20T09:00:00+09:00"
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

<a id="post--stocks"></a>
#### `POST /stocks`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/stocks/routes.py` `add_stock`
- 프론트: `addStock(code: string, status: StockStatus): Promise<MyStock>`
  - 호출: stocks.ts:45 `return mine(await http.post<MyStockWire>('/stocks', { code, status }));`

**요청 본문** `StockCreateRequest` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `code` | `string` | 예 | 최소 길이 6, 최대 길이 6, 형식 `^[0-9A-Z]{6}$` |
| `status` | `"holding" \| "watching"` | 예 |  |

**응답** `200`

OpenAPI 응답 스키마 `MyStockResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `code` | `string` | 예 |  |
| `name` | `string` | 예 |  |
| `market` | `"KOSPI" \| "KOSDAQ" \| "KONEX"` | 예 |  |
| `status` | `"holding" \| "watching"` | 예 |  |
| `tags` | `string[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `added_at` | `string(date-time)` | 예 |  |
| `position` | `integer` |  | 기본 `0` |

프론트 타입 (mock 기준) `MyStock`

| 필드 | 타입 | 필수 |
|---|---|---|
| `code` | `string` | 예 |
| `name` | `string` | 예 |
| `market` | `Market` | 예 |
| `status` | `StockStatus` | 예 |
| `tags` | `string[]` | 예 |
| `unread_updates` | `number` | 예 |
| `added_at` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
{
  "code": "string",
  "name": "string",
  "market": "KOSPI",
  "status": "holding",
  "tags": [
    "string"
  ],
  "unread_updates": 0,
  "added_at": "2026-11-20T09:00:00+09:00"
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="put--stocks-order"></a>
#### `PUT /stocks/order`

사이드바에서 끌어 옮긴 뒤 내 종목 전체 순서를 저장하고, 새 순서의 목록을 돌려준다 (0021).

- 상태: **백엔드만 있음** · 담당: 이민성
- 인증: 필요 · 구현: `backend/app/stocks/routes.py` `put_stock_order`

**요청 본문** `StockOrderRequest` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `codes` | `string[]` | 예 | 최대 개수 500 |

**응답** `200`

OpenAPI 응답 스키마 `MyStockResponse[]`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `code` | `string` | 예 |  |
| `name` | `string` | 예 |  |
| `market` | `"KOSPI" \| "KOSDAQ" \| "KONEX"` | 예 |  |
| `status` | `"holding" \| "watching"` | 예 |  |
| `tags` | `string[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `added_at` | `string(date-time)` | 예 |  |
| `position` | `integer` |  | 기본 `0` |

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--stocks-search"></a>
#### `GET /stocks/search`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/stocks/routes.py` `search_stocks`
- 프론트: `searchStocks(q: string): Promise<StockMaster[]>`
  - 호출: stocks.ts:39 `return (await http.get<StockMasterWire[]>('/stocks/search', { q })).map(master);`

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `q` | 쿼리 | `string` | 예 | 최소 길이 1, 최대 길이 80 |

**응답** `200`

OpenAPI 응답 스키마 `StockMasterResponse[]`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `code` | `string` | 예 |  |
| `name` | `string` | 예 |  |
| `market` | `"KOSPI" \| "KOSDAQ" \| "KONEX"` | 예 |  |

프론트 타입 (mock 기준) `StockMaster[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `code` | `string` | 예 |
| `name` | `string` | 예 |
| `market` | `Market` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "code": "string",
    "name": "string",
    "market": "KOSPI"
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="delete--stocks-code"></a>
#### `DELETE /stocks/{code}`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/stocks/routes.py` `delete_stock`
- 프론트: `removeStock(code: string): Promise<void>`
  - 호출: stocks.ts:54 `` return http.del(`/stocks/${code}`); ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 |  |

**응답** `204` 본문 없음

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--stocks-code"></a>
#### `GET /stocks/{code}`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/stocks/routes.py` `get_stock`
- 프론트: `getStock(code: string): Promise<StockMaster>`
  - 호출: stocks.ts:42 `` return master(await http.get<StockMasterWire>(`/stocks/${code}`)); ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 |  |

**응답** `200`

OpenAPI 응답 스키마 `StockMasterResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `code` | `string` | 예 |  |
| `name` | `string` | 예 |  |
| `market` | `"KOSPI" \| "KOSDAQ" \| "KONEX"` | 예 |  |

프론트 타입 (mock 기준) `StockMaster`

| 필드 | 타입 | 필수 |
|---|---|---|
| `code` | `string` | 예 |
| `name` | `string` | 예 |
| `market` | `Market` | 예 |

<details><summary>예시</summary>

```json
{
  "code": "string",
  "name": "string",
  "market": "KOSPI"
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="patch--stocks-code"></a>
#### `PATCH /stocks/{code}`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/stocks/routes.py` `update_stock`
- 프론트: `updateStock(code: string, patch: Partial<Pick<MyStock, 'status' | 'tags'>>): Promise<MyStock>`
  - 호출: stocks.ts:51 `` return mine(await http.patch<MyStockWire>(`/stocks/${code}`, patch)); ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 |  |

**요청 본문** `StockUpdateRequest` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `status` | `"holding" \| "watching" \| null` |  |  |
| `tags` | `string[] \| null` |  |  |

**응답** `200`

OpenAPI 응답 스키마 `MyStockResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `code` | `string` | 예 |  |
| `name` | `string` | 예 |  |
| `market` | `"KOSPI" \| "KOSDAQ" \| "KONEX"` | 예 |  |
| `status` | `"holding" \| "watching"` | 예 |  |
| `tags` | `string[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `added_at` | `string(date-time)` | 예 |  |
| `position` | `integer` |  | 기본 `0` |

프론트 타입 (mock 기준) `MyStock`

| 필드 | 타입 | 필수 |
|---|---|---|
| `code` | `string` | 예 |
| `name` | `string` | 예 |
| `market` | `Market` | 예 |
| `status` | `StockStatus` | 예 |
| `tags` | `string[]` | 예 |
| `unread_updates` | `number` | 예 |
| `added_at` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
{
  "code": "string",
  "name": "string",
  "market": "KOSPI",
  "status": "holding",
  "tags": [
    "string"
  ],
  "unread_updates": 0,
  "added_at": "2026-11-20T09:00:00+09:00"
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

### 시세·뉴스·기업

<a id="get--market-overview"></a>
#### `GET /market/overview`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/marketdata/routes.py` `get_market_overview`
- 프론트: `getMarketOverview(): Promise<MarketOverview>`
  - 호출: real.ts:54 `getMarketOverview: () => http.get('/market/overview'),`

**응답** `200`

프론트 타입 (mock 기준) `MarketOverview`

| 필드 | 타입 | 필수 |
|---|---|---|
| `indices` | `MarketIndex[]` | 예 |
| `macro` | `MacroItem[]` | 예 |
| `as_of` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
{
  "indices": [
    {
      "key": "KOSPI",
      "label": "string",
      "flag": "kr",
      "value": 0,
      "change": 0,
      "change_pct": 0,
      "series": {
        "…": "…"
      }
    }
  ],
  "macro": [
    {
      "key": "string",
      "label": "string",
      "value": 0,
      "unit": "string",
      "change": 0
    }
  ],
  "as_of": "2026-11-20T09:00:00+09:00"
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

<a id="get--news-headlines"></a>
#### `GET /news/headlines`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/marketdata/routes.py` `list_headlines`
- 프론트: `listNews(): Promise<NewsHeadline[]>`
  - 호출: real.ts:57 `listNews: () => http.get('/news/headlines'),`

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `limit` | 쿼리 | `integer` |  | ≥ 1, ≤ 50, 기본 `20` |

**응답** `200`

프론트 타입 (mock 기준) `NewsHeadline[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `title` | `string` | 예 |
| `source` | `NewsSource` | 예 |
| `url` | `string` | 예 |
| `published_at` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "id": "string",
    "title": "string",
    "source": "매일경제",
    "url": "string",
    "published_at": "2026-11-20T09:00:00+09:00"
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--stocks-code-candles"></a>
#### `GET /stocks/{code}/candles`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/marketdata/routes.py` `get_candles`
- 프론트: `getCandles(code: string, range: ChartRange): Promise<Candle[]>`
  - 호출: real.ts:26 `` getCandles: (code, range) => http.get(`/stocks/${code}/candles`, { range }), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 | 형식 `^[0-9A-Z]{6}$` |
| `range` | 쿼리 | `"1W" \| "1M" \| "3M" \| "1Y"` |  | 기본 `"3M"` |
| `adjusted` | 쿼리 | `boolean` |  | true: 수정주가(기본), false: 원시 주가 기본 `true` |

**응답** `200`

프론트 타입 (mock 기준) `Candle[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `date` | `string` | 예 |
| `open` | `number` | 예 |
| `high` | `number` | 예 |
| `low` | `number` | 예 |
| `close` | `number` | 예 |
| `volume` | `number` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "date": "string",
    "open": 0,
    "high": 0,
    "low": 0,
    "close": 0,
    "volume": 0
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--stocks-code-financials"></a>
#### `GET /stocks/{code}/financials`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/marketdata/routes.py` `get_financials`
- 프론트: `getFinancials(code: string): Promise<Financials>`
  - 호출: real.ts:28 `` getFinancials: (code) => http.get(`/stocks/${code}/financials`), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 | 형식 `^[0-9A-Z]{6}$` |

**응답** `200`

프론트 타입 (mock 기준) `Financials`

| 필드 | 타입 | 필수 |
|---|---|---|
| `code` | `string` | 예 |
| `source_code` | `string` | 예 |
| `sector` | `'general' \| 'financial'` | 예 |
| `fin_type` | `string \| null` | 예 |
| `financial` | `boolean` | 예 |
| `preparing` | `boolean` | 예 |
| `basis` | `string` | 예 |
| `quarters` | `FinancialQuarter[]` | 예 |
| `health` | `FinancialHealth` | 예 |
| `health_as_of` | `string \| null` | 예 |
| `interest_coverage_basis` | `string \| null` | 예 |

<details><summary>예시</summary>

```json
{
  "code": "string",
  "source_code": "string",
  "sector": "general",
  "fin_type": "string",
  "financial": false,
  "preparing": false,
  "basis": "string",
  "quarters": [
    {
      "period_end": "string",
      "q": "string",
      "label": "string",
      "revenue": 0,
      "op": 0,
      "net": 0,
      "op_margin": 0,
      "net_margin": 0,
      "roe": 0
    }
  ],
  "health": {
    "debt": 0,
    "current": 0,
    "quick": 0,
    "interest": 0,
    "reserve": 0
  },
  "health_as_of": "string",
  "interest_coverage_basis": "string"
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--stocks-code-profile"></a>
#### `GET /stocks/{code}/profile`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/marketdata/routes.py` `get_profile`
- 프론트: `getProfile(code: string): Promise<StockProfile>`
  - 호출: real.ts:27 `` getProfile: (code) => http.get(`/stocks/${code}/profile`), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 | 형식 `^[0-9A-Z]{6}$` |

**응답** `200`

프론트 타입 (mock 기준) `StockProfile`

| 필드 | 타입 | 필수 |
|---|---|---|
| `code` | `string` | 예 |
| `name` | `string` | 예 |
| `market` | `Market` | 예 |
| `overview` | `string` | 예 |
| `prev_close` | `number` | 예 |
| `open` | `number` | 예 |
| `high` | `number` | 예 |
| `low` | `number` | 예 |
| `volume` | `number` | 예 |
| `trading_value` | `number` | 예 |
| `per` | `number \| null` | 예 |
| `pbr` | `number \| null` | 예 |
| `eps` | `number \| null` | 예 |
| `bps` | `number \| null` | 예 |
| `market_cap` | `number` | 예 |
| `shares_outstanding` | `number` | 예 |
| `week52_low` | `number` | 예 |
| `week52_high` | `number` | 예 |

<details><summary>예시</summary>

```json
{
  "code": "string",
  "name": "string",
  "market": "KOSPI",
  "overview": "string",
  "prev_close": 0,
  "open": 0,
  "high": 0,
  "low": 0,
  "volume": 0,
  "trading_value": 0,
  "per": 0,
  "pbr": 0,
  "eps": 0,
  "bps": 0,
  "market_cap": 0,
  "shares_outstanding": 0,
  "week52_low": 0,
  "week52_high": 0
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--stocks-code-quote"></a>
#### `GET /stocks/{code}/quote`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/marketdata/routes.py` `get_quote`
- 프론트: `getQuote(code: string): Promise<Quote>`
  - 호출: real.ts:25 `` getQuote: (code) => http.get(`/stocks/${code}/quote`), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 | 형식 `^[0-9A-Z]{6}$` |

**응답** `200`

프론트 타입 (mock 기준) `Quote`

| 필드 | 타입 | 필수 |
|---|---|---|
| `code` | `string` | 예 |
| `price` | `number` | 예 |
| `change` | `number` | 예 |
| `change_pct` | `number` | 예 |
| `as_of` | `ISODate` | 예 |
| `spark` | `number[]` | 예 |

<details><summary>예시</summary>

```json
{
  "code": "string",
  "price": 0,
  "change": 0,
  "change_pct": 0,
  "as_of": "2026-11-20T09:00:00+09:00",
  "spark": [
    0
  ]
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

### 메모 보드

<a id="delete--board-items-memoid"></a>
#### `DELETE /board-items/{memo_id}`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/board/routes.py` `delete_board_item`
- 프론트: `deleteBoardItem(id: string): Promise<void>`
  - 호출: board.ts:110 `` deleteBoardItem: (id: string) => http.del<void>(`/board-items/${id}`), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `memo_id` | 경로 | `integer` | 예 |  |

**응답** `204` 본문 없음

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--board-items-memoid"></a>
#### `GET /board-items/{memo_id}`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/board/routes.py` `get_board_item`
- 프론트: `getBoardItem(id: string): Promise<BoardItem>`
  - 호출: board.ts:96 `` return normalizeBoardItem(await http.get<RawBoardItem>(`/board-items/${id}`)); ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `memo_id` | 경로 | `integer` | 예 |  |

**응답** `200`

OpenAPI 응답 스키마 `MemoResponse | ChecklistResponse | ReferenceResponse`

- `MemoResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"memo"` | 예 |  |
| `body` | `string` | 예 |  |
| `tags` | `string[]` | 예 |  |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple"` | 예 |  |
| `pinned` | `boolean` | 예 |  |
| `ai_linked` | `boolean` | 예 |  |
| `ai_linked_at` | `string(date-time) \| null` | 예 |  |
| `price_conditions` | `any[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `analysis` | `object \| null` |  |  |

- `ChecklistResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"checklist"` | 예 |  |
| `items` | `ChecklistItemResponse[]` | 예 |  |
| `items.id` | `string` | 예 |  |
| `items.text` | `string` | 예 |  |
| `items.done` | `boolean` | 예 |  |
| `pinned` | `boolean` |  | 기본 `false` |

- `ReferenceResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"reference"` | 예 |  |
| `links` | `ReferenceLinkResponse[]` | 예 |  |
| `links.id` | `string` | 예 |  |
| `links.title` | `string` | 예 |  |
| `links.url` | `string` | 예 |  |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` | 예 |  |
| `links.source` | `"link" \| "file"` | 예 |  |

프론트 타입 (mock 기준) `BoardItem`

<details><summary>예시</summary>

```json
{
  "id": "string",
  "kind": "memo",
  "stock_code": "string",
  "title": "string",
  "position": 0,
  "created_at": "2026-11-20T09:00:00+09:00",
  "updated_at": "2026-11-20T09:00:00+09:00",
  "body": "string",
  "tags": [
    "string"
  ],
  "color": "yellow",
  "pinned": false,
  "ai_linked": false,
  "ai_linked_at": "2026-11-20T09:00:00+09:00",
  "price_conditions": [
    {
      "id": "string",
      "direction": "below",
      "price": 0,
      "tracking": false,
      "status": "waiting",
      "reached_at": "2026-11-20T09:00:00+09:00"
    }
  ],
  "unread_updates": 0
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="patch--board-items-memoid"></a>
#### `PATCH /board-items/{memo_id}`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/board/routes.py` `update_board_item`
- 프론트: `updateBoardItem(id: string, patch: BoardItemPatch): Promise<BoardItem>`
  - 호출: board.ts:108 `` return normalizeBoardItem(await http.patch<RawBoardItem>(`/board-items/${id}`, patch)); ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `memo_id` | 경로 | `integer` | 예 |  |

**요청 본문** `BoardItemPatch` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `title` | `string \| null` |  | 최소 길이 1, 최대 길이 500 |
| `body` | `string \| null` |  | 최대 길이 100000 |
| `tags` | `string[] \| null` |  | 최대 개수 50 |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple" \| null` |  |  |
| `pinned` | `boolean \| null` |  |  |
| `position` | `integer \| null` |  | ≥ 0.0 |
| `items` | `ChecklistItemInput[] \| null` |  | 최대 개수 200 |
| `items.id` | `string \| null` |  |  |
| `items.text` | `string` | 예 | 최소 길이 1, 최대 길이 500 |
| `items.done` | `boolean` |  | 기본 `false` |
| `links` | `ReferenceLinkInput[] \| null` |  | 최대 개수 100 |
| `links.id` | `string \| null` |  |  |
| `links.title` | `string` | 예 | 최소 길이 1, 최대 길이 500 |
| `links.url` | `string(uri)` | 예 | 최소 길이 1, 최대 길이 2083 |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` |  | 기본 `"etc"` |
| `links.source` | `"link" \| "file"` |  | 기본 `"link"` |

**응답** `200`

OpenAPI 응답 스키마 `MemoResponse | ChecklistResponse | ReferenceResponse`

- `MemoResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"memo"` | 예 |  |
| `body` | `string` | 예 |  |
| `tags` | `string[]` | 예 |  |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple"` | 예 |  |
| `pinned` | `boolean` | 예 |  |
| `ai_linked` | `boolean` | 예 |  |
| `ai_linked_at` | `string(date-time) \| null` | 예 |  |
| `price_conditions` | `any[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `analysis` | `object \| null` |  |  |

- `ChecklistResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"checklist"` | 예 |  |
| `items` | `ChecklistItemResponse[]` | 예 |  |
| `items.id` | `string` | 예 |  |
| `items.text` | `string` | 예 |  |
| `items.done` | `boolean` | 예 |  |
| `pinned` | `boolean` |  | 기본 `false` |

- `ReferenceResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"reference"` | 예 |  |
| `links` | `ReferenceLinkResponse[]` | 예 |  |
| `links.id` | `string` | 예 |  |
| `links.title` | `string` | 예 |  |
| `links.url` | `string` | 예 |  |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` | 예 |  |
| `links.source` | `"link" \| "file"` | 예 |  |

프론트 타입 (mock 기준) `BoardItem`

<details><summary>예시</summary>

```json
{
  "id": "string",
  "kind": "memo",
  "stock_code": "string",
  "title": "string",
  "position": 0,
  "created_at": "2026-11-20T09:00:00+09:00",
  "updated_at": "2026-11-20T09:00:00+09:00",
  "body": "string",
  "tags": [
    "string"
  ],
  "color": "yellow",
  "pinned": false,
  "ai_linked": false,
  "ai_linked_at": "2026-11-20T09:00:00+09:00",
  "price_conditions": [
    {
      "id": "string",
      "direction": "below",
      "price": 0,
      "tracking": false,
      "status": "waiting",
      "reached_at": "2026-11-20T09:00:00+09:00"
    }
  ],
  "unread_updates": 0
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="patch--checklists-memoid-items-itemid"></a>
#### `PATCH /checklists/{memo_id}/items/{item_id}`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/board/routes.py` `update_checklist_item`
- 프론트: `setBoardChecklistItem(checklistId: string, itemId: string, done: boolean): Promise<void>`
  - 호출: board.ts:117 `` await http.patch<RawBoardItem>(`/checklists/${checklistId}/items/${itemId}`, { done }); ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `memo_id` | 경로 | `integer` | 예 |  |
| `item_id` | 경로 | `integer` | 예 |  |

**요청 본문** `ChecklistItemPatch` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `text` | `string \| null` |  | 최소 길이 1, 최대 길이 500 |
| `done` | `boolean \| null` |  |  |

**응답** `200`

OpenAPI 응답 스키마 `MemoResponse | ChecklistResponse | ReferenceResponse`

- `MemoResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"memo"` | 예 |  |
| `body` | `string` | 예 |  |
| `tags` | `string[]` | 예 |  |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple"` | 예 |  |
| `pinned` | `boolean` | 예 |  |
| `ai_linked` | `boolean` | 예 |  |
| `ai_linked_at` | `string(date-time) \| null` | 예 |  |
| `price_conditions` | `any[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `analysis` | `object \| null` |  |  |

- `ChecklistResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"checklist"` | 예 |  |
| `items` | `ChecklistItemResponse[]` | 예 |  |
| `items.id` | `string` | 예 |  |
| `items.text` | `string` | 예 |  |
| `items.done` | `boolean` | 예 |  |
| `pinned` | `boolean` |  | 기본 `false` |

- `ReferenceResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"reference"` | 예 |  |
| `links` | `ReferenceLinkResponse[]` | 예 |  |
| `links.id` | `string` | 예 |  |
| `links.title` | `string` | 예 |  |
| `links.url` | `string` | 예 |  |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` | 예 |  |
| `links.source` | `"link" \| "file"` | 예 |  |

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--memos-pinned"></a>
#### `GET /memos/pinned`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/board/routes.py` `list_pinned_memos`
- 프론트: `listPinnedMemos(): Promise<PinnedMemo[]>`
  - 호출: real.ts:58 `listPinnedMemos: () => http.get('/memos/pinned'),`

**응답** `200`

프론트 타입 (mock 기준) `PinnedMemo[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `kind` | `'memo'` | 예 |
| `stock_code` | `string` | 예 |
| `title` | `string` | 예 |
| `position` | `number` | 예 |
| `created_at` | `ISODate` | 예 |
| `updated_at` | `ISODate` | 예 |
| `body` | `string` | 예 |
| `tags` | `string[]` | 예 |
| `color` | `MemoColor` | 예 |
| `pinned` | `boolean` | 예 |
| `ai_linked` | `boolean` | 예 |
| `ai_linked_at` | `ISODate \| null` | 예 |
| `price_conditions` | `PriceCondition[]` | 예 |
| `unread_updates` | `number` | 예 |
| `stock_name` | `string` | 예 |

<details><summary>예시</summary>

```json
[
  "Memo & { stock_name: string }"
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

<a id="post--memos-memoid-conclude"></a>
#### `POST /memos/{memoId}/conclude`

- 상태: **mock**
- 인증: (백엔드 미구현) · 응답은 `frontend/src/api/mock/index.ts`의 같은 함수가 기준
- 프론트: `concludeMemo(memoId: string, conclusion: string): Promise<JournalEntry>`
  - 호출: real.ts:70 `` concludeMemo: (memoId, conclusion) => http.post(`/memos/${memoId}/conclude`, { conclusion }), ``

프론트 타입 (mock 기준) `JournalEntry`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `title` | `string` | 예 |
| `stock_code` | `string \| null` | 예 |
| `stock_name` | `string \| null` | 예 |
| `blocks` | `JournalBlock[]` | 예 |
| `created_at` | `ISODate` | 예 |
| `updated_at` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
{
  "id": "string",
  "title": "string",
  "stock_code": "string",
  "stock_name": "string",
  "blocks": [
    {
      "id": "string",
      "type": "paragraph",
      "text": "string",
      "highlight": false
    }
  ],
  "created_at": "2026-11-20T09:00:00+09:00",
  "updated_at": "2026-11-20T09:00:00+09:00"
}
```

</details>

<a id="put--memos-memoid-ai-link"></a>
#### `PUT /memos/{memo_id}/ai-link`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/board/routes.py` `set_ai_link`
- 프론트: `setAiLink(memoId: string, enabled: boolean): Promise<Memo>`
  - 호출: board.ts:113 `` await http.put<RawBoardItem>(`/memos/${memoId}/ai-link`, { enabled }), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `memo_id` | 경로 | `integer` | 예 |  |

**요청 본문** `AiLinkPatch` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `enabled` | `boolean` | 예 |  |

**응답** `200`

OpenAPI 응답 스키마 `MemoResponse | ChecklistResponse | ReferenceResponse`

- `MemoResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"memo"` | 예 |  |
| `body` | `string` | 예 |  |
| `tags` | `string[]` | 예 |  |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple"` | 예 |  |
| `pinned` | `boolean` | 예 |  |
| `ai_linked` | `boolean` | 예 |  |
| `ai_linked_at` | `string(date-time) \| null` | 예 |  |
| `price_conditions` | `any[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `analysis` | `object \| null` |  |  |

- `ChecklistResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"checklist"` | 예 |  |
| `items` | `ChecklistItemResponse[]` | 예 |  |
| `items.id` | `string` | 예 |  |
| `items.text` | `string` | 예 |  |
| `items.done` | `boolean` | 예 |  |
| `pinned` | `boolean` |  | 기본 `false` |

- `ReferenceResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"reference"` | 예 |  |
| `links` | `ReferenceLinkResponse[]` | 예 |  |
| `links.id` | `string` | 예 |  |
| `links.title` | `string` | 예 |  |
| `links.url` | `string` | 예 |  |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` | 예 |  |
| `links.source` | `"link" \| "file"` | 예 |  |

프론트 타입 (mock 기준) `Memo`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `kind` | `'memo'` | 예 |
| `stock_code` | `string` | 예 |
| `title` | `string` | 예 |
| `position` | `number` | 예 |
| `created_at` | `ISODate` | 예 |
| `updated_at` | `ISODate` | 예 |
| `body` | `string` | 예 |
| `tags` | `string[]` | 예 |
| `color` | `MemoColor` | 예 |
| `pinned` | `boolean` | 예 |
| `ai_linked` | `boolean` | 예 |
| `ai_linked_at` | `ISODate \| null` | 예 |
| `price_conditions` | `PriceCondition[]` | 예 |
| `unread_updates` | `number` | 예 |

<details><summary>예시</summary>

```json
{
  "id": "string",
  "kind": "memo",
  "stock_code": "string",
  "title": "string",
  "position": 0,
  "created_at": "2026-11-20T09:00:00+09:00",
  "updated_at": "2026-11-20T09:00:00+09:00",
  "body": "string",
  "tags": [
    "string"
  ],
  "color": "yellow",
  "pinned": false,
  "ai_linked": false,
  "ai_linked_at": "2026-11-20T09:00:00+09:00",
  "price_conditions": [
    {
      "id": "string",
      "direction": "below",
      "price": 0,
      "tracking": false,
      "status": "waiting",
      "reached_at": "2026-11-20T09:00:00+09:00"
    }
  ],
  "unread_updates": 0
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--memos-memoid-answers"></a>
#### `GET /memos/{memo_id}/answers`

- 상태: **백엔드만 있음** · 담당: 이민성
- 인증: 필요 · 구현: `backend/app/answers/routes.py` `get_memo_answers`

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `memo_id` | 경로 | `integer` | 예 |  |

**응답** `200`

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="post--memos-memoid-confirmations"></a>
#### `POST /memos/{memo_id}/confirmations`

메모 분석의 확인 질문에서 고른 선택지(option_id)로 가격 항목을 만든다. 메모가 바뀌었으면 409.

- 상태: **백엔드만 있음**
- 인증: 필요 · 구현: `backend/app/board/routes.py` `answer_confirmation`

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `memo_id` | 경로 | `integer` | 예 |  |

**요청 본문** `ConfirmationAnswer` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `option_id` | `string` | 예 | 최소 길이 10, 최대 길이 4000 |

**응답** `200`

OpenAPI 응답 스키마 `MemoResponse | ChecklistResponse | ReferenceResponse`

- `MemoResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"memo"` | 예 |  |
| `body` | `string` | 예 |  |
| `tags` | `string[]` | 예 |  |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple"` | 예 |  |
| `pinned` | `boolean` | 예 |  |
| `ai_linked` | `boolean` | 예 |  |
| `ai_linked_at` | `string(date-time) \| null` | 예 |  |
| `price_conditions` | `any[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `analysis` | `object \| null` |  |  |

- `ChecklistResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"checklist"` | 예 |  |
| `items` | `ChecklistItemResponse[]` | 예 |  |
| `items.id` | `string` | 예 |  |
| `items.text` | `string` | 예 |  |
| `items.done` | `boolean` | 예 |  |
| `pinned` | `boolean` |  | 기본 `false` |

- `ReferenceResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"reference"` | 예 |  |
| `links` | `ReferenceLinkResponse[]` | 예 |  |
| `links.id` | `string` | 예 |  |
| `links.title` | `string` | 예 |  |
| `links.url` | `string` | 예 |  |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` | 예 |  |
| `links.source` | `"link" \| "file"` | 예 |  |

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--stocks-code-board"></a>
#### `GET /stocks/{code}/board`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/board/routes.py` `list_board`
- 프론트: `listBoard(code: string): Promise<BoardItem[]>`
  - 호출: board.ts:92 `` const rows = await http.get<RawBoardItem[]>(`/stocks/${code}/board`); ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 |  |

**응답** `200`

OpenAPI 응답 스키마 `MemoResponse | ChecklistResponse | ReferenceResponse[]`

- `MemoResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"memo"` | 예 |  |
| `body` | `string` | 예 |  |
| `tags` | `string[]` | 예 |  |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple"` | 예 |  |
| `pinned` | `boolean` | 예 |  |
| `ai_linked` | `boolean` | 예 |  |
| `ai_linked_at` | `string(date-time) \| null` | 예 |  |
| `price_conditions` | `any[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `analysis` | `object \| null` |  |  |

- `ChecklistResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"checklist"` | 예 |  |
| `items` | `ChecklistItemResponse[]` | 예 |  |
| `items.id` | `string` | 예 |  |
| `items.text` | `string` | 예 |  |
| `items.done` | `boolean` | 예 |  |
| `pinned` | `boolean` |  | 기본 `false` |

- `ReferenceResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"reference"` | 예 |  |
| `links` | `ReferenceLinkResponse[]` | 예 |  |
| `links.id` | `string` | 예 |  |
| `links.title` | `string` | 예 |  |
| `links.url` | `string` | 예 |  |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` | 예 |  |
| `links.source` | `"link" \| "file"` | 예 |  |

프론트 타입 (mock 기준) `BoardItem[]`

<details><summary>예시</summary>

```json
[
  {
    "id": "string",
    "kind": "memo",
    "stock_code": "string",
    "title": "string",
    "position": 0,
    "created_at": "2026-11-20T09:00:00+09:00",
    "updated_at": "2026-11-20T09:00:00+09:00",
    "body": "string",
    "tags": [
      "string"
    ],
    "color": "yellow",
    "pinned": false,
    "ai_linked": false,
    "ai_linked_at": "2026-11-20T09:00:00+09:00",
    "price_conditions": [
      {
        "id": "…",
        "direction": "…",
        "price": "…",
        "tracking": "…",
        "status": "…",
        "reached_at": "…"
      }
    ],
    "unread_updates": 0
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="put--stocks-code-board-order"></a>
#### `PUT /stocks/{code}/board-order`

끌어서 옮긴 뒤 보드 카드 전체 순서를 저장하고, 새 순서의 보드를 돌려준다.

- 상태: **백엔드만 있음** · 담당: 이민성
- 인증: 필요 · 구현: `backend/app/board/routes.py` `put_board_order`

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 |  |

**요청 본문** `BoardOrderPut` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `ids` | `integer[]` | 예 | 최대 개수 1000 |

**응답** `200`

OpenAPI 응답 스키마 `MemoResponse | ChecklistResponse | ReferenceResponse[]`

- `MemoResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"memo"` | 예 |  |
| `body` | `string` | 예 |  |
| `tags` | `string[]` | 예 |  |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple"` | 예 |  |
| `pinned` | `boolean` | 예 |  |
| `ai_linked` | `boolean` | 예 |  |
| `ai_linked_at` | `string(date-time) \| null` | 예 |  |
| `price_conditions` | `any[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `analysis` | `object \| null` |  |  |

- `ChecklistResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"checklist"` | 예 |  |
| `items` | `ChecklistItemResponse[]` | 예 |  |
| `items.id` | `string` | 예 |  |
| `items.text` | `string` | 예 |  |
| `items.done` | `boolean` | 예 |  |
| `pinned` | `boolean` |  | 기본 `false` |

- `ReferenceResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"reference"` | 예 |  |
| `links` | `ReferenceLinkResponse[]` | 예 |  |
| `links.id` | `string` | 예 |  |
| `links.title` | `string` | 예 |  |
| `links.url` | `string` | 예 |  |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` | 예 |  |
| `links.source` | `"link" \| "file"` | 예 |  |

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="post--stocks-code-checklists"></a>
#### `POST /stocks/{code}/checklists`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/board/routes.py` `create_checklist`
- 프론트: `createChecklist(code: string, input: ChecklistInput): Promise<Checklist>`
  - 호출: board.ts:102 `` return normalizeBoardItem(await http.post<RawBoardItem>(`/stocks/${code}/checklists`, input)) as Checklist; ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 |  |

**요청 본문** `ChecklistCreate` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `title` | `string` | 예 | 최소 길이 1, 최대 길이 500 |
| `items` | `ChecklistItemInput[]` |  | 최대 개수 200 |
| `items.id` | `string \| null` |  |  |
| `items.text` | `string` | 예 | 최소 길이 1, 최대 길이 500 |
| `items.done` | `boolean` |  | 기본 `false` |

**응답** `201`

OpenAPI 응답 스키마 `MemoResponse | ChecklistResponse | ReferenceResponse`

- `MemoResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"memo"` | 예 |  |
| `body` | `string` | 예 |  |
| `tags` | `string[]` | 예 |  |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple"` | 예 |  |
| `pinned` | `boolean` | 예 |  |
| `ai_linked` | `boolean` | 예 |  |
| `ai_linked_at` | `string(date-time) \| null` | 예 |  |
| `price_conditions` | `any[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `analysis` | `object \| null` |  |  |

- `ChecklistResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"checklist"` | 예 |  |
| `items` | `ChecklistItemResponse[]` | 예 |  |
| `items.id` | `string` | 예 |  |
| `items.text` | `string` | 예 |  |
| `items.done` | `boolean` | 예 |  |
| `pinned` | `boolean` |  | 기본 `false` |

- `ReferenceResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"reference"` | 예 |  |
| `links` | `ReferenceLinkResponse[]` | 예 |  |
| `links.id` | `string` | 예 |  |
| `links.title` | `string` | 예 |  |
| `links.url` | `string` | 예 |  |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` | 예 |  |
| `links.source` | `"link" \| "file"` | 예 |  |

프론트 타입 (mock 기준) `Checklist`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `kind` | `'checklist'` | 예 |
| `stock_code` | `string` | 예 |
| `title` | `string` | 예 |
| `position` | `number` | 예 |
| `created_at` | `ISODate` | 예 |
| `updated_at` | `ISODate` | 예 |
| `items` | `ChecklistItem[]` | 예 |
| `pinned` | `boolean` |  |

<details><summary>예시</summary>

```json
{
  "id": "string",
  "kind": "checklist",
  "stock_code": "string",
  "title": "string",
  "position": 0,
  "created_at": "2026-11-20T09:00:00+09:00",
  "updated_at": "2026-11-20T09:00:00+09:00",
  "items": [
    {
      "id": "string",
      "text": "string",
      "done": false
    }
  ],
  "pinned": false
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="post--stocks-code-memos"></a>
#### `POST /stocks/{code}/memos`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/board/routes.py` `create_memo`
- 프론트: `createMemo(code: string, input: MemoInput): Promise<Memo>`
  - 호출: board.ts:99 `` return normalizeBoardItem(await http.post<RawBoardItem>(`/stocks/${code}/memos`, input)) as Memo; ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 |  |

**요청 본문** `MemoCreate` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `title` | `string` | 예 | 최소 길이 1, 최대 길이 500 |
| `body` | `string` | 예 | 최대 길이 100000 |
| `tags` | `string[]` |  | 최대 개수 50 |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple"` |  | 기본 `"yellow"` |
| `ai_linked` | `boolean` |  | 기본 `false` |
| `pinned` | `boolean` |  | 기본 `false` |

**응답** `201`

OpenAPI 응답 스키마 `MemoResponse | ChecklistResponse | ReferenceResponse`

- `MemoResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"memo"` | 예 |  |
| `body` | `string` | 예 |  |
| `tags` | `string[]` | 예 |  |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple"` | 예 |  |
| `pinned` | `boolean` | 예 |  |
| `ai_linked` | `boolean` | 예 |  |
| `ai_linked_at` | `string(date-time) \| null` | 예 |  |
| `price_conditions` | `any[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `analysis` | `object \| null` |  |  |

- `ChecklistResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"checklist"` | 예 |  |
| `items` | `ChecklistItemResponse[]` | 예 |  |
| `items.id` | `string` | 예 |  |
| `items.text` | `string` | 예 |  |
| `items.done` | `boolean` | 예 |  |
| `pinned` | `boolean` |  | 기본 `false` |

- `ReferenceResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"reference"` | 예 |  |
| `links` | `ReferenceLinkResponse[]` | 예 |  |
| `links.id` | `string` | 예 |  |
| `links.title` | `string` | 예 |  |
| `links.url` | `string` | 예 |  |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` | 예 |  |
| `links.source` | `"link" \| "file"` | 예 |  |

프론트 타입 (mock 기준) `Memo`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `kind` | `'memo'` | 예 |
| `stock_code` | `string` | 예 |
| `title` | `string` | 예 |
| `position` | `number` | 예 |
| `created_at` | `ISODate` | 예 |
| `updated_at` | `ISODate` | 예 |
| `body` | `string` | 예 |
| `tags` | `string[]` | 예 |
| `color` | `MemoColor` | 예 |
| `pinned` | `boolean` | 예 |
| `ai_linked` | `boolean` | 예 |
| `ai_linked_at` | `ISODate \| null` | 예 |
| `price_conditions` | `PriceCondition[]` | 예 |
| `unread_updates` | `number` | 예 |

<details><summary>예시</summary>

```json
{
  "id": "string",
  "kind": "memo",
  "stock_code": "string",
  "title": "string",
  "position": 0,
  "created_at": "2026-11-20T09:00:00+09:00",
  "updated_at": "2026-11-20T09:00:00+09:00",
  "body": "string",
  "tags": [
    "string"
  ],
  "color": "yellow",
  "pinned": false,
  "ai_linked": false,
  "ai_linked_at": "2026-11-20T09:00:00+09:00",
  "price_conditions": [
    {
      "id": "string",
      "direction": "below",
      "price": 0,
      "tracking": false,
      "status": "waiting",
      "reached_at": "2026-11-20T09:00:00+09:00"
    }
  ],
  "unread_updates": 0
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="post--stocks-code-references"></a>
#### `POST /stocks/{code}/references`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/board/routes.py` `create_reference`
- 프론트: `createReference(code: string, input: ReferenceInput): Promise<ReferenceBoard>`
  - 호출: board.ts:105 `` return normalizeBoardItem(await http.post<RawBoardItem>(`/stocks/${code}/references`, input)) as ReferenceBoard; ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 |  |

**요청 본문** `ReferenceCreate` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `title` | `string` | 예 | 최소 길이 1, 최대 길이 500 |
| `links` | `ReferenceLinkInput[]` |  | 최대 개수 100 |
| `links.id` | `string \| null` |  |  |
| `links.title` | `string` | 예 | 최소 길이 1, 최대 길이 500 |
| `links.url` | `string(uri)` | 예 | 최소 길이 1, 최대 길이 2083 |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` |  | 기본 `"etc"` |
| `links.source` | `"link" \| "file"` |  | 기본 `"link"` |

**응답** `201`

OpenAPI 응답 스키마 `MemoResponse | ChecklistResponse | ReferenceResponse`

- `MemoResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"memo"` | 예 |  |
| `body` | `string` | 예 |  |
| `tags` | `string[]` | 예 |  |
| `color` | `"yellow" \| "blue" \| "pink" \| "green" \| "purple"` | 예 |  |
| `pinned` | `boolean` | 예 |  |
| `ai_linked` | `boolean` | 예 |  |
| `ai_linked_at` | `string(date-time) \| null` | 예 |  |
| `price_conditions` | `any[]` |  |  |
| `unread_updates` | `integer` |  | 기본 `0` |
| `analysis` | `object \| null` |  |  |

- `ChecklistResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"checklist"` | 예 |  |
| `items` | `ChecklistItemResponse[]` | 예 |  |
| `items.id` | `string` | 예 |  |
| `items.text` | `string` | 예 |  |
| `items.done` | `boolean` | 예 |  |
| `pinned` | `boolean` |  | 기본 `false` |

- `ReferenceResponse`

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `id` | `string` | 예 |  |
| `stock_code` | `string` | 예 |  |
| `title` | `string` | 예 |  |
| `position` | `integer` | 예 |  |
| `created_at` | `string(date-time)` | 예 |  |
| `updated_at` | `string(date-time)` | 예 |  |
| `kind` | `"reference"` | 예 |  |
| `links` | `ReferenceLinkResponse[]` | 예 |  |
| `links.id` | `string` | 예 |  |
| `links.title` | `string` | 예 |  |
| `links.url` | `string` | 예 |  |
| `links.ref_type` | `"ir" \| "news" \| "report" \| "disclosure" \| "etc"` | 예 |  |
| `links.source` | `"link" \| "file"` | 예 |  |

프론트 타입 (mock 기준) `ReferenceBoard`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `kind` | `'reference'` | 예 |
| `stock_code` | `string` | 예 |
| `title` | `string` | 예 |
| `position` | `number` | 예 |
| `created_at` | `ISODate` | 예 |
| `updated_at` | `ISODate` | 예 |
| `links` | `ReferenceLink[]` | 예 |

<details><summary>예시</summary>

```json
{
  "id": "string",
  "kind": "reference",
  "stock_code": "string",
  "title": "string",
  "position": 0,
  "created_at": "2026-11-20T09:00:00+09:00",
  "updated_at": "2026-11-20T09:00:00+09:00",
  "links": [
    {
      "id": "string",
      "title": "string",
      "url": "string",
      "ref_type": "ir",
      "source": "link"
    }
  ]
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

### AI 업데이트

<a id="get--ai-updates-summary"></a>
#### `GET /ai-updates/summary`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/updates/routes.py` `get_ai_updates_summary`
- 프론트: `listMemoUpdateSummary(): Promise<MemoUpdateSummary[]>`
  - 호출: real.ts:66 `listMemoUpdateSummary: () => http.get('/ai-updates/summary'),`

**응답** `200`

프론트 타입 (mock 기준) `MemoUpdateSummary[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `stock_code` | `string` | 예 |
| `stock_name` | `string` | 예 |
| `new_count` | `number` | 예 |
| `memos` | `{ memo_id: string; title: string; color: MemoColor; updates: AiUpdate[] }[]` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "stock_code": "string",
    "stock_name": "string",
    "new_count": 0,
    "memos": [
      {
        "memo_id": "…",
        "title": "…",
        "color": "…",
        "updates": "…"
      }
    ]
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

<a id="post--ai-updates-updateid-read"></a>
#### `POST /ai-updates/{update_id}/read`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/updates/routes.py` `mark_ai_update_read`
- 프론트: `markAiUpdateRead(id: string): Promise<void>`
  - 호출: real.ts:34 `` markAiUpdateRead: (id) => http.post(`/ai-updates/${id}/read`), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `update_id` | 경로 | `integer` | 예 |  |

**응답** `204` 본문 없음

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--memos-memoid-timeline"></a>
#### `GET /memos/{memo_id}/timeline`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/updates/routes.py` `get_memo_timeline`
- 프론트: `getMemoTimeline(memoId: string): Promise<MemoTimeline>`
  - 호출: real.ts:32 `` getMemoTimeline: (memoId) => http.get(`/memos/${memoId}/timeline`), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `memo_id` | 경로 | `integer` | 예 |  |

**응답** `200`

프론트 타입 (mock 기준) `MemoTimeline`

| 필드 | 타입 | 필수 |
|---|---|---|
| `memo_id` | `string` | 예 |
| `entries` | `TimelineEntry[]` | 예 |
| `price_condition_count` | `number` | 예 |

<details><summary>예시</summary>

```json
{
  "memo_id": "string",
  "entries": [
    {
      "kind": "update",
      "at": "2026-11-20T09:00:00+09:00",
      "update": {
        "id": "…",
        "stock_code": "…",
        "stock_name": "…",
        "type": "…",
        "title": "…",
        "source": "…",
        "url": "…",
        "published_at": "…",
        "memo_id": "…",
        "memo_title": "…",
        "memo_version": "…",
        "summary": "…",
        "headline": "…",
        "read": "…",
        "relevance": "…"
      },
      "memo_snapshot": {
        "version": "…",
        "title": "…",
        "body": "…",
        "saved_at": "…"
      }
    }
  ],
  "price_condition_count": 0
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--stocks-code-ai-updates"></a>
#### `GET /stocks/{code}/ai-updates`

보드 우측 패널: 이 종목의 AI 연결 ON 메모에 연결된 카드, 최신순.

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/updates/routes.py` `list_stock_ai_updates`
- 프론트: `listStockAiUpdates(code: string): Promise<AiUpdate[]>`
  - 호출: real.ts:33 `` listStockAiUpdates: (code) => http.get(`/stocks/${code}/ai-updates`), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `code` | 경로 | `string` | 예 |  |
| `limit` | 쿼리 | `integer` |  | ≥ 1, ≤ 500, 기본 `100` |

**응답** `200`

프론트 타입 (mock 기준) `AiUpdate[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `stock_code` | `string` | 예 |
| `stock_name` | `string` | 예 |
| `type` | `UpdateType` | 예 |
| `title` | `string` | 예 |
| `source` | `string` | 예 |
| `url` | `string \| null` | 예 |
| `published_at` | `ISODate` | 예 |
| `memo_id` | `string` | 예 |
| `memo_title` | `string` | 예 |
| `memo_version` | `number` | 예 |
| `summary` | `string` | 예 |
| `headline` | `string` | 예 |
| `read` | `boolean` | 예 |
| `relevance` | `number` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "id": "string",
    "stock_code": "string",
    "stock_name": "string",
    "type": "disclosure",
    "title": "string",
    "source": "string",
    "url": "string",
    "published_at": "2026-11-20T09:00:00+09:00",
    "memo_id": "string",
    "memo_title": "string",
    "memo_version": 0,
    "summary": "string",
    "headline": "string",
    "read": false,
    "relevance": 0
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--updates"></a>
#### `GET /updates`

최신 업데이트 피드 (계약 listUpdates → MarketUpdate[]): 지금 내 종목의 최근 30일 카드, 최신순.

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/updates/routes.py` `list_market_updates`
- 프론트: `listUpdates(params?: { stock_code?: string; limit?: number }): Promise<MarketUpdate[]>`
  - 호출: real.ts:43 `listUpdates: (params) => http.get('/updates', params),`

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `stock_code` | 쿼리 | `string \| null` |  | 형식 `^[0-9A-Z]{6}$` |
| `limit` | 쿼리 | `integer \| null` |  | ≥ 1, ≤ 500 |

**응답** `200`

프론트 타입 (mock 기준) `MarketUpdate[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `stock_code` | `string` | 예 |
| `stock_name` | `string` | 예 |
| `type` | `UpdateType` | 예 |
| `title` | `string` | 예 |
| `source` | `string` | 예 |
| `url` | `string \| null` | 예 |
| `published_at` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "id": "string",
    "stock_code": "string",
    "stock_name": "string",
    "type": "disclosure",
    "title": "string",
    "source": "string",
    "url": "string",
    "published_at": "2026-11-20T09:00:00+09:00"
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

### 홈 위젯

<a id="get--checklist-items"></a>
#### `GET /checklist-items`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/home/routes.py` `list_checklist_items`
- 프론트: `listHomeChecklist(): Promise<HomeChecklistItem[]>`
  - 호출: real.ts:59 `listHomeChecklist: () => http.get('/checklist-items'),`

**응답** `200`

프론트 타입 (mock 기준) `HomeChecklistItem[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `checklist_id` | `string` | 예 |
| `text` | `string` | 예 |
| `done` | `boolean` | 예 |
| `stock_code` | `string` | 예 |
| `stock_name` | `string` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "id": "string",
    "checklist_id": "string",
    "text": "string",
    "done": false,
    "stock_code": "string",
    "stock_name": "string"
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

<a id="post--checklist-items"></a>
#### `POST /checklist-items`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/home/routes.py` `add_checklist_item`
- 프론트: `addChecklistItem(stockCode: string, text: string): Promise<HomeChecklistItem>`
  - 호출: real.ts:62 `addChecklistItem: (stockCode, text) => http.post('/checklist-items', { stock_code: stockCode, text }),`

**요청 본문** `ChecklistItemCreate` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `stock_code` | `string` | 예 | 형식 `^[0-9A-Z]{6}$` |
| `text` | `string` | 예 | 최소 길이 1, 최대 길이 500 |

**응답** `201`

프론트 타입 (mock 기준) `HomeChecklistItem`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `checklist_id` | `string` | 예 |
| `text` | `string` | 예 |
| `done` | `boolean` | 예 |
| `stock_code` | `string` | 예 |
| `stock_name` | `string` | 예 |

<details><summary>예시</summary>

```json
{
  "id": "string",
  "checklist_id": "string",
  "text": "string",
  "done": false,
  "stock_code": "string",
  "stock_name": "string"
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="patch--memos-memoid-price-conditions-conditionid"></a>
#### `PATCH /memos/{memo_id}/price-conditions/{condition_id}`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/home/routes.py` `set_price_condition_tracking`
- 프론트: `setPriceConditionTracking(memoId: string, conditionId: string, tracking: boolean): Promise<void>`
  - 호출: real.ts:65 `` http.patch(`/memos/${memoId}/price-conditions/${conditionId}`, { tracking }), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `memo_id` | 경로 | `integer` | 예 |  |
| `condition_id` | 경로 | `integer` | 예 |  |

**요청 본문** `PriceTrackingPatch` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `tracking` | `boolean` | 예 |  |

**응답** `204` 본문 없음

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="get--price-conditions"></a>
#### `GET /price-conditions`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/home/routes.py` `list_price_conditions`
- 프론트: `listPriceConditions(): Promise<PriceConditionRow[]>`
  - 호출: real.ts:63 `listPriceConditions: () => http.get('/price-conditions'),`

**응답** `200`

프론트 타입 (mock 기준) `PriceConditionRow[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `memo_id` | `string` | 예 |
| `memo_title` | `string` | 예 |
| `stock_code` | `string` | 예 |
| `stock_name` | `string` | 예 |
| `condition` | `PriceCondition` | 예 |
| `current_price` | `number` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "memo_id": "string",
    "memo_title": "string",
    "stock_code": "string",
    "stock_name": "string",
    "condition": {
      "id": "string",
      "direction": "below",
      "price": 0,
      "tracking": false,
      "status": "waiting",
      "reached_at": "2026-11-20T09:00:00+09:00"
    },
    "current_price": 0
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

### 휴지통

<a id="get--trash"></a>
#### `GET /trash`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/trash/routes.py` `list_trash`
- 프론트: `listTrash(): Promise<TrashItem[]>`
  - 호출: real.ts:73 `listTrash: () => http.get('/trash'),`

**응답** `200`

프론트 타입 (mock 기준) `TrashItem[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `kind` | `TrashKind` | 예 |
| `title` | `string` | 예 |
| `context` | `string` | 예 |
| `deleted_at` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "id": "string",
    "kind": "memo",
    "title": "string",
    "context": "string",
    "deleted_at": "2026-11-20T09:00:00+09:00"
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

<a id="delete--trash-trashid"></a>
#### `DELETE /trash/{trash_id}`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/trash/routes.py` `purge_trash`
- 프론트: `purgeTrash(id: string): Promise<void>`
  - 호출: real.ts:75 `` purgeTrash: (id) => http.del(`/trash/${id}`), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `trash_id` | 경로 | `string` | 예 |  |

**응답** `204` 본문 없음

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `409` 지금 상태와 충돌 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="post--trash-trashid-restore"></a>
#### `POST /trash/{trash_id}/restore`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/trash/routes.py` `restore_trash`
- 프론트: `restoreTrash(id: string): Promise<void>`
  - 호출: real.ts:74 `` restoreTrash: (id) => http.post(`/trash/${id}/restore`), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `trash_id` | 경로 | `string` | 예 |  |

**응답** `204` 본문 없음

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

### 크레딧

<a id="get--me-usage"></a>
#### `GET /me/usage`

이번 기간 사용량. 이번 달 기본량을 아직 안 받았으면 여기서 지급한다(쓰기 세션).

- 상태: **구현됨** · 담당: 이민성
- 인증: 필요 · 구현: `backend/app/credits/routes.py` `get_my_usage`
- 프론트: `getUsage(): Promise<CreditUsage>`
  - 호출: real.ts:80 `getUsage: () => http.get('/me/usage'),`

**응답** `200`

프론트 타입 (mock 기준) `CreditUsage`

| 필드 | 타입 | 필수 |
|---|---|---|
| `usage_percent` | `number` | 예 |
| `used` | `number` | 예 |
| `balance` | `number` | 예 |
| `period_start` | `string` | 예 |
| `renews_at` | `ISODate` | 예 |
| `renew_label` | `string` | 예 |
| `paused` | `boolean` | 예 |

<details><summary>예시</summary>

```json
{
  "usage_percent": 0,
  "used": 0,
  "balance": 0,
  "period_start": "string",
  "renews_at": "2026-11-20T09:00:00+09:00",
  "renew_label": "string",
  "paused": false
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

### 투자 기록

<a id="get--journal"></a>
#### `GET /journal`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/journal/routes.py` `list_journal`
- 프론트: `listJournal(): Promise<JournalEntry[]>`
  - 호출: real.ts:46 `listJournal: () => http.get('/journal'),`

**응답** `200`

프론트 타입 (mock 기준) `JournalEntry[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `title` | `string` | 예 |
| `stock_code` | `string \| null` | 예 |
| `stock_name` | `string \| null` | 예 |
| `blocks` | `JournalBlock[]` | 예 |
| `created_at` | `ISODate` | 예 |
| `updated_at` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "id": "string",
    "title": "string",
    "stock_code": "string",
    "stock_name": "string",
    "blocks": [
      {
        "id": "…",
        "type": "…",
        "text": "…",
        "highlight": "…"
      }
    ],
    "created_at": "2026-11-20T09:00:00+09:00",
    "updated_at": "2026-11-20T09:00:00+09:00"
  }
]
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `503` 서버 설정·의존 서비스 문제

<a id="post--journal"></a>
#### `POST /journal`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/journal/routes.py` `create_journal`
- 프론트: `createJournal(input: JournalInput): Promise<JournalEntry>`
  - 호출: real.ts:47 `createJournal: (input) => http.post('/journal', input),`

**요청 본문** `JournalCreate` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `title` | `string` |  | 최대 길이 500, 기본 `""` |
| `stock_code` | `string \| null` |  | 형식 `^[0-9A-Z]{6}$` |
| `blocks` | `TextBlock \| ChecklistBlock \| TableBlock \| AttachmentBlock[]` |  | 최대 개수 500 |

**응답** `201`

프론트 타입 (mock 기준) `JournalEntry`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `title` | `string` | 예 |
| `stock_code` | `string \| null` | 예 |
| `stock_name` | `string \| null` | 예 |
| `blocks` | `JournalBlock[]` | 예 |
| `created_at` | `ISODate` | 예 |
| `updated_at` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
{
  "id": "string",
  "title": "string",
  "stock_code": "string",
  "stock_name": "string",
  "blocks": [
    {
      "id": "string",
      "type": "paragraph",
      "text": "string",
      "highlight": false
    }
  ],
  "created_at": "2026-11-20T09:00:00+09:00",
  "updated_at": "2026-11-20T09:00:00+09:00"
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열) · `503` 서버 설정·의존 서비스 문제

<a id="delete--journal-entryid"></a>
#### `DELETE /journal/{entry_id}`

휴지통으로 보낸다 (deleted_at). 복원·영구 삭제는 /trash.

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/journal/routes.py` `delete_journal`
- 프론트: `deleteJournal(id: string): Promise<void>`
  - 호출: real.ts:49 `` deleteJournal: (id) => http.del(`/journal/${id}`), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `entry_id` | 경로 | `integer` | 예 |  |

**응답** `204` 본문 없음

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

<a id="patch--journal-entryid"></a>
#### `PATCH /journal/{entry_id}`

- 상태: **구현됨**
- 인증: 필요 · 구현: `backend/app/journal/routes.py` `update_journal`
- 프론트: `updateJournal(id: string, patch: Partial<JournalInput>): Promise<JournalEntry>`
  - 호출: real.ts:48 `` updateJournal: (id, patch) => http.patch(`/journal/${id}`, patch), ``

**요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|---|
| `entry_id` | 경로 | `integer` | 예 |  |

**요청 본문** `JournalPatch` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `title` | `string \| null` |  | 최대 길이 500 |
| `stock_code` | `string \| null` |  | 형식 `^[0-9A-Z]{6}$` |
| `blocks` | `TextBlock \| ChecklistBlock \| TableBlock \| AttachmentBlock[] \| null` |  | 최대 개수 500 |

**응답** `200`

프론트 타입 (mock 기준) `JournalEntry`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `title` | `string` | 예 |
| `stock_code` | `string \| null` | 예 |
| `stock_name` | `string \| null` | 예 |
| `blocks` | `JournalBlock[]` | 예 |
| `created_at` | `ISODate` | 예 |
| `updated_at` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
{
  "id": "string",
  "title": "string",
  "stock_code": "string",
  "stock_name": "string",
  "blocks": [
    {
      "id": "string",
      "type": "paragraph",
      "text": "string",
      "highlight": false
    }
  ],
  "created_at": "2026-11-20T09:00:00+09:00",
  "updated_at": "2026-11-20T09:00:00+09:00"
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `404` 대상 없음 (다른 사용자 것 포함) · `422` 요청 검증 실패 (FastAPI 형식 detail 배열) · `503` 서버 설정·의존 서비스 문제

### 캘린더

<a id="get--calendar"></a>
#### `GET /calendar`

- 상태: **mock**
- 인증: (백엔드 미구현) · 응답은 `frontend/src/api/mock/index.ts`의 같은 함수가 기준
- 프론트: `listCalendar(month: string): Promise<CalendarEvent[]>`
  - 호출: real.ts:55 `listCalendar: (month) => http.get('/calendar', { month }),`

프론트 타입 (mock 기준) `CalendarEvent[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `date` | `string` | 예 |
| `title` | `string` | 예 |
| `category` | `CalendarCategory` | 예 |
| `stock_code` | `string \| null` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "id": "string",
    "date": "string",
    "title": "string",
    "category": "holiday",
    "stock_code": "string"
  }
]
```

</details>

<a id="post--calendar"></a>
#### `POST /calendar`

- 상태: **mock**
- 인증: (백엔드 미구현) · 응답은 `frontend/src/api/mock/index.ts`의 같은 함수가 기준
- 프론트: `createCalendarEvent(input: { date: string; title: string }): Promise<CalendarEvent>`
  - 호출: real.ts:56 `createCalendarEvent: (input) => http.post('/calendar', input),`

프론트 타입 (mock 기준) `CalendarEvent`

| 필드 | 타입 | 필수 |
|---|---|---|
| `id` | `string` | 예 |
| `date` | `string` | 예 |
| `title` | `string` | 예 |
| `category` | `CalendarCategory` | 예 |
| `stock_code` | `string \| null` | 예 |

<details><summary>예시</summary>

```json
{
  "id": "string",
  "date": "string",
  "title": "string",
  "category": "holiday",
  "stock_code": "string"
}
```

</details>

### 인사이트

<a id="get--insights-compare-memos"></a>
#### `GET /insights/compare-memos`

- 상태: **mock**
- 인증: (백엔드 미구현) · 응답은 `frontend/src/api/mock/index.ts`의 같은 함수가 기준
- 프론트: `listCompareMemos(): Promise<CompareMemoCard[]>`
  - 호출: real.ts:68 `listCompareMemos: () => http.get('/insights/compare-memos'),`

프론트 타입 (mock 기준) `CompareMemoCard[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `memo_id` | `string` | 예 |
| `memo_title` | `string` | 예 |
| `left` | `CompareSide` | 예 |
| `right` | `CompareSide` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "memo_id": "string",
    "memo_title": "string",
    "left": {
      "stock_code": "string",
      "stock_name": "string",
      "price": 0,
      "return_1m": 0,
      "per": 0,
      "pbr": 0,
      "operating_margin": 0,
      "roe": 0,
      "debt_ratio": 0
    },
    "right": {
      "stock_code": "string",
      "stock_name": "string",
      "price": 0,
      "return_1m": 0,
      "per": 0,
      "pbr": 0,
      "operating_margin": 0,
      "roe": 0,
      "debt_ratio": 0
    }
  }
]
```

</details>

<a id="get--insights-conclude-candidates"></a>
#### `GET /insights/conclude-candidates`

- 상태: **mock**
- 인증: (백엔드 미구현) · 응답은 `frontend/src/api/mock/index.ts`의 같은 함수가 기준
- 프론트: `listConcludeCandidates(): Promise<ConcludeCandidate[]>`
  - 호출: real.ts:69 `listConcludeCandidates: () => http.get('/insights/conclude-candidates'),`

프론트 타입 (mock 기준) `ConcludeCandidate[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `memo_id` | `string` | 예 |
| `memo_title` | `string` | 예 |
| `memo_body` | `string` | 예 |
| `stock_code` | `string` | 예 |
| `stock_name` | `string` | 예 |
| `color` | `MemoColor` | 예 |
| `premise_event` | `string` | 예 |
| `occurred_at` | `ISODate` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "memo_id": "string",
    "memo_title": "string",
    "memo_body": "string",
    "stock_code": "string",
    "stock_name": "string",
    "color": "yellow",
    "premise_event": "string",
    "occurred_at": "2026-11-20T09:00:00+09:00"
  }
]
```

</details>

<a id="get--insights-memo-backtest"></a>
#### `GET /insights/memo-backtest`

- 상태: **mock**
- 인증: (백엔드 미구현) · 응답은 `frontend/src/api/mock/index.ts`의 같은 함수가 기준
- 프론트: `listMemoBacktests(): Promise<MemoBacktest[]>`
  - 호출: real.ts:67 `listMemoBacktests: () => http.get('/insights/memo-backtest'),`

프론트 타입 (mock 기준) `MemoBacktest[]`

| 필드 | 타입 | 필수 |
|---|---|---|
| `memo_id` | `string` | 예 |
| `memo_title` | `string` | 예 |
| `stock_code` | `string` | 예 |
| `stock_name` | `string` | 예 |
| `condition` | `PriceCondition` | 예 |
| `triggered_at` | `ISODate \| null` | 예 |
| `trigger_price` | `number \| null` | 예 |
| `current_price` | `number` | 예 |
| `return_pct` | `number \| null` | 예 |

<details><summary>예시</summary>

```json
[
  {
    "memo_id": "string",
    "memo_title": "string",
    "stock_code": "string",
    "stock_name": "string",
    "condition": {
      "id": "string",
      "direction": "below",
      "price": 0,
      "tracking": false,
      "status": "waiting",
      "reached_at": "2026-11-20T09:00:00+09:00"
    },
    "triggered_at": "2026-11-20T09:00:00+09:00",
    "trigger_price": 0,
    "current_price": 0,
    "return_pct": 0
  }
]
```

</details>

### AI 통계

<a id="get--ai-stats"></a>
#### `GET /ai/stats`

- 상태: **구현됨** · 담당: 이민성
- 인증: 필요 · 구현: `backend/app/stats/routes.py` `get_ai_stats`
- 프론트: `getAiStats(): Promise<AiStats>`
  - 호출: real.ts:79 `getAiStats: () => http.get('/ai/stats'),`

**응답** `200`

프론트 타입 (mock 기준) `AiStats`

| 필드 | 타입 | 필수 |
|---|---|---|
| `linked_memos` | `number` | 예 |
| `updates_this_month` | `number` | 예 |
| `linked_stocks` | `number` | 예 |

<details><summary>예시</summary>

```json
{
  "linked_memos": 0,
  "updates_this_month": 0,
  "linked_stocks": 0
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

### 데이터

<a id="delete--data"></a>
#### `DELETE /data`

- 상태: **mock**
- 인증: (백엔드 미구현) · 응답은 `frontend/src/api/mock/index.ts`의 같은 함수가 기준
- 프론트: `deleteAllData(): Promise<void>`
  - 호출: real.ts:83 `deleteAllData: () => http.del('/data'),`

<a id="post--data-export"></a>
#### `POST /data/export`

- 상태: **mock**
- 인증: (백엔드 미구현) · 응답은 `frontend/src/api/mock/index.ts`의 같은 함수가 기준
- 프론트: `exportData(format: 'csv' | 'json'): Promise<{ url: string }>`
  - 호출: real.ts:82 `exportData: (format) => http.post('/data/export', { format }),`

프론트 타입 (mock 기준) `{ url: string }`

| 필드 | 타입 | 필수 |
|---|---|---|
| `url` | `string` | 예 |

<details><summary>예시</summary>

```json
{
  "url": "string"
}
```

</details>

<a id="get--data-stats"></a>
#### `GET /data/stats`

- 상태: **구현됨** · 담당: 이민성
- 인증: 필요 · 구현: `backend/app/stats/routes.py` `get_data_stats`
- 프론트: `getDataStats(): Promise<DataStats>`
  - 호출: real.ts:81 `getDataStats: () => http.get('/data/stats'),`

**응답** `200`

프론트 타입 (mock 기준) `DataStats`

| 필드 | 타입 | 필수 |
|---|---|---|
| `memos` | `number` | 예 |
| `journals` | `number` | 예 |
| `stocks` | `number` | 예 |

<details><summary>예시</summary>

```json
{
  "memos": 0,
  "journals": 0,
  "stocks": 0
}
```

</details>

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)

### 피드백

<a id="post--feedback"></a>
#### `POST /feedback`

- 상태: **구현됨** · 담당: 이민성
- 인증: 필요 · 구현: `backend/app/stats/routes.py` `post_feedback`
- 프론트: `sendFeedback(payload: FeedbackPayload): Promise<void>`
  - 호출: real.ts:84 `sendFeedback: (payload) => http.post('/feedback', payload),`

**요청 본문** `FeedbackPayload` (필수)

| 필드 | 타입 | 필수 | 설명·제약 |
|---|---|---|---|
| `kind` | `"general" \| "bug"` | 예 |  |
| `rating` | `integer \| null` |  | ≥ 1.0, ≤ 5.0 |
| `screen` | `string \| null` |  | 최대 길이 200 |
| `categories` | `string[]` |  | 최대 개수 20 |
| `message` | `string` | 예 | 최대 길이 5000 |

**응답** `204` 본문 없음

**에러**: `401` 인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도) · `403` 권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치 · `422` 요청 검증 실패 (FastAPI 형식 detail 배열)

### MCP

<a id="delete--mcp-apps-appid"></a>
#### `DELETE /mcp/apps/{appId}`

- 상태: **mock**
- 인증: (백엔드 미구현) · 응답은 `frontend/src/api/mock/index.ts`의 같은 함수가 기준
- 프론트: `disconnectMcpApp(appId: string): Promise<Settings>`
  - 호출: real.ts:78 `` disconnectMcpApp: (appId) => http.del(`/mcp/apps/${appId}`), ``

프론트 타입 (mock 기준) `Settings`

| 필드 | 타입 | 필수 |
|---|---|---|
| `theme` | `ThemePref` | 예 |
| `language` | `'ko'` | 예 |
| `updown_color` | `UpDownColor` | 예 |
| `notifications` | `{ disclosure: boolean; news: boolean; price_condition: boolean; price_spike: boolean; price_spike_threshold: 3 \| 5 \| 10; channels: { in_app: boolean; email: boolean; push: boolean }; frequency: 'realtime' \| 'hourly' \| 'daily'; quiet_hours: { enabled: boolean; from: string; to: string }; }` | 예 |
| `ai` | `{ default_link_new_memo: boolean; sources: { disclosure: boolean; news: boolean; price: boolean }; sensitivity: 'strict' \| 'balanced' \| 'broad'; }` | 예 |
| `mcp` | `{ enabled: boolean; server_url: string; scopes: { memo: boolean; journal: boolean; stock: boolean }; access: 'read' \| 'read_write'; only_ai_linked: boolean; apps: { id: string; name: string; access: 'read' \| 'read_write'; last_used_at: ISODate }[]; }` | 예 |

<details><summary>예시</summary>

```json
{
  "theme": "system",
  "language": "ko",
  "updown_color": "red_up",
  "notifications": {
    "disclosure": false,
    "news": false,
    "price_condition": false,
    "price_spike": false,
    "price_spike_threshold": 3,
    "channels": {
      "in_app": false,
      "email": false,
      "push": false
    },
    "frequency": "realtime",
    "quiet_hours": {
      "enabled": false,
      "from": "string",
      "to": "string"
    }
  },
  "ai": {
    "default_link_new_memo": false,
    "sources": {
      "disclosure": false,
      "news": false,
      "price": false
    },
    "sensitivity": "strict"
  },
  "mcp": {
    "enabled": false,
    "server_url": "string",
    "scopes": {
      "memo": false,
      "journal": false,
      "stock": false
    },
    "access": "read",
    "only_ai_linked": false,
    "apps": [
      {
        "id": "…",
        "name": "…",
        "access": "…",
        "last_used_at": "…"
      }
    ]
  }
}
```

</details>

### 파일

<a id="post--files"></a>
#### `POST /files`

- 상태: **mock**
- 인증: (백엔드 미구현) · 응답은 `frontend/src/api/mock/index.ts`의 같은 함수가 기준
- 프론트: `uploadFile(file: UploadFile): Promise<{ url: string; name: string }>`
  - 호출: real.ts:39 `return http.upload('/files', form);`

프론트 타입 (mock 기준) `{ url: string; name: string }`

| 필드 | 타입 | 필수 |
|---|---|---|
| `url` | `string` | 예 |
| `name` | `string` | 예 |

<details><summary>예시</summary>

```json
{
  "url": "string",
  "name": "string"
}
```

</details>
