# PR 초안: UI v2 — 원본 시안 기준 새 UI (앱 · 웹)

`feature/cly-ui-v2` → `dev`

## 무엇을 했나
- 팀원이 만든 원본 시안(앱 HTML · 웹 React)을 기준으로 화면을 새로 옮겼습니다. 새 UI는 `frontend/src/ui/` 한 곳에 있고, 앱과 웹이 같은 코드베이스(Expo · expo-router · react-native-web)를 씁니다.
  - 화면: `ui/screens/<화면>/app` · `ui/screens/<화면>/web`
  - 공용 부품 · 셸: `ui/shared` · `ui/layout`
- 라우트(`frontend/src/app/`)는 새 화면을 쓰도록 바꿨습니다. 옛 화면은 지우지 않고 `features/`에 보관했습니다.
- **전부 mock 데이터입니다** (`EXPO_PUBLIC_USE_MOCK=true`, 기본값). 서버·결제·알림 연결은 이 PR에 없습니다.
- 연결되지 않은 동작은 "아직 연결되지 않았어요 · 데이터는 그대로예요"라고만 안내합니다.
- 앱이 만드는 문구에서는 매수·매도 권유, 호재·악재, 가격 전망 같은 표현을 뺐습니다.

## 묶음별 커밋
| 묶음 | 커밋 |
|---|---|
| 규칙 문서 | `f222000` |
| ① 토대 (값 · 아이콘 · 모션 · 공용 부품 · 셸) | `1fb5286` `9a64b98` |
| ③ 메모 보드 | `f45a83b` |
| ④ 메모 상세 · 새 메모 · AI 연결 / ④-2 근거 상세 | `54fd150` `e3810b4` |
| ⑤ 기업정보 | `ceeb58c` |
| ② 홈 | `d25431c` |
| ⑥ 업데이트 · 내 종목 | `f520299` |
| ⑨-1·2 소개 · 로그인 · 약관 · 첫 시작 | `a18f118` `72d2310` `2fbd063` `dc86001` `71353e5` `60874f5` `0c1011a` `66b7c55` `4ec4af6` `48df523` |
| ⑨-3 MY · 설정 | `9d80da9` `767cd07` `9c4c0c7` `0e90e36` `c5dd2fc` `ea32eeb` `1f34a29` `fc929d1` `c01f3db` |
| ⑧ 스튜디오 | `79c021a` `9e22655` `b18ea59` `d4ea10a` `c9cd9ef` `4963fa1` `c43c5a5` |
| ⑦ 투자 기록 | `a6b8f9b` `f0c508d` |
| ⑩ 마무리 (다크 모드 · 사용법 안내 · 넛지 · 다듬기) | `36f1416` `3f44945` `1ecc7d5` |
| 4단계 전체 점검 | `43c6d8c` `7649f41` · 점검표 · 이 초안 |

`36f1416`(다크 모드)에는 ⑦-7b 투자 기록 편집기 버그 수정도 들어 있습니다. 새로 친 줄바꿈이 아닌데도 블록이 나뉘던 문제입니다.

## 리뷰 때 볼 곳
- **공용 부품**: `ui/shared` (Sheet · ConfirmDialog · PaperBox · MemoEditor · Coach 등), `ui/theme.ts`
- **라우트**: `app/(main)` (탭 · 웹 셸), `app/(detail)` (앱 상세 화면). `.native.tsx`가 앱, `.tsx`가 웹입니다.
- **다크 모드**: 원본처럼 화면 전체를 색 반전합니다(`ui/shared/Dark.tsx`, `ui/shared/darkMode.web.ts`). 로고·사진은 `Keep`으로 원래 색을 유지합니다. iOS에는 다크 줄이 없습니다.
- **store/**: `coach` · `nudge` · `theme` · `journal` · `studioPlayer`. 모두 앱이 켜져 있는 동안만 기억합니다(mock).
- DOM(`document` · `window`)은 `.web.ts(x)` 파일에서만 씁니다.

## 연결 단계에서 할 일
- mock → 실제 API: 메모 · 보드 · 업데이트 · 기업정보 · 투자 기록 · 스튜디오(오디오 · 보고서 · 실험실 · 퀴즈)
- 저장: 사용법 안내를 본 적 있는지, 넛지 닫힘, 다크 설정, 투자 기록
- 결제 · 크레딧 · 플랜 가격(지금은 `[가격]` 자리표시), 내보내기, 피드백 전송, 영구 삭제
- 앱 체크리스트 상세 화면을 새 UI로 추출 (지금은 옛 화면)
- 원본과 다른 곳 전체 목록: `docs/ui-v2-final-check.md`

## 확인 방법
```bash
cd frontend
npm install
npm run typecheck
npm run lint
npx expo start          # 앱: Expo Go(안드로이드) · 웹: w 키
```
- 웹은 1440 · 1280 폭, 앱은 412dp 기준으로 맞췄습니다.
- 흐름: 소개 → 로그인 → 약관 → 종목 고르기 → 첫 메모 → 사용법 안내 → 홈 · 보드 · 메모 · 기업정보 · 업데이트 · 내 종목 · 스튜디오 · 투자 기록 · MY/설정 → 로그아웃
- 다크 모드: 앱은 MY › 화면, 웹은 사이드바 아래 스위치입니다.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
