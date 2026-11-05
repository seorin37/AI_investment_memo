# MEMO'S · AI 투자 메모보드 — 프론트엔드

> 팀 SIG(Saram Is Good) · "내 투자 메모를 AI가 계속 기억하고 시장 변화와 연결해주는 서비스"

**React Native + Expo (SDK 58)** · 웹 우선 개발 → 같은 코드로 iOS/Android 앱 확장
Figma 시안 `AI 투자 메모보드 UI_최종`의 화면 46장을 기준으로 구현했습니다.

```
┌────────────────────────── React Native + Expo (이 저장소) ──────────────────────────┐
│  expo-router · TanStack Query · zustand · react-native-svg · Pretendard            │
└───────────────────────────────▲─────────────────────────────────────────────────────┘
                                │  HTTP/JSON  (EXPO_PUBLIC_API_BASE_URL, docs/API_CONTRACT.md)
┌───────────────────────────────┴──── 강의실 PC · Windows + WSL2 · Docker Compose ─────┐
│  FastAPI (API 서버)   PostgreSQL + pgvector   BGE-M3 (임베딩)   Python Worker (수집)  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. 빠르게 실행하기 (백엔드 없이 목업으로)

```bash
npm install
cp .env.example .env          # 기본값: EXPO_PUBLIC_USE_MOCK=true
npm run web                   # http://localhost:8081
```

로그인 화면에서 아무 버튼이나 누르면 예시 계정 **김나라**로 들어갑니다. 목업 데이터는 시안 문구(SK하이닉스·삼성전자·네이버, 메모 7개, 투자 기록 4개 …)를 그대로 쓰며, 새로고침하면 처음 상태로 돌아갑니다. 사이드바 아래 `● 목업 데이터로 실행 중`이 보이면 목업 모드입니다.

휴대폰에서 보기: **Expo Go**(스토어 최신 버전 = SDK 58 지원) 설치 → `npm start` → QR 스캔.

| 명령 | 설명 |
|---|---|
| `npm run web` | 웹 개발 서버 |
| `npm start` / `npm run tunnel` | 모바일(Expo Go) · 같은 Wi-Fi가 막혀 있으면 tunnel |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | `expo lint` (eslint-config-expo) |
| `npm run export:web` | 정적 웹 빌드 → `dist/` |

## 2. 우리 파이프라인(FastAPI)에 붙이기

1. `.env` 수정
   ```env
   EXPO_PUBLIC_USE_MOCK=false
   EXPO_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
   ```
2. FastAPI에 **CORS** 추가 (`http://localhost:8081` 허용) — 코드 조각은 `docs/API_CONTRACT.md` §0
3. 엔드포인트·JSON 모양은 **`docs/API_CONTRACT.md`** 그대로 구현. 필드는 snake_case.
4. 개발 서버 재시작 (`EXPO_PUBLIC_*` 값은 번들 시점에 들어가므로 `.env`를 바꾸면 재시작 필요)

### 종목 CRUD만 먼저 연결하기

다른 화면은 목업을 유지하면서 인증과 종목 검색·목록·추가·변경·삭제만 FastAPI에 연결할 수 있습니다.

```env
EXPO_PUBLIC_USE_MOCK=true
EXPO_PUBLIC_USE_REAL_STOCKS=true
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
EXPO_PUBLIC_ANDROID_API_BASE_URL=http://10.0.2.2:8000/api/v1
```

실제 종목 API는 인증을 요구하므로 이 혼합 모드에서도 로그인은 실제 OAuth/JWT 흐름을 사용합니다. OAuth Client 설정이 없으면 계약·오류 처리 검증까지만 가능하며 운영용 인증 우회는 제공하지 않습니다. 종목 태그는 현재 백엔드 스키마에 저장 구조가 없어 실서버 종목 모드에서는 편집 UI를 표시하지 않습니다.

### 메모 보드 CRUD만 연결하기

다른 화면은 목업을 유지하면서 메모·체크리스트·참고자료만 FastAPI에 연결할 수 있습니다.

```env
EXPO_PUBLIC_USE_MOCK=true
EXPO_PUBLIC_USE_REAL_BOARD=true
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
EXPO_PUBLIC_ANDROID_API_BASE_URL=http://10.0.2.2:8000/api/v1
```

