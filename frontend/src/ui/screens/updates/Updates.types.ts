import type { ReactNode } from 'react';
import type { MemoColor } from '@/types/models';
import type { FeedKind, MemoFeedItem } from '@/ui/screens/memo/MemoDetail.types';

/** 업데이트 한 건 = ④ 메모 소식(MemoFeedItem) + 어느 종목·메모에 붙었는지 */
export interface UpdateItem extends MemoFeedItem {
  stock_code: string;
  memo_id: string;
  memo_title: string;
  memo_color: MemoColor;
}

/** 업데이트 탭의 종목 (내 종목 순서) */
export interface UpdateStock {
  stock_code: string;
  name: string;
  logo: string;
  logo_bg: string;
  logo_ink?: string;
  market: string;
  status: 'holding' | 'watching';
  /** AI 연결 준비 중 종목 (메모만) */
  ai_ready: boolean;
}

export type KindFilter = '전체' | FeedKind;

export interface UpdatesData {
  stocks: UpdateStock[];
  items: UpdateItem[];
  /** 지금 ('N시간 전' 계산) */
  now: string;
  /** 처음 고른 종목 (없으면 전체) */
  code?: string;
}

export interface UpdatesCallbacks {
  /** 근거 상세 (④-2) */
  onOpenEvidence: (u: UpdateItem) => void;
  /** 메모 보드 (③) */
  onOpenBoard: (code: string) => void;
  /** 원문 (뉴스·공시) */
  onOpenSource: (u: UpdateItem) => void;
  /** 읽음 표시 바꾸기 (여러 건 · true = 읽음) */
  onMarkRead: (ids: string[], read: boolean) => void;
  /** 넛지: 오늘 소식 라디오 */
  onNudge: () => void;
  /** 고른 종목이 바뀜 (웹은 주소 · 앱은 화면 안) */
  onChangeCode?: (code: string | undefined) => void;
}

export interface AppUpdatesProps extends UpdatesData, UpdatesCallbacks {
  header: (o: { line: boolean; onReadAll?: () => void; readAllOff: boolean }) => ReactNode;
}

export type WebUpdatesProps = UpdatesData & UpdatesCallbacks;
