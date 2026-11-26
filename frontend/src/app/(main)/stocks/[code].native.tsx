import React, { useCallback, useRef, useState } from 'react';
import { View } from 'react-native';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { copyText, memoText } from '@/lib/copyText';
import { useUI } from '@/store/ui';
import type { Memo } from '@/types/models';
import { AppCompanyInfo } from '@/ui/screens/company/app/CompanyInfo';
import type { CompanyInfoProps } from '@/ui/screens/company/CompanyInfo.types';
import { useCompanyInfo } from '@/ui/screens/company/useCompanyInfo';
import { AppStockTop } from '@/ui/screens/board/app/StockTop';
import { mockCompanyByCode } from '@/ui/screens/company/CompanyInfo.mock';
import { StockBar } from '@/ui/screens/board/app/StockBar';
import { NewMemoSheet, type NewMemoTarget } from '@/ui/screens/memo/app/NewMemoSheet';
import { AiOffSheet } from '@/ui/shared/AiOffSheet';
import { AppMemoBoard } from '@/ui/screens/board/app/MemoBoard';
import { patchMemo } from '@/ui/screens/board/boardCards';
import { useBoardCards } from '@/ui/screens/board/useBoardCards';
import { useMemoTimeline } from '@/hooks/queries';
import { useStockTop } from '@/ui/screens/board/useBoardStock';
import { useUsageView } from '@/ui/screens/my/useUsageView';
import { useAiOffChoice } from '@/ui/shared/useAiOffChoice';
import { env } from '@/config/env';
import { mockBoardStock, mockEmptyStock } from '@/ui/screens/board/MemoBoard.mock';

/**
 * 앱 종목 상세: 메모 보드 = UI v2 (ui/screens/board/app) · 기업정보 = UI v2 (ui/screens/company/app · ⑤).
 * mock 모드: 000660 은 예시 메모, 105560(KB금융) 은 빈 보드. 바꾼 내용은 기기에 저장 (store/mockBoard).
 * 실제 모드(2026-11-22): 보드 데이터와 저장은 useBoardData (웹 보드와 같음).
 * 메모 상세 · 새 메모 · AI 연결 = UI v2 (④ · app/(detail)/memo). 체크리스트 화면은 아직 옛 화면.
 */
