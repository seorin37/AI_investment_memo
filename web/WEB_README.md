# web/ — MEMO'S 웹 (Vite + React 19 + TypeScript + Tailwind)

웹 시연 v2를 옮겨 온 웹 전용 프론트엔드예요. `frontend/`(Expo 앱)와 따로 돌아요.

| 명령 | 하는 일 |
|---|---|
| `npm ci` | 설치 (package-lock.json 기준) |
| `npm run dev` | 개발 서버 http://localhost:8081 (백엔드 CORS와 로그인 복귀 주소가 8081 기준) |
| `npm run build` | 타입 검사 후 `dist/`에 빌드 |
| `npm run preview` | 빌드 결과를 8081에서 확인 |
| `npm run lint` | oxlint |

- Expo 개발 서버(`frontend`의 `npm run web`)도 8081을 써요. 그래서 둘을 동시에 띄울 수 없어요.

## 데이터 구조 (11.18~)
- 화면 코드에는 예시 데이터가 없어요. 화면은 `src/api/index.ts`의 `api` 객체로만 데이터를 받아요.
- 지금은 **가상 서버**(`src/api/mock/`)가 답해요.
  - 코스피 시총 상위 50종목마다 시세·차트·재무·공시/뉴스/주가 소식을 날짜 기준으로 만들어요.
  - 같은 날이면 같은 값이 나와요.
- 내 데이터는 브라우저 localStorage에 계정(소셜 제공자)별로 저장돼요.
  - 새로고침하거나 다시 로그인해도 그대로 남아요.
- **새 가입자는 빈 상태로 시작해요.** 고른 종목만 있고, 메모·기록·만든 항목은 없어요.
- 백엔드 연결 방법과 데이터 모양은 **`API.md`**에 있어요. 타입은 `src/api/types.ts`에 있어요.

```
src/api/types.ts        API 데이터 모양 (백엔드와의 약속)
src/api/index.ts        api 객체 — 백엔드 연결 시 여기만 바꿈
src/api/mock/           가상 서버 (universe 50종목 · market · ai · db(localStorage) · seed(발표용 예시 계정))
src/store.tsx           내 데이터 상태(ud) + 모든 변경(act.*) + 로그인 세션(useSession)
```

## API 모드 (실제 FastAPI 연결)
기본은 위의 **시연 모드**(가상 서버)예요. `VITE_USE_API=true`일 때만 실제 백엔드(`backend/app`, `/api/v1`)에 붙어요.

```
cp .env.example .env.local     # VITE_USE_API=true · VITE_API_BASE_URL=http://localhost:8000/api/v1
npm run dev                    # 8081 (백엔드 CORS·로그인 복귀 주소 기준)
```
- 백엔드 `.env`에 필요한 설정 이름: `AUTH_JWT_SECRET`, `AUTH_PUBLIC_BASE_URL`, `AUTH_WEB_RETURN_URLS=http://localhost:8081`, `{KAKAO,NAVER,GOOGLE}_OAUTH_CLIENT_ID/SECRET`, 로컬 http면 `AUTH_COOKIE_SECURE=false`. 값은 프론트에 넣지 않아요.
- 팀원 `API.md`의 `/api/me/state` · `/api/market/*` · `/api/ai/*` 주소는 백엔드에 없어서 쓰지 않아요. 실제로 있는 API만 연결했어요.
- 실제 백엔드로 끝까지 돌려 본 확인은 **아직 안 했어요 (미확인)**. 시연 모드는 e2e 85개로 확인했어요.

| 무엇 | API 모드에서 | 엔드포인트 |
|---|---|---|
| 로그인 · 로그아웃 | 서버 (쿠키 세션 · CSRF · 401이면 refresh 1번) | `GET /auth/{provider}/start` → `GET /auth/me`, `POST /auth/logout` |
| 내 종목 (추가·보유/관심·삭제·검색) | 서버 | `GET/POST /stocks`, `PATCH/DELETE /stocks/{code}`, `GET /stocks/search` |
| 종목 빼기 · 다시 추가 (휴지통 복원) | 서버 — 빼면 내 종목 표시만 지워지고(`user_stocks.deleted_at`) 메모는 그대로예요. 같은 종목을 다시 추가하면 `deleted_at`이 풀려 메모도 함께 돌아와요 (`backend/app/stocks/repository.py` `soft_delete` · `upsert_user_stock`) | `DELETE /stocks/{code}` → `POST /stocks` |
| 메모 (만들기·제목/본문/색/고정·삭제) | 서버 | `GET /stocks/{code}/board`, `POST /stocks/{code}/memos`, `PATCH/DELETE /board-items/{id}` |
| 체크리스트 (종목마다 하나) | 서버 | `POST /stocks/{code}/checklists`, `PATCH /board-items/{id}`, `PATCH /checklists/{id}/items/{itemId}` |
| AI 연결 | 서버 — 연결 창이 열리면 `enabled:true`로 켜고 서버 분석 결과(`analysis.items`)를 보여 줘요 (미리보기 없음). 결과를 보고 연결을 누르면 켠 채로 두고, '일반 메모로 두기'·Esc·바깥 클릭으로 닫거나 카드 토글을 끄면 `enabled:false` | `PUT /memos/{id}/ai-link` |
| AI 업데이트 타임라인 · 새 소식 배지 · 읽음 | 서버 | `GET /memos/{id}/timeline`, `POST /ai-updates/{id}/read` |
| 내 종목 가격 | **"—" (시세 준비 중)** — 시세 API가 생기면 `api.market.price` 한 곳만 바꾸면 돼요 | 없음 |
| 시세·차트·재무·소식·지수·일정 · 최신 업데이트 · 스튜디오(오디오·보고서·실험실·퀴즈) | 가상 서버 그대로 + 화면 위 **'예시 데이터'** 안내 | 없음 |
| 투자 기록 · 휴지통 목록 · 만든 항목 · 알림 · 설정 · 홈 위젯 · 프로필 수정 · 종목 순서 · 보드 카드 순서 | **이 기기에만 저장** (localStorage, 사용자 id별) — 투자 기록 화면에 '이 기기에만 저장돼요' | 없음 |
| 휴지통 메모 복원 | 새 메모로 다시 만들어요 — AI 연결과 업데이트 기록은 복원되지 않아요 | 복원 API 없음 |
| 전체 삭제 · 회원 탈퇴 | 막아 둠 ("아직 지원하지 않아요") — 지운 척하지 않아요 | 없음 |
| 시연 도구 | 숨김 | — |

