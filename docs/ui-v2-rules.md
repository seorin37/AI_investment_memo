# UI v2 추출 규칙 (2026-11-19)

## 0. 원본과 똑같이 (가장 중요)
- 원본을 요약하거나 단순하게 바꾸지 말 것. 다시 디자인하지 말 것
- 레이아웃 구조, 요소 순서, 정렬, 색, 글자 크기·굵기, 간격, 라운드, 구분선, 테두리, 배경을 원본 값 그대로
- 그림 요소(막대, 점, 슬라이더, 게이지, 그래프, 아이콘, 배지)를 빼지 말 것.
  HTML·CSS로 만든 것은 View 조합이나 react-native-svg로 같은 모양으로
- 원본 CSS 숫자(px, 색 코드)를 그대로. 비슷한 값으로 바꾸지 말 것
- 어쩔 수 없이 다르게 만든 곳은 전부 "원본과 다른 곳" 목록에
- 예외: 문구 규칙(7번)으로 바뀌는 문구. 이것도 목록에

## 1. 기술
- expo 58 / expo-router 58 / react 19 / react-native 0.88 / react-native-web / typescript 6
  (정확한 버전은 frontend/package.json)
- 부품: View, Pressable, ScrollView, FlatList, Image, Modal, StyleSheet, Animated, Easing,
  PanResponder, KeyboardAvoidingView
- 글자: react-native의 Text·TextInput 대신 '@/components/ui/AppText'의 Text·TextInput·AnimatedText
  (fontWeight 400·500·600·700을 Pretendard 굵기로 바꿔 줌). fontFamily 직접 지정 금지
- 추가 패키지: react-native-svg, react-native-safe-area-context, expo-font만. 새 패키지 설치 금지
- Tailwind/className, .css 파일, Vite 금지

## 2. 웹·앱이 다른 부분
- 화면 자체가 다르면 화면을 따로: ui/screens/<기능>/app/, ui/screens/<기능>/web/
- 공통 부품인데 동작만 다르면 같은 이름 두 파일 + 같은 props: <부품>.native.tsx / <부품>.web.tsx
- 한두 줄 차이면 Platform.OS === 'web'
- 앱 전용 동작(줄 밀기, 꾹 눌러 고르기, 시트 끌어 닫기, 하드웨어 뒤로가기, 당겨서 새로고침, 탭바 숨기기)은
  앱 화면이나 .native.tsx에
- 웹 전용 동작(hover, 우클릭, 키보드 단축키, 메모 편집기, 마우스 끌기)은 웹 화면이나 .web.tsx에.
  HTML 요소·document·window는 .web.tsx 안에서만

## 3. 폴더 (새 코드는 전부 frontend/src/ui/ 아래)
- ui/shared/ 공통 부품, ui/motion/ 모션, ui/icons/ 아이콘
- ui/layout/app/ (BottomTabBar 탭 5개: 홈·업데이트·내 종목·투자 기록·스튜디오, TopBar)
- ui/layout/web/ (Sidebar 펼침 250 / 접힘 72px, WebShell)
- ui/screens/<기능>/app|web/<화면>.tsx + <화면>.types.ts + <화면>.mock.ts
- 같은 데이터를 쓰는 웹·앱 화면은 같은 props 타입 공유
- 화면 파일에 셸(사이드바·탭바·상단 바) 넣지 말 것
- import는 '@/ui/...', PascalCase, named export
- 옛 화면(src/features/, src/components/motion/, src/components/layout/, src/components/mobile/)은
  참고·수정·재사용 금지

## 4. 데이터
- 데이터는 props로만, 버튼 동작은 콜백 props로만 (onSave, onDelete, onToggleAi 등)
- 금지: API 호출(fetch·axios), API 명세, 가상 서버, localStorage·AsyncStorage, 로그인·세션 처리, .env
- 예시 데이터는 .mock.ts에 고정 값만
- 타입: '@/types/models' 재사용. 필드는 snake_case.
  메모: id 문자열, title, body, color, pinned, ai_linked, ai_linked_at, unread_updates, created_at, updated_at
  체크리스트 항목: id 문자열, text, done / 종목: stock_code, name, market, status("holding"|"watching")
- 메모 입력은 한 칸, 첫 줄이 제목: '@/lib/memoText'의 splitMemo

## 5. 지난번에 나온 문제 피하기
- ref 타입: TextInputInstance, ScrollViewInstance (RN 0.88)
- lint(react-hooks 7): 렌더 중 ref 읽기·쓰기, effect 안 setState, 렌더 중 Math.random 피하기.
  애니메이션 값은 useState(() => new Animated.Value()). 정말 필요한 모션 파일만 그 파일에서 규칙 끄기 + 이유 주석
- JSX 글자 안 따옴표 이스케이프, 같은 파일 import 두 줄 금지
- 줄 밀기(SwipeRow)를 Pressable로 감싸지 말 것
- BottomSheet 끌기는 터치 시작부터 (onStartShouldSetPanResponder)
- 탭바 숨김 때 높이 접기 (빈 공간 금지)
- 안드로이드 뒤로가기: 시트 → 열린 줄 → 고르기 → 화면 순
- 그림자는 shadow*와 elevation 함께, 배경색 지정, overflow hidden 부모 바로 안에 두지 않기

## 6. 안드로이드에서 원본과 같게
- 글자마다 fontSize와 lineHeight 함께
- 글자 칸·칩·버튼 height 고정 금지 (minHeight + paddingVertical)
- 한 줄 글자: numberOfLines={1} + flexShrink: 1
- 고정 px 폭 금지 (flex, %, useWindowDimensions). 412·360 모두
- safe area insets, 입력 화면은 KeyboardAvoidingView
- 한국어 줄바꿈은 어절 단위, 1px 구분선은 원본 두께·색 그대로

## 7. 문구
- 금지: 매수·매도 권유, 호재·악재, 가격 전망, "장중", "기대감에 강세"류 해석
- 주가는 "MM.DD 종가 기준"

## 8. 디자인 기준 (원본과 다르면 원본 우선)
- 웹: 사이드바 250/72, 배경 #FFFFFF, 페이지 #FDFDFD, Hover #F9F9F9, 선택 배경 #FBF8FF, 선택 글자 #6A42AB
- 앱: 폭 412, 좌우 16, 카드 간격 14, 라운드 20(메모 16), 탭바 80, 터치 44+, 배경 #F3F4F6,
  주요 선택 #8569E3, 상승 #E5484D, 하락 #2F6BDB
- 모션: 화면 전환·페이드 사용, 스와이프 허용, 동작 줄이기 설정 존중

## 9. 묶음마다 확인
- npm run typecheck, npm run lint 통과
- .web.tsx 밖에서 <div, <span, className, react-dom, document., window. 0
- fetch(, axios, localStorage, AsyncStorage, process.env 0
- react-native Text·TextInput 직접 import 0
- 원본 캡처와 우리 화면 나란히 비교 (눈 + CSS 값 대조), 차이 표: 고침 / 의도 / 못 고침+이유