export default function StockDetail() {
  const { code, tab: tabParam, notice: noticeParam, t: noticeKey, undo } = useLocalSearchParams<{ code: string; tab?: string; notice?: string; t?: string; undo?: string }>();
  /* 새 메모에서 돌아올 때 보드 스낵바 (원본 saveNew) */
  const NOTICE: Record<string, string> = { empty: '빈 메모는 저장하지 않았어요', saved: '메모를 저장했어요', cl_trash: '체크리스트를 휴지통으로 옮겼어요' };
  const boardNotice = noticeParam && noticeKey && NOTICE[noticeParam] ? { message: NOTICE[noticeParam], key: noticeKey, undo: undo ? [undo] : undefined } : undefined;
  const router = useRouter();
  const notice = useMockNotice();
  const setTabBarHidden = useUI((s) => s.setTabBarHidden);
  const [tab, setTab] = useState<'board' | 'company'>(tabParam === 'company' || tabParam === 'info' ? 'company' : 'board');
  const lastY = useRef(0);
  const [startY, setStartY] = useState(0);
  /* 머리: 두 탭이 같은 StockBar · 같은 스크롤 상태 */
  const cardH = useRef(200);
  const [compact, setCompact] = useState(false);
  const [line, setLine] = useState(false);
  const onScrollY = useCallback((y: number) => {
    lastY.current = y;
    setLine(y > 8);
    setCompact(y > cardH.current - 10);
  }, []);
  const empty = code === mockEmptyStock.stock_code;
  /* 위 카드: 두 탭이 같은 카드 · 같은 시세 (최신 종가 GET /stocks/{code}/quote). 탭을 바꿔도 스크롤 자리를 이어 감 */
  const { stock, priceNote, loading } = useStockTop(code, empty ? mockEmptyStock : mockBoardStock);
  const real = !env.useMock;
  const board = useBoardCards(code, null);
  const { bd } = board;
  const { memos, checklists, order } = board.cards;
  /* AI 사용량을 다 쓰면 보드 안내 상자 (스튜디오와 같은 기준, 2026-11-24) */
  const usage = useUsageView();
  const spent = usage.paused || usage.usage_pct >= 100;
  const toast = useUI((s) => s.showToast);
  const askAiOff = useAiOffChoice();
  const [memoTo, setMemoTo] = useState<NewMemoTarget | null>(null);
  const [offFor, setOffFor] = useState<Memo | null>(null);
  /* AI 끄기 확인 창의 '추적 항목 N개': 실제 모드면 그 메모의 추적 항목 수 (질문 제외), mock 은 예시 2개 */
  const offTimeline = useMemoTimeline(offFor?.id ?? '', real && !!offFor);
  const offItems = (offTimeline.data as { tracking_items?: { type: string }[] } | undefined)?.tracking_items;
  const offCount = real ? (offItems ?? []).filter((i) => i.type !== 'ask').length : 2;
  /* 다른 화면으로 가면 고르기 때문에 숨긴 탭바를 다시 보이게 */
  useFocusEffect(useCallback(() => () => setTabBarHidden(false), [setTabBarHidden]));
  const onSelectionChange = useCallback((n: number) => setTabBarHidden(n > 0), [setTabBarHidden]);

  const topCard = (
    <View onLayout={(e) => { cardH.current = e.nativeEvent.layout.height; }}>
      <AppStockTop stock={stock} priceNote={priceNote} loading={loading} />
    </View>
  );
  const header = <StockBar name={stock.name} price={priceNote || loading ? null : stock.price} pct={stock.change_pct} compact={compact} line={line} onBack={() => router.back()} onMore={() => notice('종목 메뉴')} />;
  const changeTab = (t: 'board' | 'company') => {
    setStartY(lastY.current);
    setTab(t);
  };

  if (tab === 'company') return <AppCompanyTab code={code} onBack={() => router.back()} onMore={() => notice('종목 메뉴')} onChangeTab={changeTab} onNudge={() => notice('주간보고서')} stock={stock} header={header} topCard={topCard} startY={startY} onScrollY={onScrollY} />;

  return (
    <>
    <AppMemoBoard
      header={header}
      stock={stock}
      topCard={topCard}
      startY={startY}
      onScrollY={onScrollY}
      memos={memos}
      checklists={checklists}
      order={order}
      notice={boardNotice}
      onOpenMemo={(id, t) => router.push({ pathname: '/memo/[id]', params: { id, tab: t } })}
      onOpenChecklist={(id) => router.push({ pathname: '/checklist/[id]', params: { id, code, name: stock.name } })}
      onNewMemo={(first) => setMemoTo({ code, name: stock.name, text: first })}
      onNewChecklist={() => router.push({ pathname: '/checklist/[id]', params: { id: 'new', code, name: stock.name } })}
      onToggleChecklistItem={board.toggleItem}
      onPin={board.pin}
      onToggleAi={(id) => {
        const m = memos.find((x) => x.id === id);
        /* 원본 aiToggle: 켜져 있으면 해제 확인 시트, 꺼져 있으면 AI 연결 창 */
        if (m?.ai_linked && spent) askAiOff();               // 끄기 대기: '모두 끄기' 선택
        else if (m?.ai_linked) setOffFor(m);
        else if (m && spent) toast('AI 사용량을 다 써서 AI 연결을 켤 수 없어요. 일반 메모로는 계속 쓸 수 있어요');
        else if (m) router.push({ pathname: '/memo/link', params: { id: m.id } });
      }}
      onDelete={board.remove}
      onUndoDelete={board.undoRemove}
      onCopy={(ids) => copyText(memos.filter((m) => ids.includes(m.id)).map(memoText).join('\n\n'))}
      onChangeColor={(ids, color) => {
        bd.ops.color(ids, color);
        board.update((b) => ({ ...b, memos: b.memos.map((m) => (ids.includes(m.id) ? { ...m, color } : m)) }));
      }}
      onReorder={board.reorder}
      onChangeTab={changeTab}
      onSelectionChange={onSelectionChange}
      aiSpent={spent}
      aiRefill={usage.usage_refill}
      aiCount={usage.ai_count}
      onSpentAction={(a) => (a === 'choice' ? askAiOff() : router.push(a === 'credit' ? '/studio-charge' : '/my-plans'))}
    />
    <NewMemoSheet target={memoTo} onClose={() => setMemoTo(null)} />
    <AiOffSheet
      open={!!offFor}
      stockName={stock.name}
      title={offFor?.title ?? ''}
      itemCount={offCount}
      onClose={() => setOffFor(null)}
      onConfirm={() => {
        const id = offFor?.id;
        setOffFor(null);
        if (id) bd.ops.aiOff(id);
        if (id) board.update((b) => patchMemo(b, id, (x) => ({ ...x, ai_linked: false })));
      }}
    />
    </>
  );
}

/* 기업정보 (앱, 2026-11-21): 실제 API 4개 → 화면 props (useCompanyInfo). 주가 데이터도 없으면 '준비 중' */
function AppCompanyTab({ code, ...rest }: { code: string } & Pick<CompanyInfoProps, 'onBack' | 'onMore' | 'onChangeTab' | 'onNudge' | 'stock'> & { topCard: React.ReactNode; header: React.ReactNode; startY: number; onScrollY: (y: number) => void }) {
  const { data, error } = useCompanyInfo(code);
  /* 받는 중에도 카드 · 탭은 그대로 (아래만 뼈대) */
  return <AppCompanyInfo {...(data ?? mockCompanyByCode(code))} {...rest} loading={!data && !error} preparing={error ? true : data?.preparing} />;
}