Real 보드 모드도 실제 OAuth/JWT 로그인이 필요합니다. 메모의 AI 연결 상태는 저장하지만 AI 업데이트·타임라인·가격 조건과 파일 업로드는 아직 실제 API가 없으므로 Real 보드 화면에서 성공한 것처럼 표시하지 않습니다.

### 강의실 PC(WSL2 + Docker) 네트워크 메모

| 상황 | API 주소 | 할 일 |
|---|---|---|
| 같은 PC 브라우저에서 웹 개발 | `http://localhost:8000/api/v1` | Docker Desktop(WSL2 백엔드) 또는 WSL2 localhost 포워딩으로 바로 됨 |
| 휴대폰 Expo Go (같은 Wi-Fi) | `http://<강의실PC IPv4>:8000/api/v1` | `uvicorn --host 0.0.0.0`, Windows 방화벽 8000 허용. WSL2 안에서 Docker Engine을 직접 돌리면 `.wslconfig`의 `networkingMode=mirrored` 또는 `netsh interface portproxy` 필요 |
| Android 에뮬레이터 | `http://10.0.2.2:8000/api/v1` | – |
| 강의실 Wi-Fi가 기기 간 통신을 막을 때 | – | `npm run tunnel`(Metro) + API는 ngrok/Cloudflare Tunnel 등으로 노출 |

> Expo 개발 서버(Metro)를 WSL2 안에서 띄우면 휴대폰이 8081에 못 붙는 경우가 많습니다. **Windows 쪽 터미널에서 `npm start`** 하거나 tunnel을 쓰세요.

### 소셜 로그인
카카오·네이버·구글 OAuth는 **백엔드가 처리**하고, 프론트는 `/auth/{provider}/login?redirect_uri=…`만 엽니다. 콜백(`/auth/callback?token=JWT`)에서 토큰을 저장합니다 (웹: localStorage, 앱: SecureStore). 자세한 흐름은 API 계약서 §0.

## 3. 시안 → 코드 매핑

| 시안 (zip) | 라우트 | 주요 파일 |
|---|---|---|
| 1. 로그인 | `/login` | `src/app/login.tsx` |
| Main Sidebar · 12. 설정 및 지원 팝업 | (공통) | `src/components/layout/Sidebar.tsx`, `AppShell.tsx` |
| 2.0 홈 시작 설정 · 2.1 기본 템플릿 · 2.2 / 2.4.x 사용자화 | `/` | `src/features/home/HomeScreen.tsx`, `registry.tsx` |
| 이상규의 위젯 아이디어 (6종 + 세부 화면) | `/` 위젯 | `src/features/home/widgets/MemoWidgets.tsx` |
| 3.1 최신 업데이트 · 3.2 종목별 업데이트 | `/updates`, `/updates/[code]` | `src/features/updates/UpdatesScreens.tsx` |
| 4. 종목 추가 | 모달 | `src/features/stock/AddStockModal.tsx` |
| 5. 투자 기록 | `/journal` | `src/app/(main)/journal.tsx`, `features/journal/JournalEditor.tsx` |
| 6~6.3 기업 메모장 · 새 메모/체크리스트/참고자료 | `/stocks/[code]` | `src/features/board/*` |
| 메모 팝업 · AI 업데이트 세부 화면(타임라인) | 모달 | `MemoDetailModal.tsx`, `AiTimeline.tsx` |
| 7~7.2 기업정보 · 그래프 호버 | `/stocks/[code]?tab=info` | `src/features/company/CompanyInfo.tsx`, `components/charts/*` |
| 8-1~8-7 설정 | 모달 | `src/features/settings/SettingsModal.tsx` |
| 9 · 9.1 피드백/오류 신고 | 모달 | `src/features/feedback/FeedbackModal.tsx` |
| 10 휴지통 (최종: 검색 + 유형) | 모달 | `src/features/trash/TrashModal.tsx` |
| 11 도움말 | `/help` | `src/app/(main)/help.tsx` |

