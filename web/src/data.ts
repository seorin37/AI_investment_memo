/* 화면에서 쓰는 모양(뷰 타입)과 디자인 상수만 둬요. 실제 데이터는 api/ 에서 와요. */
import type { ColorKey, Hold, Journal as JournalRaw, TrackItem, UpKind } from "./api/types";
export type { ColorKey, Hold, UpKind } from "./api/types";

/* dk: 다크 모드 메모지 (11.18) — 밝은 파스텔은 어두운 화면에서 눈이 부셔서, 같은 색 계열의 어둡고 차분한 종이로 바꿔요.
   글자는 밝은 색으로 바뀌어요 (theme.css .memo-card). 값은 다크 화면 필터를 거친 뒤 실제로 보이는 색 기준 */
export const PAPER: Record<ColorKey, { bg: string; accent: string; label: string; dk: { bg: string; accent: string } }> = {
  yellow: { bg: "#fceaaa", accent: "#efbf2a", label: "노랑", dk: { bg: "#5f5128", accent: "#b39339" } },
  green: { bg: "#cdefd9", accent: "#2fae68", label: "초록", dk: { bg: "#2a5240", accent: "#3f9a66" } },
  blue: { bg: "#cfe0ff", accent: "#3d73f0", label: "파랑", dk: { bg: "#2b4268", accent: "#5683de" } },
  purple: { bg: "#d2beff", accent: "#7046f5", label: "보라", dk: { bg: "#433870", accent: "#8c70e6" } },
  pink: { bg: "#f7c6f0", accent: "#d62bc4", label: "분홍", dk: { bg: "#5e2d57", accent: "#c25ab0" } },
};
/* 메모지 배경 (테마 따라 자동으로 바뀌는 CSS 변수, theme.css). keep: .dk-keep 안쪽 요소일 때 */
export const paperBg = (c: ColorKey, keep = false) => `var(--${keep ? "pk" : "pp"}-${c})`;
/* 지금 테마에 맞는 메모지 색 */
export const paper = (c: ColorKey, dark: boolean) => (dark ? { ...PAPER[c], ...PAPER[c].dk } : PAPER[c]);

/* 내 종목 (종목 정보 + 시세 + 보유/관심) */
export type Stock = { stock_code: string; name: string; short: string; logo: string; logo_bg: string; logo_ink?: string; hold: Hold; market: string; sector: string; financial: boolean; price: number; chg: number; pct: number; as_of: string; seed: number;
  priced?: boolean /* false = 가격 없음(API 모드, 시세 API 없음) → 화면은 "—". api.market.price 참고 */ };

/* 메모 (보드·팝업에서 쓰는 모양) */
export type TL = { kind: UpKind | "edit" | "first" | "start"; at: string; date: string; title?: string; body?: string; src?: string; url?: string; old?: { when: string; title: string; body: string } };
export type Memo = {
  id: number; stock_code: string; date: string; created_at: string; title: string; body: string; color: ColorKey;
  ai: boolean; pinned: boolean; pinned_at?: number; badge: number; col: number;
  tracks?: string; track_items?: TrackItem[]; timeline?: TL[]; news: number;
};
export type Journal = JournalRaw & { date: string; full: string };
export type CheckItem = { id: number; t: string; d: boolean };