코드 위치: `src/api/config.ts`(환경변수) · `http.ts`(쿠키+CSRF 클라이언트) · `client.ts`(실제 엔드포인트) · `sync.ts`(바뀐 내 데이터 → 필요한 요청만) · `remote.ts`(API 모드 구현·이 기기 저장) · `src/apimode.tsx`(안내 문구). 화면과 `act.*`는 그대로 두고, `api.me.save(상태)`가 불릴 때 서버에 저장된 값과 비교해 필요한 요청만 보내요. 요청이 실패하면 알림을 띄우고 서버 내용으로 다시 불러와요.

### 백엔드 할 일 (웹에서 필요한 것)
- **휴지통 복원 API** (메모·체크리스트·종목). 지금은 복원하면 새 메모로 다시 만들어서 AI 연결·업데이트 기록·수정 이력이 이어지지 않아요.
- 회원 탈퇴 · 내 데이터 전체 삭제 API
- 시세 API (내 종목 가격·등락·차트) — 웹은 `api.market.price`만 바꾸면 돼요
- 공시·뉴스 소식 목록(최신 업데이트 화면용, 메모 연결 여부와 상관없이), 시장 지수·일정
- 메모 AI 연결 **미리보기**(켜기 전에 추적 항목 확인)와 항목 골라 켜기 — 지금은 켜는 순간 서버가 항목을 정해요
- 투자 기록 · 설정 · 홈 위젯 · 보드 카드 순서 저장 API (지금은 이 기기에만 저장)
- 프로필 수정 API (이름·한 줄 소개)
- 스튜디오(AI 오디오·주간보고서·실험실·퀴즈)와 사용량

## 시연 도구
- 키보드 `` ` `` 키나 왼쪽 아래 '시연' 버튼으로 열어요.
- **예시 계정으로 보기**: 메모 8개, 체크리스트, 투자 기록, 만든 항목이 채워진 발표용 계정이에요.
- **처음 상태로 초기화**: 모든 계정을 지우고 첫 화면부터 시작해요.
- 실패, 사용량 소진, 인터넷 끊김 같은 상황도 여기서 켤 수 있어요.

## 전체 흐름 테스트
```
npm i -D playwright && npx playwright install chromium   # 한 번만
npm run dev                                               # 다른 터미널에서
node e2e/full-flow.cjs                                    # 85개 항목 · 실패하면 e2e/out/fail_*.png
```
테스트는 아래 흐름을 확인해요.
1. 가입하고 종목을 골라요.
2. 종목별 체크리스트와 메모를 써요.
3. AI 연결, 타임라인, 배지를 확인해요.
4. 수정 이력을 확인해요.
5. 휴지통으로 보내고 복원해요.
6. 종목을 뺐다가 복원해요.
7. 스튜디오 4종이 내 종목으로 만들어지는지 확인해요.
8. 업데이트 화면과 기업정보를 확인해요.
9. 새로고침과 재로그인 뒤에도 데이터가 남는지 확인해요.
10. 다른 계정으로 로그인해요.
11. 알림, 검색, 프로필, 알림 끄기를 확인해요.
12. 다크 모드와 맞춤 홈을 확인해요.
13. 전체 삭제와 탈퇴를 확인해요.
14. 다크 모드 메모지 색, 이름 꺾임, 그래프 선, 메모·체크리스트 끌어서 옮기기(마우스·터치)를 확인해요.

## 문서
- 결정 기록: `DECISIONS.md`
- 화면 명세: `SPEC.md`
- 백엔드 API: `API.md`
