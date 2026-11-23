# MEMO'S 웹 ↔ 백엔드 API 명세 (11.18, 프론트 기준)

이 문서의 기준은 프론트(web/)예요. 백엔드는 아래 데이터 모양 그대로 JSON을 돌려주면 돼요.
지금 화면은 가상 서버(`src/api/mock/`)로 모든 기능이 돌아가요. 백엔드가 준비되면 **`src/api/index.ts` 한 파일만** 바꾸면 돼요.

- 데이터 모양(타입)은 `src/api/types.ts`에 있어요. 아래 설명과 다르면 그 파일이 맞아요.
- **데이터 필드 이름은 모두 snake_case예요** (예: `stock_code`, `created_at`). 종목 코드는 `stock_code`, 여러 종목은 `stock_codes`.
- 시간은 모두 한국 시간 ISO 문자열이에요. 예: `2026-11-17T15:30:00+09:00`. 날짜만 쓸 때는 `YYYY-MM-DD`.
- 값이 없으면 `null`로 보내요. 화면에는 `—`로 나와요. 예: 금융업 매출·영업이익.
- 금액 단위: 시세는 원, 재무는 억 원, 비율은 %예요.

---

## 1. 연결 구조

| 구분 | 화면이 부르는 방식 | 백엔드 |
|---|---|---|
| 로그인·내 데이터 | 비동기 (Promise) | 1장 |
| 시장 데이터 (시세·차트·재무·소식·지수·퀴즈) | **동기** | 로그인·새로고침 때 **스냅샷 한 번**으로 받아 캐시해요 (2장) |
| 메모 매칭 (AI 업데이트 타임라인·새 소식 배지) | **동기** | 스냅샷에 포함해요 (3장) |
| AI 생성 (추적 항목 찾기·오디오·보고서·실험실) | 비동기 | 요청할 때마다 호출해요 (4장) |

시장 데이터를 스냅샷으로 받는 이유가 있어요. 앱의 시세는 모두 **전일 종가 기준**이라 하루에 한 번만 바뀌어요.
그래서 화면마다 따로 부르지 않고 한 번에 받아요. 종목을 추가하면 그 종목만 다시 받아요.

---

## 2. 로그인 · 내 데이터

| 메서드 | 경로 | 요청 | 응답 | 화면 함수 |
|---|---|---|---|---|
| GET | `/api/auth/session` | — | `UserState` 또는 401 | `api.auth.session` |
| GET | `/api/auth/{provider}/start` | provider = kakao·naver·google | 소셜 로그인 페이지로 이동 | 로그인 버튼 |
| (콜백) | `/api/auth/{provider}/callback` | — | 웹 `/`로 돌아옴 + 세션 쿠키 | — |
| POST | `/api/auth/login` | `{ provider }` | `{ state: UserState, is_new: boolean }` | `api.auth.login` |
| POST | `/api/auth/logout` | — | 204 | `api.auth.logout` |
| DELETE | `/api/me` | — | 204 (계정과 모든 데이터 삭제) | `api.auth.withdraw` |
| GET | `/api/me/state` | — | `UserState` | 새로고침 |
| PUT | `/api/me/state` | `UserState` 전체 | 204 | `api.me.save` (바뀐 뒤 0.3초 모아서 저장) |

- **계정 단위는 소셜 제공자 하나**예요. 같은 제공자로 다시 들어오면 데이터가 그대로 있어요. `is_new = true`면 약관 → 종목 고르기로 가요.
- **새 가입자 `UserState`는 비어 있어야 해요.** 메모·기록·만든 항목 0개, `onboarded:false`. 예시 데이터는 넣지 않아요.
- `PUT /api/me/state`는 처음 연결용 단순한 방식이에요. 나중에 메모·기록 단위 API로 나눠도 돼요. 그때도 화면 코드는 `store.tsx`의 `act.*`만 바꾸면 돼요.
- 서버가 정하는 값이 있어요. 아래 값은 PUT으로 받아도 **서버 값으로 덮어써요.**
  - `usage`: 사용량은 서버가 계산해요.
  - `notifs` 중 `kind:"upd"`: 매칭 결과에서 서버가 만들어요.
  - `made[].data`: AI 생성 결과예요.

