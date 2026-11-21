# UI 코드 추출 요청서 (MEMO'S frontend용)

> 이 문서 전체를 Claude Code에 그대로 붙여 넣고, 맨 아래 "추출 대상"에 화면 이름을 적어서 요청해 주세요.
> 목표: 받은 코드를 `frontend/`에 **복사만 해서** 바로 쓸 수 있게 하는 것. (지난번처럼 Vite 프로젝트로 받으면 다시 옮겨야 합니다.)
> 기준 레포 상태: 2026-11-18 `dev` 브랜치 `frontend/`

---

## 0. Claude Code에게 하는 요청

지금 만든 인터랙티브 UI를 아래 조건에 맞춰 **React Native(Expo) 컴포넌트 코드**로 다시 작성해 줘.
화면마다 **웹 UI 파일 하나, 앱 UI 파일 하나, 공통 props 타입 파일 하나**를 만들어 줘.
조건을 못 지키는 부분은 억지로 맞추지 말고 "구현 못 한 부분" 목록에 적어 줘.

---

## 1. 기술 조건 (반드시 지킬 것)

| 항목 | 우리 버전 (package-lock 기준) |
|---|---|
| Expo SDK | `expo` 58.0.16 (`~58.0.16`) |
| Expo Router | 58.0.24 |
| React / React Native | 19.3.0 / 0.88.0 |
| react-native-web | 0.21.4 |
| TypeScript | 6.0.3, `strict: true` |

**쓰면 안 되는 것**
- Vite, `index.html`, `react-dom`, `document`/`window` 직접 사용
- `div`, `span`, `p`, `button`, `img`, `input` 같은 HTML 태그
- `.css` / `.scss` 파일, `className`, Tailwind, NativeWind, styled-components
- 웹 전용 라이브러리 (shadcn, Radix, lucide-react, framer-motion 등)
- `position: 'fixed'`, CSS `transition`, `:hover` 같은 CSS 문법

**써야 하는 것**
- `react-native`의 `View`, `Text`, `Pressable`, `ScrollView`, `FlatList`, `TextInput`, `Image`, `Modal`, `Animated`
- 스타일은 `StyleSheet.create` 또는 style 객체만

**쓸 수 있는 패키지 (우리 `package.json`에 이미 있는 것만)**
- `react-native-svg` 15.16.0: 아이콘·차트 그릴 때
- `react-native-safe-area-context` 5.10.1
- `expo-router`: `Link`, `useRouter` (화면 이동이 꼭 필요할 때만)

위 목록 밖의 패키지는 쓰지 마. 정말 필요하면 코드에 넣지 말고 "필요한 패키지" 목록에 이름과 이유를 적어 줘.
- `react-native-reanimated`와 `react-native-gesture-handler`는 우리 `package.json`에 직접 들어 있지 않아. 그러니 쓰지 마.
- 애니메이션은 `react-native`의 `Animated`, 드래그는 `PanResponder`로 해 줘.
- `@expo/vector-icons`, `expo-linear-gradient`, `expo-blur`, `expo-image`, `expo-haptics`도 설치되어 있지 않아.

---

## 2. 웹 / 앱 분리 방식

화면(또는 큰 부품) 하나마다 아래 **4개 파일**을 같은 폴더에 만들어 줘.

```
<이름>.types.ts     공통 props 타입 (웹·앱 둘 다 이 타입을 씀)
<이름>.web.tsx      웹 UI (브라우저, 데스크톱 기준)
<이름>.native.tsx   앱 UI (iOS·Android, 412 기준)
<이름>.tsx          한 줄짜리 타입 확인용 파일 (아래 그대로)
```

`<이름>.tsx` 내용은 이것만 넣어 줘.
```ts
// 실제 화면은 Metro가 플랫폼에 맞게 .web.tsx / .native.tsx 를 고른다. 이 파일은 tsc 타입 확인용.
export * from './<이름>.native';
```
이 파일이 필요한 이유:
- 우리 tsconfig에는 `moduleSuffixes` 설정이 없어.
- 그래서 `.web`/`.native`만 있으면 `import ... from './<이름>'`을 `tsc`가 찾지 못해.

