/* API 연결 설정 — 값은 web/.env.local 등 Vite 환경변수에서만 읽는다 (비밀값 없음: 주소와 켜기/끄기뿐).
   VITE_USE_API=true  → 실제 FastAPI에 연결 (로그인 · 내 종목 · 메모 · 체크리스트 · AI 업데이트)
   그 밖의 값/없음     → 지금까지의 시연 모드 (예시 데이터, 서버 호출 없음) */
const env = import.meta.env;

export const API_MODE = String(env.VITE_USE_API ?? "").trim().toLowerCase() === "true";
export const API_BASE = String(env.VITE_API_BASE_URL || "http://localhost:8000/api/v1").trim().replace(/\/+$/, "");
