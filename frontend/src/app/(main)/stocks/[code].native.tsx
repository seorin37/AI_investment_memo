import React, { useCallback, useState } from 'react';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { MobileScreen, useMockNotice } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import type { StockTab } from '@/components/mobile/StockSummaryCard';
import type { ChartRange } from '@/types/models';
import { MemoBoard } from '@/features/board/MemoBoard';
import { mockMemoBoardProps } from '@/features/board/MemoBoard.mock';
import type { BoardEntry } from '@/features/board/MemoBoard.types';
import { CompanyOverview } from '@/features/company/CompanyOverview';
import { mockCompanyOverviewProps } from '@/features/company/CompanyOverview.mock';
import { useUI } from '@/store/ui';

/**
 * 앱 종목 상세: 보드(MemoBoard) · 기업정보(CompanyOverview). 웹은 [code].tsx (BoardScreen · CompanyInfo).
 * mock 단계: 종목은 mock(SK하이닉스) 그대로, 체크 · 고정 같은 변화는 이 화면 안에서만.
 */
export default function StockDetail() {
  const { tab: tabParam } = useLocalSearchParams<{ code: string; tab?: string }>();
  const router = useRouter();
  const notice = useMockNotice();
  const setTabBarHidden = useUI((s) => s.setTabBarHidden);
  const [tab, setTab] = useState<StockTab>(tabParam === 'company' || tabParam === 'info' ? 'company' : 'board');
  const [items, setItems] = useState<BoardEntry[]>(mockMemoBoardProps.items);
  const [range, setRange] = useState<ChartRange>(mockCompanyOverviewProps.range);
  /* 다른 화면으로 가면 고르기 때문에 숨긴 탭바를 다시 보이게 */
  useFocusEffect(useCallback(() => () => setTabBarHidden(false), [setTabBarHidden]));
  const stock = mockMemoBoardProps.stock;
  const openLink = (id: string) => {
    const m = items.find((x) => x.id === id);
    if (m?.kind === 'memo') router.push({ pathname: '/memo/link', params: { title: m.title, body: m.body } });
  };
  return (
    <MobileScreen bar={<TopBar left="back" title={stock.name} onBack={() => router.back()} />}>
      {tab === 'board' ? (
        <MemoBoard
          {...mockMemoBoardProps}
          items={items}
          onChangeTab={setTab}
          onOpenMemo={(id, t) => router.push({ pathname: '/memo/[id]', params: { id, tab: t } })}
          onOpenChecklist={(id) => router.push({ pathname: '/checklist/[id]', params: { id } })}
          onToggleChecklistItem={(cid, iid) =>
            setItems((all) => all.map((e) => (e.kind === 'checklist' && e.id === cid ? { ...e, items: e.items.map((i) => (i.id === iid ? { ...i, done: !i.done } : i)) } : e)))
          }
          onCreate={(kind, first_line) =>
            kind === 'memo'
              ? router.push({ pathname: '/memo/new', params: { code: stock.stock_code, name: stock.name, first_line: first_line ?? '' } })
              : router.push({ pathname: '/checklist/[id]', params: { id: 'new' } })
          }
          onPin={(ids, pinned) => setItems((all) => all.map((e) => (ids.includes(e.id) ? { ...e, pinned } : e)))}
          onDelete={(ids) => setItems((all) => all.filter((e) => !ids.includes(e.id)))}
          onUndoDelete={() => setItems(mockMemoBoardProps.items)}
          onCopy={() => notice('복사')}
          onChangeColor={(ids, color) => setItems((all) => all.map((e) => (e.kind === 'memo' && ids.includes(e.id) ? { ...e, color } : e)))}
          onToggleAi={(id) => {
            const m = items.find((x) => x.id === id);
            if (m?.kind === 'memo' && m.ai_linked) notice('AI 연결 끄기');
            else openLink(id);
          }}
          onSelectionChange={(n) => setTabBarHidden(n > 0)}
        />
      ) : (
        <CompanyOverview
          {...mockCompanyOverviewProps}
          onChangeTab={setTab}
          onGoBoard={() => setTab('board')}
          range={range}
          onChangeRange={setRange}
          onHelp={() => notice('지표 설명')}
        />
      )}
    </MobileScreen>
  );
}
