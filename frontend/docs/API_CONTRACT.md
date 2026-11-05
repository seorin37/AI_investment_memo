# MEMO'S 프론트엔드 ↔ FastAPI API 계약 (v0.1)

프론트엔드는 이 문서의 엔드포인트만 호출합니다. 타입 정의 원본은 `src/types/models.ts`, 호출 코드는 `src/api/real.ts` 입니다.
목업(`src/api/mock`)도 같은 인터페이스(`src/api/types.ts`의 `Api`)를 구현하므로, **목업 응답 모양 = 백엔드가 돌려줘야 할 모양**입니다.

## 0. 공통 규칙

| 항목 | 규칙 |
|---|---|
| Base URL | `EXPO_PUBLIC_API_BASE_URL` (예: `http://localhost:8000/api/v1`) |
| 필드 이름 | **snake_case 그대로** (Pydantic 기본값, 변환 레이어 없음) |
| 날짜 | ISO 8601 + 타임존 (`2026-10-21T09:30:00+09:00`). 일봉·캘린더 날짜만 `YYYY-MM-DD` |
| 금액 | 원 단위 정수/실수 (`97146700000000`). 조·억 표기는 프론트가 처리 |
| 비율 | 퍼센트 숫자 (`48.6` = 48.6%) |
| 인증 | `Authorization: Bearer <JWT>` |
| 에러 | FastAPI 기본 형식 `{"detail": "메시지"}` 또는 422 `{"detail":[{"msg": ...}]}` → 프론트가 `detail`을 그대로 사용자에게 보여줌 |
| 401 | 프론트가 자동 로그아웃 → 로그인 화면 |
| 204 | 본문 없는 성공 응답 허용 (DELETE 등) |

### CORS (FastAPI)

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",          # npx expo start --web
        "http://127.0.0.1:8081",
        "http://<강의실PC_IP>:8081",       # 같은 Wi-Fi의 다른 PC에서 웹으로 볼 때
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

> 네이티브 앱(Expo Go/개발 빌드)은 브라우저가 아니므로 CORS 영향을 받지 않습니다.

### 소셜 로그인 (카카오·네이버·구글)

클라이언트 시크릿은 **백엔드에만** 둡니다. 프론트는 시스템 브라우저만 열며 토큰을 리다이렉트 URL로 받지 않습니다.

1. 프론트 → `GET /auth/{provider}/start?client=&return_to=&code_challenge=` (provider = `kakao` | `naver` | `google`)
2. 백엔드 → 각 사 OAuth 동의 화면으로 302
3. 백엔드 콜백에서 사용자 생성/조회. 웹은 HttpOnly 쿠키, Android는 짧은 수명의 단일 사용 code만 전달
4. Android 앱은 앱 PKCE verifier와 code를 `/auth/mobile/exchange`에서 교환하고 Refresh Token만 SecureStore에 저장

허용할 복귀 주소 예시: `http://localhost:8081/auth/callback`(웹), `memos://auth/callback`(Development Build). Expo Go 전용 주소는 운영 allowlist에 넣지 않습니다.

---

## 1. 인증 · 사용자

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/auth/{provider}/start` | `?client=web\|mobile&return_to=&code_challenge=` | 302 |
| GET | `/auth/{provider}/callback` | Provider `code`, `state` | 302 (웹 쿠키 또는 모바일 1회용 code) |
| POST | `/auth/mobile/exchange` | `{code, code_verifier}` | `AuthToken` |
| POST | `/auth/refresh` | 웹: 쿠키 / Android: `{refresh_token}` | `AuthToken` |
| POST | `/auth/logout` | 웹: 쿠키 / Android: `{refresh_token}` | 204 |
| GET | `/auth/me` | – | `User` |
| PATCH | `/me` | `{name?, bio?}` | `User` |

```json
// AuthToken
{ "access_token": "eyJ...", "refresh_token": "Android 응답에만 포함", "expires_in": 900, "token_type": "bearer",
  "user": { "id": "u_1", "name": "김나라", "bio": "대학생", "avatar_url": null, "email": "nara@kakao.example",
            "providers": [{ "provider": "kakao", "email": "nara@kakao.example", "connected": true, "current": true }] } }