**이름 규칙** (우리 레포 규칙)
- 컴포넌트 파일과 컴포넌트 이름은 PascalCase로 해 줘. 예: `UpdatesList.web.tsx` 안에 `export function UpdatesList`.
- **named export만** 써 줘. `export default`는 쓰지 마. 우리 레포는 라우트 파일에서만 default를 써.
- 웹 파일과 앱 파일은 **같은 이름, 같은 props 타입**으로 export해야 해.
  ```ts
  // UpdatesList.web.tsx 와 UpdatesList.native.tsx 둘 다
  import type { UpdatesListProps } from './UpdatesList.types';
  export function UpdatesList(props: UpdatesListProps) { ... }
  ```

**폴더 위치**: `frontend/src/features/<기능>/` 아래.
- 기존 기능 폴더: `home`, `board`, `company`, `journal`, `settings`, `stock`, `trash`, `updates`, `feedback`
- 새 기능이면 영문 소문자 폴더를 새로 만들어 줘. 예: `studio`

---

## 3. 화면 단위: 컴포넌트만 (라우트·레이아웃 제외)

- **`src/app/` 라우트 파일은 만들지 마.** 우리 라우트 파일은 컴포넌트를 import하는 얇은 파일이고, 연결은 우리가 해.
  - 예: `src/app/(main)/updates/index.tsx`는 `export default UpdatesOverview;` 한 줄이야.
  - 라우트 파일을 플랫폼별로 나누면 기본 파일도 따로 있어야 해서 번거로워(Expo Router 규칙).
- **이미 있는 것은 만들지 마.**
  - 사이드바: `Sidebar.tsx`, 펼침 250 / 접힘 72
  - 모바일 상단 바·드로어, 앱 골격: `AppShell.tsx`
  - 페이지 스크롤 틀: `Page.tsx` (`Page`, `PageHeader`)
  - 전역 모달 자리: `ModalHost.tsx`
  - 토스트
  - 로그인·폰트 로딩·데이터 캐시 설정
- 화면 컴포넌트는 **사이드바 오른쪽 본문 영역**만 그려 줘. 바깥 스크롤 틀(`Page`)도 우리가 감싸.
  - 단, 화면 안쪽의 가로 스크롤이나 목록 스크롤은 컴포넌트 안에 넣어도 돼.
- 팝업은 팝업 **내용 컴포넌트**만 만들어 줘. 열고 닫는 상태는 `open`, `onClose` props로 받아.

---

## 4. 데이터: 하드코딩 금지, props로 받기

- 화면에 보이는 데이터(종목, 메모, 업데이트, 숫자, 날짜)는 **전부 props로** 받아 줘.
- 버튼 동작은 `onXxx` 콜백 props로 받아 줘. 예: `onOpenMemo(id: string)`, `onToggleAi(id: string, on: boolean)`.
- 컴포넌트 안에서 API 호출, `fetch`, 전역 상태 저장소를 쓰지 마. 데이터 연결은 우리가 해.
  - 우리 쪽 연결 코드: `@/hooks/queries`, `@/api`, `@/store/*`
- 화면 안의 잠깐 상태(탭 선택, 펼침, 입력 중인 글자)는 `useState`로 컴포넌트 안에 둬도 돼.
- **props 타입은 우리 `src/types/models.ts` 타입을 그대로** 써 줘. 필드 이름은 snake_case이고 바꾸지 마.
  - 새 이름을 만들지 말고 `import type { Memo, MyStock } from '@/types/models';`처럼 가져와 줘.

자주 쓰는 타입 (필드 일부):

