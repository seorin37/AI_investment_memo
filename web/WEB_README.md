# web/ — MEMO'S 웹 (Vite + React 19 + TypeScript + Tailwind)

웹 시연 v2를 옮겨 온 웹 전용 프론트엔드. `frontend/`(Expo 앱)와 따로 돈다.

| 명령 | 하는 일 |
|---|---|
| `npm ci` | 설치 (package-lock.json 기준) |
| `npm run dev` | 개발 서버 http://localhost:8081 (백엔드 CORS·로그인 복귀 주소가 8081 기준) |
| `npm run build` | `dist/`에 빌드 |
| `npm run preview` | 빌드 결과를 8081에서 확인 |

- 주의: Expo 개발 서버(`frontend`의 `npm run web`)도 8081을 써서 둘을 동시에 띄울 수 없음.
- 지금은 모든 화면이 예시 데이터(`src/data.ts`, `src/store.tsx`)로 돈다. 실제 API 연결은 다음 단계.
- 결정 기록: `DECISIONS.md`, 화면 명세: `SPEC.md`
