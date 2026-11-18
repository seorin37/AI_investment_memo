# web/ — MEMO'S 웹 (Vite + React 19 + TypeScript + Tailwind)

웹 시연 v2를 옮겨 온 웹 전용 프론트엔드. `frontend/`(Expo 앱)와 따로 돈다.

| 명령 | 하는 일 |
|---|---|
| `npm ci` | 설치 (package-lock.json 기준) |
| `npm run dev` | 개발 서버 http://localhost:8081 (백엔드 CORS·로그인 복귀 주소가 8081 기준) |
| `npm run build` | `dist/`에 빌드 |
| `npm run preview` | 빌드 결과를 8081에서 확인 |

- 주의: Expo 개발 서버(`frontend`의 `npm run web`)도 8081을 써서 둘을 동시에 띄울 수 없음.
- 결정 기록: `DECISIONS.md`, 화면 명세: `SPEC.md`

## 두 가지 모드

| 모드 | 켜는 법 | 데이터 |
|---|---|---|
| 시연 (기본) | 아무것도 안 함 | 예시 데이터(`src/data.ts`). 서버 호출 없음. 화면은 이전과 같음 |
| API | `cp .env.example .env.local` (`VITE_USE_API=true`, `VITE_API_BASE_URL`) | FastAPI + PostgreSQL |

API 모드에서 서버와 연결된 것 (나머지는 예시 데이터로 남고, 화면 위에 '예시 데이터' 안내가 뜸):

- 로그인: 카카오·네이버·구글 버튼 → `GET /auth/{provider}/start?client=web` → 돌아오면 쿠키 세션으로 `GET /auth/me`. 로그아웃 `POST /auth/logout`
- 내 종목: 목록·검색·추가·삭제·보유/관심 바꾸기 (`/stocks`, `/stocks/search`)
- 메모 보드: 메모 만들기·고치기·색·고정·삭제(휴지통, 6초 뒤 서버에서 지움 — '되돌리기' 5초 안이면 안 지움)·AI 연결 켜기/끄기, 종목마다 체크리스트 하나
- AI 업데이트: 메모를 열면 `GET /memos/{id}/timeline`, 빨간 숫자를 지우면 `POST /ai-updates/{id}/read`

코드 위치: `src/api/` (`config` 환경변수 · `http` 쿠키+CSRF 클라이언트 · `client` 엔드포인트 · `map` 응답→화면 모양 · `sync` 상태 변화→API), `src/apimode.tsx`(오류 알림·예시 안내).
화면 컴포넌트는 지금처럼 `setStocks`·`setMemos`로 상태만 바꾸고, `store.tsx`가 서버에 저장된 값과 비교해 필요한 요청만 보낸다. 요청이 실패하면 알림을 띄우고 서버 상태로 다시 불러온다.

백엔드 쪽 필요 설정 (`.env`, 값은 프론트에 넣지 않음): `AUTH_JWT_SECRET`, `AUTH_PUBLIC_BASE_URL`, `AUTH_WEB_RETURN_URLS=http://localhost:8081`, `AUTH_MOBILE_RETURN_URLS`, `{KAKAO,NAVER,GOOGLE}_OAUTH_CLIENT_ID/SECRET`, 로컬 http면 `AUTH_COOKIE_SECURE=false`. CORS 기본값이 `http://localhost:8081`이라 개발 서버는 8081 그대로 쓴다.
