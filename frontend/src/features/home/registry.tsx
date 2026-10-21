import React from 'react';
import type { WidgetInstance, WidgetType } from '@/types/models';
import { CalendarWidget, MarketWidget, NewsWidget, UpdatesWidget } from './widgets/MarketWidgets';
import {
  ChecklistWidget,
  CompareMemoWidget,
  ConcludeMemoWidget,
  MemoBacktestWidget,
  MemoUpdatesWidget,
  PinnedMemosWidget,
  PriceConditionWidget,
  QuickMemoWidget,
  RecentJournalWidget,
} from './widgets/MemoWidgets';

export interface WidgetDef {
  type: WidgetType;
  title: string;
  desc: string;
  group: '기본' | '메모';
  spans: WidgetInstance['span'][]; // 허용 너비 (4열 기준)
  defaultSpan: WidgetInstance['span'];
  Component: React.ComponentType;
}

/** 홈 위젯 카탈로그 — 새 위젯은 여기에 한 줄 추가 */
export const WIDGETS: WidgetDef[] = [
  { type: 'market', title: '시장 지수·환율', desc: '코스피·코스닥·환율 + 금리·금·유가·채권 띠', group: '기본', spans: [3, 4], defaultSpan: 3, Component: MarketWidget },
  { type: 'updates', title: '종목별 업데이트', desc: '내 종목의 새 소식 개수', group: '기본', spans: [1, 2], defaultSpan: 1, Component: UpdatesWidget },
  { type: 'calendar', title: '주요 증시 일정', desc: '휴장일·실적 발표·내 일정 캘린더', group: '기본', spans: [2, 3], defaultSpan: 2, Component: CalendarWidget },
  { type: 'news', title: '뉴스', desc: '매일경제·한국경제·서울경제·연합뉴스 헤드라인', group: '기본', spans: [1, 2], defaultSpan: 1, Component: NewsWidget },
  { type: 'pinned_memos', title: '고정한 메모', desc: '잊고 싶지 않은 내 투자 생각', group: '메모', spans: [1, 2], defaultSpan: 1, Component: PinnedMemosWidget },
  { type: 'checklist', title: '확인할 것', desc: '종목별 체크리스트를 한곳에서', group: '메모', spans: [1, 2], defaultSpan: 1, Component: ChecklistWidget },
  { type: 'quick_memo', title: '빠른 메모', desc: '떠오른 생각을 바로 종목 보드에', group: '메모', spans: [1, 2], defaultSpan: 1, Component: QuickMemoWidget },
  { type: 'price_conditions', title: '지켜보는 가격 조건', desc: '내가 정한 기준과 지금의 거리', group: '메모', spans: [1, 2], defaultSpan: 1, Component: PriceConditionWidget },
  { type: 'recent_journal', title: '최근 투자 기록', desc: '그때의 판단을 다시 돌아보기', group: '메모', spans: [1, 2], defaultSpan: 1, Component: RecentJournalWidget },
  { type: 'memo_updates', title: '메모에 도착한 소식', desc: '종목별 업데이트를 연결된 메모까지', group: '메모', spans: [1, 2], defaultSpan: 1, Component: MemoUpdatesWidget },
  { type: 'memo_backtest', title: '메모대로 했다면', desc: '행동 조건 메모를 실제 주가로 검증', group: '메모', spans: [1, 2], defaultSpan: 1, Component: MemoBacktestWidget },
  { type: 'compare_memo', title: '비교 메모 자동 카드', desc: '“A랑 비교해보기” 메모에 두 기업 지표를 나란히', group: '메모', spans: [1, 2], defaultSpan: 1, Component: CompareMemoWidget },
  { type: 'conclude_memo', title: '결론 낼 메모', desc: '전제가 일어난 메모에 결론을 쓰고 투자 기록으로', group: '메모', spans: [1, 2], defaultSpan: 1, Component: ConcludeMemoWidget },
];

export const widgetDef = (t: WidgetType) => WIDGETS.find((w) => w.type === t)!;

/** '기본 템플릿 적용' 시 사용자화 화면으로 옮길 때의 초기 배치 */
export const TEMPLATE_WIDGETS: WidgetInstance[] = [
  { id: 'w_market', type: 'market', span: 4 },
  { id: 'w_updates', type: 'updates', span: 1 },
  { id: 'w_calendar', type: 'calendar', span: 2 },
  { id: 'w_news', type: 'news', span: 1 },
];
