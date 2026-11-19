import React, { useCallback, useRef, useState } from 'react';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { MobileScreen, useMockNotice } from '@/components/layout/MobileScreen';
import { TopBar as OldTopBar } from '@/components/layout/TopBar';
import { CompanyOverview } from '@/features/company/CompanyOverview';
import { mockCompanyOverviewProps } from '@/features/company/CompanyOverview.mock';
import { useUI } from '@/store/ui';
import type { ChartRange, Checklist, Memo } from '@/types/models';
import { TopBar } from '@/ui/layout/app/TopBar';
import { AiOffSheet } from '@/ui/shared/AiOffSheet';
import { AppMemoBoard } from '@/ui/screens/board/app/MemoBoard';
import { mockBoardChecklist, mockBoardMemos, mockBoardStock, mockEmptyStock } from '@/ui/screens/board/MemoBoard.mock';

/**
 * 앱 종목 상세: 메모 보드 = UI v2 (ui/screens/board/app) · 기업정보 = 아직 옛 화면 (⑤에서 교체).
 * mock 단계: 000660 은 예시 메모, 105560(KB금융) 은 빈 보드. 변화는 이 화면 안에서만.
 * 메모 상세 · 새 메모 · AI 연결 = UI v2 (④ · app/(detail)/memo). 체크리스트 화면은 아직 옛 화면.
 */
export default function StockDetail() {
  const { code, tab: tabParam, notice: noticeParam, t: noticeKey } = useLocalSearchParams<{ code: string; tab?: string; notice?: string; t?: string }>();
  /* 새 메모에서 돌아올 때 보드 스낵바 (원본 saveNew) */
  const NOTICE: Record<string, string> = { empty: '빈 메모는 저장하지 않았어요', saved: '메모를 저장했어요' };
  const boardNotice = noticeParam && noticeKey && NOTICE[noticeParam] ? { message: NOTICE[noticeParam], key: noticeKey } : undefined;
  const router = useRouter();
  const notice = useMockNotice();
  const setTabBarHidden = useUI((s) => s.setTabBarHidden);
  const [tab, setTab] = useState<'board' | 'company'>(tabParam === 'company' || tabParam === 'info' ? 'company' : 'board');
  const empty = code === mockEmptyStock.stock_code;
  const stock = empty ? mockEmptyStock : mockBoardStock;
  const [memos, setMemos] = useState<Memo[]>(empty ? [] : mockBoardMemos);
  const [checklist, setChecklist] = useState<Checklist | null>(empty ? null : mockBoardChecklist);
  const removed = useRef<Memo[]>([]);
  const [offFor, setOffFor] = useState<Memo | null>(null);
  const [range, setRange] = useState<ChartRange>(mockCompanyOverviewProps.range);
  /* 다른 화면으로 가면 고르기 때문에 숨긴 탭바를 다시 보이게 */
  useFocusEffect(useCallback(() => () => setTabBarHidden(false), [setTabBarHidden]));
  const onSelectionChange = useCallback((n: number) => setTabBarHidden(n > 0), [setTabBarHidden]);

  if (tab === 'company')
    return (
      <MobileScreen bar={<OldTopBar left="back" title={stock.name} onBack={() => router.back()} />}>
        <CompanyOverview {...mockCompanyOverviewProps} onChangeTab={(t) => setTab(t === 'company' ? 'company' : 'board')} onGoBoard={() => setTab('board')} range={range} onChangeRange={setRange} onHelp={() => notice('지표 설명')} />
      </MobileScreen>
    );

  return (
    <>
    <AppMemoBoard
      header={<TopBar preset="board" title={stock.name} onBack={() => router.back()} actions={[{ icon: 'moreV2', label: '종목 메뉴', onPress: () => notice('종목 메뉴') }]} />}
      stock={stock}
      memos={memos}
      checklist={checklist}
      notice={boardNotice}
      onOpenMemo={(id, t) => router.push({ pathname: '/memo/[id]', params: { id, tab: t } })}
      onOpenChecklist={() => router.push({ pathname: '/checklist/[id]', params: { id: checklist?.id ?? 'new' } })}
      onNewMemo={(first) => router.push({ pathname: '/memo/new', params: { code: stock.stock_code, name: stock.name, first_line: first ?? '' } })}
      onNewChecklist={() => router.push({ pathname: '/checklist/[id]', params: { id: 'new' } })}
      onToggleChecklistItem={(iid) => setChecklist((c) => (c ? { ...c, items: c.items.map((i) => (i.id === iid ? { ...i, done: !i.done } : i)) } : c))}
      onPin={(ids, pinned) => setMemos((all) => all.map((m) => (ids.includes(m.id) ? { ...m, pinned } : m)))}
      onTogglePin={(pinned) => setChecklist((c) => (c ? { ...c, pinned } : c))}
      onToggleAi={(id) => {
        const m = memos.find((x) => x.id === id);
        /* 원본 aiToggle: 켜져 있으면 해제 확인 시트, 꺼져 있으면 AI 연결 창 */
        if (m?.ai_linked) setOffFor(m);
        else if (m) router.push({ pathname: '/memo/link', params: { id: m.id } });
      }}
      onDelete={(ids) => {
        removed.current = [...removed.current, ...memos.filter((m) => ids.includes(m.id))];
        setMemos((all) => all.filter((m) => !ids.includes(m.id)));
      }}
      onUndoDelete={(ids) => {
        const back = removed.current.filter((m) => ids.includes(m.id));
        removed.current = removed.current.filter((m) => !ids.includes(m.id));
        setMemos((all) => [...all, ...back]);
      }}
      onCopy={() => {}}
      onChangeColor={(ids, color) => setMemos((all) => all.map((m) => (ids.includes(m.id) ? { ...m, color } : m)))}
      onReorder={() => {}}
      onChangeTab={setTab}
      onSelectionChange={onSelectionChange}
      onSpentAction={(a) => notice(a === 'credit' ? '크레딧 구매' : '플랜 변경')}
    />
    <AiOffSheet
      open={!!offFor}
      stockName={stock.name}
      title={offFor?.title ?? ''}
      itemCount={2}
      onClose={() => setOffFor(null)}
      onConfirm={() => {
        const id = offFor?.id;
        setOffFor(null);
        setMemos((all) => all.map((x) => (x.id === id ? { ...x, ai_linked: false } : x)));
      }}
    />
    </>
  );
}