### 반영한 팀 결정
- 새 메모 팝업 = 메모·체크리스트·참고자료 3종, **체크리스트·참고자료는 AI 연결 없음**
- 메모 팝업 AI 업데이트 = 시계열 타임라인 + **당시 메모 버전** 표시
- AI 연결 카드 하단 사용량 줄 제거
- 홈 위젯: 기존 4종 + **메모대로 했다면 · 비교 메모 자동 카드 · 결론 낼 메모**
- 시장 한눈에 보기 = 큰 카드 3장 + **매크로 띠(D안: 금리·금·유가·채권)**
- 뉴스 = 매일경제·한국경제·서울경제·연합뉴스만, 제목·매체·원문 링크·시각만 (**C안 헤드라인 강조형**)
- 기업 건전성 레이더 = **업종 평균 없이 선택 기업만**, 지표 ?는 오른쪽 목록, 선택 지표 빨간색
- 매출·영업이익·순이익 막대 위에 **전년 대비 증감률 꺾은선**
- 투자 기록 = 애플 메모처럼, 도구 5개(가가·체크리스트·표·첨부·마크업) **편집 영역 아래 떠 있는 바(B안)**

### 시안과 다르게 처리한 부분
- **등락 색상**: 시안 홈 지수 카드는 하락=빨강이었지만, 설정(8-1) '상승 빨강·하락 파랑'을 앱 전체에 일관 적용 (설정에서 바꾸면 전부 바뀜)
- **다크 테마**: 설정 항목만 있고 '준비 중' 표시
- **사용량** 화면: 시안이 없어 AI 연결 현황 수치만 최소 구성
- **위젯 이동/크기**: '끌어서 이동' 손잡이 드래그로 순서 변경, '크기 조정' 버튼으로 너비(4열 기준) 순환
- 시세·실적 숫자는 목업에서 서로 맞도록(전일→등락률, PER=주가÷EPS 등) 계산값을 사용

## 4. 폴더 구조

```
src/
├─ app/                       # expo-router 라우트 (파일 = 화면)
│  ├─ _layout.tsx             # 폰트 · React Query · 인증 부트스트랩
│  ├─ login.tsx, auth/callback.tsx
│  └─ (main)/                 # 로그인 후: 사이드바/드로어 셸
│     ├─ index.tsx            # 홈
│     ├─ updates/, stocks/[code].tsx, journal.tsx, help.tsx
├─ api/
│  ├─ types.ts                # Api 인터페이스 (= 백엔드 계약)
│  ├─ http.ts, real.ts        # FastAPI 호출
│  └─ mock/                   # 목업 구현 + 시안 시드 데이터
├─ hooks/queries.ts           # React Query 훅 (화면은 이것만 사용)
├─ store/                     # zustand: 인증 · UI(모달/사이드바/토스트)
├─ theme/tokens.ts            # 시안에서 뽑은 색·간격·폰트 토큰
├─ components/                # ui · icons · charts(SVG) · layout
├─ features/                  # 화면 단위 기능 (home, board, company, journal, …)
└─ types/models.ts            # 도메인 타입 (snake_case)
docs/API_CONTRACT.md          # 백엔드 팀용 계약서
```

### 개발 규칙
- 화면에서 `api`를 직접 부르지 말고 `hooks/queries.ts` 훅을 쓰세요 (캐시 무효화가 한곳에 모여 있음).
- 색/폰트는 `theme/tokens.ts` 토큰만, 텍스트는 `<T>` 컴포넌트만 (안드로이드 굵기 폰트 처리).
- 새 홈 위젯: `features/home/widgets/`에 컴포넌트 → `registry.tsx`의 `WIDGETS`에 한 줄 추가.
- 새 API: `api/types.ts` → `real.ts` → `mock/index.ts` → `hooks/queries.ts` → `docs/API_CONTRACT.md` 순서로.

## 5. 검증 내역 (2026-10-21)
- `tsc --noEmit` 통과, `expo lint` 0건
- `expo export --platform web` / `--platform android` 번들 성공
- 웹(1440px)·모바일(390px)에서 전 화면 스크린샷 대조, 메모 생성→가격 조건 인식→홈 위젯 반영, 체크리스트 토글, 휴지통 삭제/복원, 위젯 드래그 정렬, 투자 기록 자동 저장, 캔들 차트 호버 동작 확인
- iOS/Android 실기기 실행은 아직 확인 전 (Expo Go로 확인 필요)

## 라이선스
폰트 Pretendard — SIL Open Font License 1.1 (orioncactus/pretendard)