| 타입 | 주요 필드 |
|---|---|
| `MyStock` | `code`, `name`, `market`(`'KOSPI'｜'KOSDAQ'｜'KONEX'`), `status`(`'holding'｜'watching'`), `tags`, `unread_updates`, `added_at` |
| `Quote` | `code`, `price`, `change`, `change_pct`, `as_of`, `spark: number[]` |
| `Memo` | `id`, `kind:'memo'`, `stock_code`, `title`, `body`, `tags`, `color`(`'yellow'｜'blue'｜'pink'｜'green'｜'purple'`), `pinned`, `ai_linked`, `price_conditions`, `unread_updates`, `created_at`, `updated_at` |
| `Checklist` | `id`, `kind:'checklist'`, `stock_code`, `title`, `items: { id, text, done }[]` |
| `ReferenceBoard` | `id`, `kind:'reference'`, `links: { id, title, url, ref_type, source }[]` |
| `BoardItem` | `Memo ｜ Checklist ｜ ReferenceBoard` |
| `AiUpdate` | `id`, `stock_code`, `stock_name`, `type`(`'disclosure'｜'news'｜'price'`), `title`, `headline`, `summary`, `source`, `url`, `published_at`, `memo_id`, `memo_title`, `memo_version`, `read` |
| `MarketUpdate` | `id`, `stock_code`, `stock_name`, `type`, `title`, `source`, `url`, `published_at` |
| `TimelineEntry` | `kind`이 `'update'｜'memo_edit'｜'memo_created'｜'ai_linked'`인 묶음 타입 |
| `JournalEntry` | `id`, `title`, `stock_code`, `stock_name`, `blocks`, `created_at`, `updated_at` |
| `User` | `id`, `name`, `bio`, `avatar_url`, `email`, `providers` |
| `TrashItem` | `id`, `kind`, `title`, `context`, `deleted_at` |

날짜는 모두 ISO 문자열(`'2026-11-17T09:30:00+09:00'`)로 받아.

- models.ts에 맞는 타입이 없으면 `<이름>.types.ts` 안에 새 타입을 만들어 줘.
- 새 타입을 만들었다면 "새로 만든 타입" 목록에 적어 줘. 우리가 models.ts에 옮길지 정할게.
- **예시 데이터는 `<이름>.mock.ts`로 따로** 만들어 줘. 컴포넌트 파일 안에는 예시 데이터를 넣지 마.
  ```ts
  // UpdatesList.mock.ts
  import type { AiUpdate } from '@/types/models';
  export const UPDATES_LIST_MOCK: AiUpdate[] = [ ... ];
  ```

---

## 5. 스타일: 토큰 import해서 쓰기

색·간격·라운드·폰트는 HEX나 숫자를 직접 쓰지 마.
`import { colors, radius, space, layout, fonts, shadow } from '@/theme/tokens';`로 가져와서 써 줘.

**글자는 `Text` 대신 우리 `T` 컴포넌트**로 써 줘. Pretendard 굵기 처리가 들어 있어.
```tsx
import { T } from '@/components/ui/Text';
<T size={15} weight="bold" color={colors.textSub}>내용</T>
// weight: 'regular' | 'medium' | 'semibold' | 'bold'
```
폰트는 **Pretendard**야(Noto Sans KR 아님). 폰트 로딩은 우리가 이미 해. `fonts.regular`='Pretendard-Regular', `medium`, `semibold`, `bold`.

### 5-1. 우리 토큰 (`src/theme/tokens.ts`) 주요 값

| 토큰 | 값 | 용도 |
|---|---|---|
| `colors.page` | `#FDFDFD` | 페이지 배경 |
| `colors.surface` | `#FFFFFF` | 카드·면 |
| `colors.surfaceMuted` | `#F9F9F9` | 사이드바 검색, 입력칸 |
| `colors.surfaceSubtle` | `#F5F6F8` | 위젯 안쪽 행 |
| `colors.surfaceWarm` | `#F5F3EF` | 메모 팝업 세그먼트·본문 박스 |
| `colors.surfaceCanvas` | `#F4F5F7` | 홈 사용자화 캔버스 |
| `colors.border` / `borderSoft` / `borderStrong` | `#E5E8EB` / `#EEF0F3` / `#D9DEE7` | 선 |
| `colors.text` / `textStrong` / `textBody` | `#15171A` / `#191F28` / `#333D4B` | 글자 |
| `colors.textSub` / `textMuted` / `placeholder` | `#6B7684` / `#9AA3B2` / `#B0B8C1` | 보조 글자 |
| `colors.brand` | `#6A42AB` | 사이드바 활성 글자 (주요 보라) |
| `colors.brandSoft` / `brandLine` | `#F4EFFD` / `#986BEE` | 활성 배경 / 보라 선 |
| `colors.blue` | `#477BFF` | 링크·기본 버튼 |
| `colors.teal` | `#1AB8A2` | AI 연결 켜짐 |
| `colors.danger` / `dangerSoft` | `#E5484D` / `#FDECEC` | 삭제·오류 |
| `colors.up` / `colors.down` | `#F04545` / `#3B82F5` | 상승 / 하락 (설정에 따라 바뀜) |
| `radius` | `xs 6, sm 8, md 12, lg 16, xl 20, xxl 24, pill 999` | 라운드 |
| `space` | `xxs 4, xs 8, sm 12, md 16, lg 20, xl 24, xxl 32, xxxl 40` | 간격 |
| `layout.sidebarWidth` / `sidebarCollapsed` | `250` / `72` | 사이드바 |
| `layout.contentMaxWidth` / `pagePaddingX` | `1180` / `32` | 본문 최대 폭 / 좌우 여백 |
| `layout.breakpoints` | `mobile 768, desktop 1100` | 화면 폭 기준 |
| `shadow.card` / `pop` / `modal` | 그림자 묶음 (iOS shadow + Android elevation) | `...shadow.card`로 펼쳐 씀 |