```

## 2. 종목 (사이드바 · 종목 추가 · 헤더 · 기업정보)

| Method | Path | 설명 | Response |
|---|---|---|---|
| GET | `/stocks` | 내 종목(보유/관심) + 안 읽은 AI 업데이트 수 | `MyStock[]` |
| GET | `/stocks/search?q=삼성` | 종목 마스터 검색 (KRX 상장사) | `StockMaster[]` (최대 8개) |
| POST | `/stocks` | `{code, status: "holding"\|"watching"}` 이미 있으면 구분만 변경 | `MyStock` |
| PATCH | `/stocks/{code}` | `{status?, tags?}` | `MyStock` |
| DELETE | `/stocks/{code}` | 휴지통으로 이동 | 204 |
| GET | `/stocks/{code}/quote` | 현재가·등락 + 헤더 스파크라인(최근 ~24개 종가) | `Quote` |
| GET | `/stocks/{code}/candles?range=1W\|1M\|3M\|1Y` | 일봉 OHLCV (오래된 → 최신) — KIS Open API → `prices_daily` | `Candle[]` |
| GET | `/stocks/{code}/profile` | 기업 개요 + 시세/투자정보 + 52주 최고·최저 | `StockProfile` |
| GET | `/stocks/{code}/financials` | 연간 실적(최근 7개년, 증감률 계산용 1년 포함) + 안정성 | `Financials` |

```json
// MyStock
{ "code": "000660", "name": "SK하이닉스", "market": "KOSPI", "status": "holding", "tags": [], "unread_updates": 3, "added_at": "2026-09-20T10:00:00+09:00" }
// Quote
{ "code": "000660", "price": 180500, "change": 4200, "change_pct": 2.38, "as_of": "2026-10-21T15:30:00+09:00", "spark": [171200, 172900, ...] }
// Financials.annual[i]
{ "period": "2025-12", "revenue": 97146700000000, "operating_income": 47206300000000, "net_income": 42947900000000,
  "operating_margin": 48.6, "net_margin": 44.2, "roe": 33.0 }
// Financials.stability
{ "as_of": "2026-06", "debt_ratio": 58, "current_ratio": 170, "quick_ratio": 125, "interest_coverage": 25, "reserve_ratio": 1750 }
```

> 기업 건전성 레이더는 **선택 기업만** 그립니다(업종 평균 없음). 점수화(0~1)는 프론트 `CompanyInfo.tsx`의 `HEALTH`에서 합니다.

## 3. 메모 보드 (6. 기업 메모장)

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/stocks/{code}/board` | – | `BoardItem[]` (`position` 오름차순) |
| POST | `/stocks/{code}/memos` | `MemoInput {title, body, tags, color, ai_linked, pinned?}` | `Memo` |
| POST | `/stocks/{code}/checklists` | `{title, items:[{text, done}]}` | `Checklist` |
| POST | `/stocks/{code}/references` | `{title, links:[{title, url, ref_type, source}]}` | `ReferenceBoard` |
| PATCH | `/board-items/{id}` | 부분 수정 (메모: title/body/tags/color/pinned/position, 체크리스트: title/items, 참고자료: title/links) | `BoardItem` |
| DELETE | `/board-items/{id}` | 휴지통으로 이동 | 204 |
| PUT | `/memos/{id}/ai-link` | `{enabled}` | `Memo` |
| GET | `/memos/{id}/timeline` | 메모 팝업 'AI 업데이트' 탭 | `MemoTimeline` |
| GET | `/stocks/{code}/ai-updates` | 보드 우측 패널 (AI 연결 ON 메모에 연결된 것만, 최신순) | `AiUpdate[]` |
| POST | `/ai-updates/{id}/read` | 읽음 처리 | 204 |
| POST | `/files` | multipart `file` (참고자료·투자 기록 첨부) | `{url, name}` |

