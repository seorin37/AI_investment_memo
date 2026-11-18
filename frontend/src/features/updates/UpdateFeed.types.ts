import type { NativeScrollEvent, NativeSyntheticEvent } from 'react-native';
import type { UpdateType } from '@/types/models';

/** 최신 업데이트 탭의 소식 1줄 */
export interface FeedItem {
  id: string;
  type: UpdateType; // 'disclosure' | 'news' | 'price'
  /** 주가는 'MM.DD 종가 +7.1%' 형식 */
  title: string;
  ago: string; // '2시간 전'
  unread: boolean;
}

/** 종목별 카드 */
export interface FeedStock {
  stock_code: string;
  name: string;
  market: string;
  logo_text: string;
  logo_bg: string;
  logo_fg?: string;
  status: 'holding' | 'watching';
  items: FeedItem[];
}

export interface UpdateFeedProps {
  stocks: FeedStock[];
  /** 위 종목 칩에서 고른 종목 (null = 전체) */
  selected_stock: string | null;
  onSelectStock: (stock_code: string | null) => void;
  onOpenStock: (stock_code: string) => void;
  onOpenItem: (stock_code: string, item_id: string) => void;
  /** AI 사용량을 다 써서 새 소식 찾기가 멈췄을 때 */
  ai_paused?: boolean;
  /** 처음 불러오는 중 (빛줄기 뼈대 #079) */
  loading?: boolean;
  /** 당겨서 새로고침 (#085) */
  refreshing?: boolean;
  onRefresh?: () => void;
  /** 스크롤 위치를 호스트로 (Lucian #332 큰 제목 접기 · TopBar 아래 선): useLargeTitle().onScroll 을 넘김 */
  onScroll?: (e: NativeSyntheticEvent<NativeScrollEvent>) => void;
}