- 메모 색: `memoPalette[memo.color]`의 `bg`, `border`, `ink`를 써 줘.
- 업데이트 배지: `updateBadge[type]`(`label`, `bg`, `fg`)를 써 줘.
- 상승/하락 색은 `colors.up`/`colors.down`을 직접 쓰지 마. 대신 `upColor`, `downColor` props로 받아 줘. 우리가 설정값을 반영해서 넘길게.

### 5-2. 웹 UI 기준 (`.web.tsx`)

| 항목 | 값 | 토큰 |
|---|---|---|
| 사이드바 | 250 / 접힘 72 (우리 쪽에 있음, 만들지 말 것) | `layout.sidebarWidth`, `layout.sidebarCollapsed` |
| 페이지 배경 | `#FDFDFD` | `colors.page` |
| 입력·검색 배경 | `#F9F9F9` | `colors.surfaceMuted` |
| 연보라 배경 | `#FBF8FF` | **토큰 없음** → `colors.brandTint` 이름으로 써 줘 (아래 5-4) |
| 주요 보라 | `#6A42AB` | `colors.brand` |
| 본문 좌우 여백 | 32 | `layout.pagePaddingX` |

### 5-3. 앱 UI 기준 (`.native.tsx`)

| 항목 | 값 | 토큰 |
|---|---|---|
| 기준 화면 폭 | 412 | **토큰 없음**. 폭을 고정하지 말고 `flex`로 늘어나게 짜 줘 |
| 좌우 여백 | 16 | `space.md` |
| 카드 라운드 | 20 | `radius.xl` |
| 메모 카드 라운드 | 16 | `radius.lg` |
| 화면 배경 | `#F3F4F6` | **토큰 없음** → `colors.appBg` 이름으로 써 줘 |
| 주요 선택 색 | `#8569E3` | **토큰 없음** → `colors.selectPrimary` 이름으로 써 줘 |
| 터치 영역 | 44 이상 | **토큰 없음**. 누르는 요소는 높이·너비 44 이상, 작으면 `hitSlop`로 넓혀 줘 |

### 5-4. 아직 없는 토큰

위에서 "토큰 없음"인 색은 지금 정한 이름으로 `colors.xxx`처럼 import해서 써 줘. 그리고 전달할 때 아래처럼 목록으로 알려 줘. 우리가 `tokens.ts`에 추가할게.
```
colors.brandTint     = '#FBF8FF'   웹 연보라 배경
colors.appBg         = '#F3F4F6'   앱 화면 배경
colors.selectPrimary = '#8569E3'   앱 주요 선택
(그 밖에 새로 필요한 값: 이름 = 값 · 용도)
```
목록에 없는 새 색이 필요하면 새 이름을 붙여서 같은 목록에 추가해 줘. HEX를 코드에 직접 쓰지 마.

---

## 6. import 경로

경로 별칭은 `@/` = `frontend/src/` 하나뿐이야. 다른 폴더 파일은 모두 `@/`로 import해 줘. 같은 폴더 파일만 `./`를 써.