### UserState 주요 필드
| 필드 | 설명 |
|---|---|
| `profile` | 이름·직업·이메일·제공자·사진(작은 data URL 또는 URL)·가입일 |
| `stocks: MyStock[]` | 내 종목 (`hold`: 보유·관심, `order`: 사이드바 순서) |
| `memos: Memo[]` | 메모. `stock_code`로 **종목별**로 나뉘어요. 아래 3장을 보세요 |
| `checklists: Record<stock_code, Checklist>` | **종목마다 하나씩** 있는 체크리스트 |
| `journal: Journal[]` | 투자 기록 (`html`이 있으면 사진이 들어간 본문) |
| `trash: TrashItem[]` | 휴지통. `data`에 원본이 들어 있고, 복원하면 그대로 돌아가요. 30일 뒤 서버가 지워요 |
| `made: Made[]` | 스튜디오에서 만든 항목. 30일 보관 |
| `quiz: QuizResult[]` | 퀴즈 답 기록 (연속 참여 계산용) |
| `notifs`, `usage`, `settings`, `home`, `recent`, `onboarded`, `coach_done` | 알림함, 사용량 %, 알림 설정, 홈 위젯 배치, 최근 본 종목, 첫 안내 완료 여부 |
| `boards: Record<stock_code, string[]>` | 종목 보드의 카드 순서 (11.18). 왼쪽→오른쪽, 위→아래 순서의 `"cl"`(체크리스트)·`"m{메모 id}"`. 화면은 3칸 격자로 그려요. 없거나 빠진 카드는 프론트가 맨 앞에 둬요. 서버는 그대로 저장만 하면 돼요 |

---

## 3. 시장 데이터 스냅샷

| 메서드 | 경로 | 응답 |
|---|---|---|
| GET | `/api/market/universe` | `StockInfo[]`: 추가할 수 있는 전체 종목 (지금은 코스피 시총 상위 50) |
| GET | `/api/market/snapshot?stock_codes=000660,005930` | 아래 묶음 |

```ts
type Snapshot = {
  as_of: string;                              // 기준 종가 시각
  trading_days: string[];                    // 최근 250거래일 YYYY-MM-DD (오래된 → 최근)
  quotes: Record<stock_code, Quote>;
  daily: Record<stock_code, Candle[]>;             // 일봉 250개 → 차트(1W·1M·3M·1Y)·미니차트·보고서가 여기서 잘라 씀
  financials: Record<stock_code, Financials>;      // 분기 12개, 오래된 → 최근
  updates: Record<stock_code, UpdateItem[]>;       // 최근 90일 공시·뉴스·주가 소식
  news: NewsItem[];                          // 홈 뉴스 카드 (시장 + 내 종목)
  indices: IndexQuote[]; index_daily: Record<"kospi"|"kosdaq"|"usd", Candle[]>; index_intraday: Record<…, number[]>; // 홈 시장 카드 '1일' 그래프
  macro: MacroRow[];                         // 실험실 변수의 현재 값 (환율·유가·기준금리·미 10년물)
  schedule: MarketEvent[];                   // 캘린더 위젯 (실적 발표·배당 기준일 등)
  quiz: { today: Quiz; prev: Quiz };         // 오늘의 퀴즈 · 어제 문제(결과 보기용)
  matches: Record<memo_id, MatchItem[]>;      // 메모별로 붙은 소식 (아래)
}
```

### 소식(UpdateItem)의 `tags`
메모 매칭에 쓰는 주제 이름이에요. 서버(LLM·분류기)가 소식마다 붙여 줘요.
`실적 · 보고서 · IR · 매출 · 배당 · 주주환원 · 자사주 · 수주 · 공급 · 투자 · 시설투자 · 수급 · 경쟁 · 주가 · 거래량 · 분석`
여기에 종목 테마도 더해요. 예: `HBM`, `파운드리`, `전기차`.
공시처럼 중요한 소식은 `important: true`로 보내요.

### 메모 매칭 규칙 (지금 가상 서버가 하는 일 = 백엔드가 할 일)
1. 메모에서 AI 연결을 켜면 `findItems`로 **추적 항목(TrackItem)**을 정해요. 사용자가 고른 항목이 `memo.tracks`에 저장돼요.
2. 소식이 이 종목 것이고, **AI 연결 시작일(`ai_since`) 7거래일 전 이후**에 나왔고, 소식의 `tags`가 추적 항목의 `tags`와 하나라도 겹치면 매칭이에요.
   - 추적 항목이 `all`(`tags:["*"]`)이면 `important` 소식과 공시만 매칭해요.
