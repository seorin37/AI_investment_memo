import type { NativeScrollEvent, NativeSyntheticEvent } from 'react-native';
/** 모바일 홈 (기존 웹용 HomeScreen 과 이름이 겹치지 않게 MobileHome) */

export interface HomeMarketItem {
  key: string; // 'kospi' | 'kosdaq' | 'usd'
  name: string; // '코스피'
  value: number;
  change: number;
  change_rate: number; // %
  closes: number[]; // 작은 선 (최근 종가)
  close_date: string; // 'MM.DD'
}

export interface HomeStockUpdate {
  stock_code: string;
  name: string;
  logo_text: string;
  logo_bg: string;
  logo_fg?: string;
  status: 'holding' | 'watching';
  new_count: number;
}

export interface HomeNews {
  id: string;
  time: string; // '12:48'
  title: string;
  source: string; // '한국경제'
}

export interface MobileHomeProps {
  user_name: string;
  /** 오늘 내 메모에 붙은 새 소식 수 (0이면 "새 소식이 없어요") */
  new_count: number;
  holding_count: number;
  watching_count: number;
  ai_memo_count: number;
  market: HomeMarketItem[];
  /** 시장 정보를 못 불러왔을 때 */
  market_error?: boolean;
  /** [다시 시도]를 누른 뒤 불러오는 중 (돌개가 돎) */
  market_retrying?: boolean;
  /** 당겨서 새로고침 (Lucian #085) */
  refreshing?: boolean;
  onRefresh?: () => void;
  /** 아래 탭 위 검정 알약 넛지 (#252) — 예: "이번 주 내 종목, 한 장으로 볼까요?" · 없으면 숨김 */
  nudge?: { text: string; onPress: () => void; onClose: () => void } | null;
  updates: HomeStockUpdate[];
  news_total_today: number;
  news: HomeNews[];
  onOpenUpdates: () => void;
  onOpenMarket: (key: string) => void;
  onRetryMarket: () => void;
  onOpenStockUpdates: (stock_code: string) => void;
  onOpenNews: (id: string) => void;
  /** 스크롤 위치를 호스트로 (Lucian #332 큰 제목 접기 · TopBar 아래 선): useLargeTitle().onScroll 을 넘김 */
  onScroll?: (e: NativeSyntheticEvent<NativeScrollEvent>) => void;
}