| 가져올 것 | import |
|---|---|
| 토큰 | `import { colors, radius, space, layout, fonts, shadow, memoPalette, updateBadge } from '@/theme/tokens';` |
| 글자 | `import { T } from '@/components/ui/Text';` |
| 기본 부품 | `import { Button, IconButton, Hoverable, Card, Badge, CountBadge, PillTabs, Segmented, Switch, AiToggle, CircleCheck, SquareCheck, TextField, TextArea, Select, Avatar, Divider, EmptyState, Loading } from '@/components/ui/primitives';` |
| 아이콘 | `import { Icon } from '@/components/icons/Icon';` → `<Icon name="bell" size={20} color={colors.text} />` |
| 모델 타입 | `import type { ... } from '@/types/models';` |
| 날짜·숫자 표기 | `import { mmdd, num, won, signed, signedPct, relative } from '@/lib/format';` |

- **기본 부품은 새로 만들지 말고 위 것을 먼저** 써 줘. 버튼, 탭, 토글, 체크, 입력칸, 배지, 빈 화면 같은 것들이야.
- 아이콘 `name`으로 쓸 수 있는 값:
  `home refresh fileText file briefcase trash settings search plus minus chevronDown chevronUp chevronLeft chevronRight arrowRight arrowLeft x check pin link external pencil edit bell bellRing sparkles panelLeft logout user monitor barChart plug database info help helpSquare grip resize calendar newspaper trendingUp candle paperclip table listChecks markup undo star grid sliders menu more filePlus history scale flag copy download camera bold`
- 목록에 없는 아이콘이 필요하면 `react-native-svg`로 그린 SVG path를 "새 아이콘" 목록에 따로 적어 줘.
- 레포가 없는 환경에서 작업한다면 위 import는 그대로 쓰고, 이름이 맞는지만 이 문서와 대조해 줘.

---

## 7. 상호작용: React Native에서 다르게 동작하는 것

| 효과 | 웹 (`.web.tsx`) | 앱 (`.native.tsx`) |
|---|---|---|
| hover | `Hoverable`의 `hoverStyle` 사용 (react-native-web이 hovered 상태를 줌) | hover 없음. `pressedStyle`(누를 때 모양)로 대신 |
| 커서 모양 | 꼭 필요할 때만 `{ cursor: 'pointer' } as object` (기본 부품은 이미 처리) | 없음 |
| 그림자 | `...shadow.card` / `pop` / `modal` | 같은 토큰 (Android는 `elevation`으로 자동 처리) |
| 애니메이션 | `Animated` (`useNativeDriver: false`) | `Animated` (`useNativeDriver: true` 가능한 곳만) |
| CSS transition·keyframes | 쓰지 말 것. `Animated.timing`으로 다시 만들거나 빼고 목록에 적기 | 같음 |
| 스크롤 | 긴 목록은 `FlatList`, 짧은 것은 `ScrollView` | 같음. 가로 스크롤은 `horizontal` |
| 고정 위치 (sticky, fixed) | `position: 'absolute'`로 대신. sticky 헤더는 `stickyHeaderIndices` | 같음 |
| 드래그 | `PanResponder` | 같음 |
| 더블클릭·우클릭·키보드 단축키 | 가능하면 버튼으로 대신. 못 하면 목록에 적기 | 길게 누르기(`onLongPress`)로 대신 |
| 그라데이션·흐림(blur)·backdrop-filter | 쓰지 말 것 (패키지 없음) → 단색으로 대신하고 목록에 적기 | 같음 |
| 글자 줄바꿈 | `T`가 이미 한국어 단어 단위 줄바꿈 처리 | 길면 `numberOfLines`로 자르기 |
| 입력칸 포커스 테두리 | `TextField`/`TextArea` 사용 (처리돼 있음) | 같음 |
| 안전 영역 (노치) | 필요 없음 | 화면 단위면 우리 `AppShell`이 처리. 바닥 고정 버튼만 `useSafeAreaInsets()` 사용 |

**구현 못 한 효과**는 지우지 말고 "구현 못 한 부분" 목록에 적어 줘. 적을 때는 원래 효과, 대신 한 것, 필요한 패키지(있다면)를 함께 써 줘.

---

## 8. 문구 규칙

**쓰면 안 되는 표현**
- 매수·매도 권유. 예: "지금 사세요", "매도 추천", "담아 두세요"
- 호재·악재 판단. 예: "호재", "악재", "긍정적 신호", "위험 신호"
- 가격 전망. 예: "오를 것으로 보여요", "목표가", "상승 여력"
- **"장중"**. 우리는 실시간 시세가 아니라 종가만 보여 줘.
- 수익 보장 표현