3. 가격 조건(`TrackItem.price`)이 있으면 종가로 계산해요.
   - 조건가의 5% 안으로 들어오면 "가까워졌어요" 1건.
   - 조건가에 닿으면 "도달했어요" 1건.
4. `MatchItem = { kind:"공시"|"뉴스"|"주가", at, title, body, src, url?, id }`, 최신순이에요.
   - `body`에는 요약과 함께 "메모에서 지켜보는 '…'와(과) 관련 있어요" 같은 연결 이유를 넣어요.
5. 새 소식 배지는 `at > memo.seen_at`인 매칭 수예요. 프론트가 계산해요.
   - 사용자가 메모의 AI 업데이트를 열면 `seen_at`이 저장돼요.
6. 업데이트 알림(`notifs` kind `upd`)은 새 매칭이 생길 때 서버가 넣어요. `settings.noti_upd`가 false면 넣지 않아요.

---

## 4. AI 생성 (비동기)

| 메서드 | 경로 | 요청 | 응답 | 화면 |
|---|---|---|---|---|
| POST | `/api/ai/track-items` | `{ stock_code, text }` (메모 제목+본문) | `TrackItem[]` (최대 4개) | 메모 › AI 연결 창 |
| POST | `/api/ai/audio` | `{ stock_codes, days: 1\|3\|7, summary: boolean }` | `AudioEp` | 스튜디오 › AI 오디오 |
| POST | `/api/ai/report` | `{ stock_codes, with_market: boolean }` | `WeeklyReport` | 스튜디오 › AI 주간보고서 |
| POST | `/api/ai/lab` | `{ stock_code, vars: [변수명, "상승"\|"유지"\|"하락"][] }` | `LabResult` | 스튜디오 › AI 투자 실험실 |

- 요청에 메모를 따로 보내지 않아요. 서버는 이미 내 메모를 알고 있어요.
  - 보고서의 `memo_links`와 오디오 스크립트의 "메모에 적어 둔 …" 문장은 서버가 내 메모로 채워요.
- 만드는 동안 화면은 진행 막대를 보여 줘요. 응답이 늦으면 100%에서 기다려요.
  - 응답이 실패하면 실패 화면이 나오고 사용량은 그대로예요.
- 성공하면 서버가 사용량을 올려요. 지금 기준은 오디오·보고서 +8%, 실험실 +4%예요.
  - 100%가 되면 스튜디오는 "이 기능부터는 PLUS예요" 안내를 띄워요.
- 결과 모양:
  - **AudioEp**:
    - `chapters`: [시각, 제목, 시작 초]
    - `script`: [화자, 문장]
    - `dur`: 초
  - **WeeklyReport**:
    - 기간 `from`·`to`
    - 시장 등락
    - 종목별 `ReportStock`: 종가 5개, 공시·뉴스·주가 건수, 주요 소식, 연결된 메모, 한 줄 요약, 다음 주 확인할 것
    - 전체 `summary`·`flow`
  - **LabResult**:
    - `score`: −100~100
    - `verdict`: 긍정·부정·중립
    - `paths`: 변수 → 경로 → 종목, `sign`: 1·−1·0
    - `notes`
  - 스튜디오 결과는 투자 권유나 주가 예측이 아니라는 문구가 화면에 늘 붙어요.

---

## 5. 프론트에서 바꿀 곳 (연결할 때)

1. `src/api/http.ts`를 새로 만들어요. 이 파일이 맡을 일은 세 가지예요.
   - 로그인 후 `snapshot`을 받아 캐시해요.
   - 위 표의 동기 함수는 캐시에서 값을 돌려줘요.
   - 비동기 함수는 `fetch`로 불러요.
2. `src/api/index.ts`에서 `import.meta.env.VITE_API === "http"`이면 http 구현을 쓰게 바꿔요.
3. `src/api/mock/seed.ts`(발표용 예시 계정)와 시연 도구의 "예시 계정으로 보기"는 mock에서만 써요.
4. 로그인 복귀 주소와 CORS 기준 포트는 지금처럼 8081이에요 (WEB_README.md).

## 6. 확인 방법
`e2e/full-flow.cjs`가 가입부터 탈퇴까지 85개 항목을 확인해요.
- 백엔드에 연결한 뒤에도 같은 테스트가 통과해야 해요.
- 실행 방법은 WEB_README.md에 있어요.