백엔드 규칙 (팀 결정):
- **체크리스트·참고자료는 AI 연결 없음** — 임베딩/분석 대상 아님.
- 메모 `title`/`body`가 바뀌면 **새 버전(`MemoVersion`) 저장** → 타임라인에서 어떤 버전에 대한 업데이트였는지 표시.
- `price_conditions`는 본문의 "15만원 밑이면…" 같은 표현을 **코드(정규식)로 파싱** — LLM 사용 안 함. 매 영업일 종가로 `status`(`waiting`/`reached`/`paused`) 갱신.
- `ai_linked=false` 메모는 임베딩·LLM 판단에서 제외.

```json
// Memo
{ "id": "m4", "kind": "memo", "stock_code": "000660", "position": 6,
  "title": "15만원 밑으로 오면 다시 생각", "body": "지지선 근처 오면\n분할 매수 고민해보기.",
  "tags": ["매수가"], "color": "green", "pinned": true,
  "ai_linked": true, "ai_linked_at": "2026-09-25T22:31:00+09:00",
  "price_conditions": [{ "id": "pc1", "direction": "below", "price": 150000, "tracking": true, "status": "waiting", "reached_at": null }],
  "unread_updates": 0, "created_at": "2026-09-25T22:31:00+09:00", "updated_at": "2026-10-06T21:14:00+09:00" }

// AiUpdate (= MarketUpdate + 메모 연결 정보)
{ "id": "a7", "stock_code": "000660", "stock_name": "SK하이닉스", "type": "price",
  "title": "종가 180,500원", "headline": "15만원 조건가에서 멀어졌어요",
  "summary": "종가 180,500원 · 조건가보다 30,500원(20.3%) 높아요. 아직 설정한 15만원 조건에 도달하지 않았어요.",
  "source": "한국투자증권 KIS", "url": null, "published_at": "2026-10-11T15:30:00+09:00",
  "memo_id": "m4", "memo_title": "15만원 밑으로 오면 다시 생각", "memo_version": 2, "read": true, "relevance": 1.0 }

// MemoTimeline.entries[] — 최신순. kind: update | memo_edit | memo_created | ai_linked
{ "kind": "update", "at": "...", "update": { /* AiUpdate */ }, "memo_snapshot": { "version": 2, "title": "...", "body": "...", "saved_at": "..." } }
{ "kind": "memo_edit", "at": "...", "version": { /* MemoVersion */ } }
{ "kind": "ai_linked", "at": "..." }
```

`type`: `disclosure`(DART) · `news`(네이버 뉴스 검색 API/RSS) · `price`(KIS 확정 일봉 → 규칙·시계열 계산)

## 4. 최신 업데이트 (3.1 / 3.2)

| Method | Path | Response |
|---|---|---|
| GET | `/updates?stock_code=005930&limit=50` | `MarketUpdate[]` 최신순. `stock_code` 생략 시 내 종목 전체 |

## 5. 투자 기록 (5)

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/journal` | – | `JournalEntry[]` 최신순 |
| POST | `/journal` | `{title, stock_code, blocks}` | `JournalEntry` |
| PATCH | `/journal/{id}` | 부분 수정 (자동 저장: 입력 멈춘 뒤 0.7초) | `JournalEntry` |
| DELETE | `/journal/{id}` | 휴지통으로 이동 | 204 |

`blocks`는 JSONB 한 컬럼에 그대로 저장하면 됩니다.
```json
[{ "id": "b1", "type": "paragraph", "text": "…", "highlight": false },
 { "id": "b4", "type": "heading", "text": "다음 액션" },
 { "id": "b5", "type": "checklist", "text": "실적 발표일 확인하기", "checked": false },
 { "id": "b7", "type": "table", "rows": [["항목","값"],["",""]] },
 { "id": "b8", "type": "attachment", "name": "리포트.pdf", "url": "https://…" }]