**주가 표기**
- 가격 옆에는 항상 **"MM.DD 종가 기준"**을 붙여 줘. 예: `11.17 종가 기준`.
- 코드에서는 `` `${mmdd(quote.as_of)} 종가 기준` ``처럼 만들어 줘.
- "현재가", "실시간", "지금 가격" 같은 말은 쓰지 마.
- 예시 데이터에서도 위 규칙을 지켜 줘.

---

## 9. 전달 형식

아래 순서로 한 번에 전달해 줘.

### 9-1. 폴더 구조 (트리)
```
frontend/src/features/studio/
├─ AudioPlayer.types.ts
├─ AudioPlayer.tsx            (한 줄 타입 확인용)
├─ AudioPlayer.web.tsx
├─ AudioPlayer.native.tsx
├─ AudioPlayer.mock.ts
└─ ...
```

### 9-2. 화면별 파일 목록
| 화면 (시안 이름) | 컴포넌트 이름 | 파일 | 웹/앱 둘 다 있음? |
|---|---|---|---|

### 9-3. 사용한 패키지
- 우리 목록에서 쓴 것: 예) `react-native-svg`
- 새로 필요한 것 (코드에는 넣지 않음): 이름 · 이유 · 대신 쓸 방법

### 9-4. props 타입 설명
컴포넌트마다 props 이름, 타입, 뜻, 꼭 필요한지 여부를 표로 적어 줘. models.ts 타입을 쓴 것과 새로 만든 타입을 구분해 줘.

### 9-5. 새로 필요한 토큰·아이콘·타입
5-4 형식으로 토큰, 6장 형식으로 아이콘, 4장 형식으로 타입을 적어 줘.

### 9-6. 구현 못 한 부분
| 화면 | 원래 효과·기능 | 대신 한 것 | 이유 |
|---|---|---|---|

### 9-7. 화면 캡처 (가능하면)
원래 UI와 추출한 코드를 실행한 화면을 나란히 첨부해 줘.

---

## 10. 추출 전 자체 점검 (전달 전에 확인해 줘)

- [ ] `react-dom`, `index.html`, `vite` 문자열이 없음
- [ ] `<div`, `<span`, `<p `, `<button`, `<img`, `<input` 태그가 없음. `tsc`는 이 태그를 못 잡으니 직접 검색해 줘
- [ ] `.css` 파일, `className`, `tailwind`, `styled` 가 없음
- [ ] `import`한 패키지가 1장 "쓸 수 있는 패키지"와 `react`, `react-native`, `@/...` 경로뿐임
- [ ] 화면마다 `.types.ts`, `.web.tsx`, `.native.tsx`, 한 줄 `.tsx`, `.mock.ts`가 다 있음
- [ ] 웹 파일과 앱 파일이 **같은 이름으로 named export**하고 같은 props 타입을 씀. `export default` 없음
- [ ] `src/app/` 라우트 파일, 사이드바, 탭바, 앱 골격을 만들지 않음
- [ ] 컴포넌트 안에 예시 데이터, `fetch`, API 호출이 없음 (예시 데이터는 `.mock.ts`에만)
- [ ] props 필드 이름이 models.ts와 같음 (snake_case)
- [ ] HEX 색(`#`)이 컴포넌트 파일에 없음. 모두 `colors.xxx` (새 토큰은 9-5에 적음)
- [ ] 글자는 모두 `T` 컴포넌트, `fontFamily` 직접 지정 없음
- [ ] 앱 파일의 누르는 요소가 44 이상 (또는 `hitSlop`)
- [ ] 금지 표현(8장)이 없고, 가격 옆에 "MM.DD 종가 기준"이 있음
- [ ] (레포가 있다면) `frontend/`에서 `npx tsc --noEmit`, `npx expo lint`를 오류 없이 통과

검색 예시 (레포가 있으면 `frontend/`에서):
```bash
grep -rnE "react-dom|<div|<span|<button|<img|<input|className|\.css|tailwind|export default|#[0-9A-Fa-f]{6}|장중|호재|악재|매수|매도" src/features/<기능>/
```

---

## 추출 대상 (요청할 때 채워서 보내기)

- 화면 목록: 
- 기능 폴더 이름 (`src/features/____`): 
- 웹/앱 둘 다 필요한지, 하나만 필요한지: 