```

## 6. 홈 · 위젯

| Method | Path | 위젯 | Response |
|---|---|---|---|
| GET / PUT | `/home/layout` | 시작 설정·사용자화 | `HomeLayout {mode, widgets:[{id,type,span}]}` |
| GET | `/market/overview` | 시장 지수·환율 + 매크로 띠(금리·금·유가·채권) | `MarketOverview` |
| GET | `/calendar?month=2026-10` | 주요 증시 일정 | `CalendarEvent[]` (`category`: holiday/market/mine) |
| POST | `/calendar` | `{date, title}` → 내 일정 | `CalendarEvent` |
| GET | `/news/headlines` | 뉴스 (매일경제·한국경제·서울경제·연합뉴스만, 최신순) | `NewsHeadline[]` |
| GET | `/memos/pinned` | 고정한 메모 | `(Memo & {stock_name})[]` |
| GET | `/checklist-items` | 확인할 것 | `HomeChecklistItem[]` |
| PATCH | `/checklists/{id}/items/{itemId}` | `{done}` | 204 |
| POST | `/checklist-items` | `{stock_code, text}` (종목 체크리스트 없으면 생성) | `HomeChecklistItem` |
| GET | `/price-conditions` | 지켜보는 가격 조건 | `PriceConditionRow[]` |
| PATCH | `/memos/{id}/price-conditions/{cid}` | `{tracking}` | 204 |
| GET | `/ai-updates/summary` | 메모에 도착한 소식(종목별) | `MemoUpdateSummary[]` |
| GET | `/insights/memo-backtest` | **메모대로 했다면** | `MemoBacktest[]` |
| GET | `/insights/compare-memos` | **비교 메모 자동 카드** | `CompareMemoCard[]` |
| GET | `/insights/conclude-candidates` | **결론 낼 메모** | `ConcludeCandidate[]` |
| POST | `/memos/{id}/conclude` | `{conclusion}` → 투자 기록 생성 + 메모 정리 | `JournalEntry` |

`IndexRange` 시리즈 키: `1D`, `1W`, `1M`, `1Y` (각 20~50개 포인트면 충분).

## 7. 휴지통 · 설정 · 데이터 · 피드백

| Method | Path | Response |
|---|---|---|
| GET | `/trash` | `TrashItem[]` |
| POST | `/trash/{id}/restore` | 204 |
| DELETE | `/trash/{id}` | 204 (영구 삭제) |
| GET / PATCH | `/settings` | `Settings` (PATCH는 깊은 부분 병합) |
| DELETE | `/mcp/apps/{id}` | `Settings` |
| GET | `/ai/stats` | `AiStats {linked_memos, updates_this_month, linked_stocks}` |
| GET | `/data/stats` | `DataStats {memos, journals, stocks}` |
| POST | `/data/export` | `{format: "csv"\|"json"}` → `{url}` (다운로드 링크) |
| DELETE | `/data` | 204 |
| POST | `/feedback` | `{kind: "general"\|"bug", rating?, screen?, categories?, message}` → 204 |

---

## 8. 파이프라인에서 누가 무엇을 채우나

| 데이터 | 생산자 (강의실 PC · Docker Compose) | 저장 |
|---|---|---|
| 공시 원문·청크 임베딩 | Python Worker (DART 수집) → BGE-M3 | PostgreSQL + pgvector |
| 뉴스 헤드라인·본문 임베딩 | Python Worker (네이버 뉴스 API/RSS, 중복 제거) → BGE-M3 | PostgreSQL + pgvector |
| 일봉 OHLCV · 가격 이벤트 | Python Worker (KIS Open API) → 규칙 계산 | `prices_daily`, `adjusted_prices_daily` 등 |
| 메모 임베딩 | FastAPI (메모 저장/수정 시, `ai_linked=true`만) → BGE-M3 | pgvector |
| `ai_updates` | Worker: 새 문서 ↔ 메모 임베딩 코사인 유사도 1차 필터 → LLM 관련성 최종 판단 → 짧은 요약 | PostgreSQL |
| `price_conditions.status` | Worker: 종가 vs 조건 (LLM 없음) | PostgreSQL |
