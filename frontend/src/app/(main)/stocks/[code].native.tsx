import React, { useCallback, useRef, useState } from 'react';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useMockNotice } from '@/components/layout/MobileScreen';
import { useUI } from '@/store/ui';
import type { Checklist, Memo } from '@/types/models';
import { AppCompanyInfo } from '@/ui/screens/company/app/CompanyInfo';
import type { CompanyInfoProps } from '@/ui/screens/company/CompanyInfo.types';
import { useCompanyInfo } from '@/ui/screens/company/useCompanyInfo';
import { mockCompanyByCode } from '@/ui/screens/company/CompanyInfo.mock';
import { TopBar } from '@/ui/layout/app/TopBar';
import { AiOffSheet } from '@/ui/shared/AiOffSheet';
import { AppMemoBoard } from '@/ui/screens/board/app/MemoBoard';
import { useBoardData } from '@/ui/screens/board/useBoardData';
import { useMemoTimeline } from '@/hooks/queries';
import { useBoardStock } from '@/ui/screens/board/useBoardStock';
import { useUsageView } from '@/ui/screens/my/useUsageView';
import { useAiOffChoice } from '@/ui/shared/useAiOffChoice';
import { env } from '@/config/env';
import { mockBoardChecklist, mockBoardMemos, mockBoardStock, mockEmptyStock } from '@/ui/screens/board/MemoBoard.mock';

/**
 * 앱 종목 상세: 메모 보드 = UI v2 (ui/screens/board/app) · 기업정보 = UI v2 (ui/screens/company/app · ⑤).
 * mock 모드: 000660 은 예시 메모, 105560(KB금융) 은 빈 보드. 변화는 이 화면 안에서만.
 * 실제 모드(2026-11-22): 보드 데이터와 저장은 useBoardData (웹 보드와 같음).
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
  /* 종목 머리 시세: 실제 모드면 GET /stocks/{code}/quote (2026-11-21), mock 모드면 mock 그대로 */
  const { stock, priceNote } = useBoardStock(code, empty ? mockEmptyStock : mockBoardStock);
  const real = !env.useMock;
  const [memos, setMemos] = useState<Memo[]>(real || empty ? [] : mockBoardMemos);
  const [checklist, setChecklist] = useState<Checklist | null>(real || empty ? null : mockBoardChecklist);
  /* 실제 모드: 서버 보드를 새로 받으면(메모 화면에서 돌아올 때 포함) 화면 상태를 서버 값으로 */
  const bd = useBoardData(code, null);
  /* AI 사용량을 다 쓰면 보드 안내 상자 (스튜디오와 같은 기준, 2026-11-24) */
  const usage = useUsageView();
  const spent = usage.paused || usage.usage_pct >= 100;
  const toast = useUI((s) => s.showToast);
  const askAiOff = useAiOffChoice();
  const [seenVersion, setSeenVersion] = useState(0);
  if (bd.data && bd.version !== seenVersion) {
    setSeenVersion(bd.version);
    setMemos(bd.data.memos);
    setChecklist(bd.data.checklist);
  }
  const removed = useRef<Memo[]>([]);
  const [offFor, setOffFor] = useState<Memo | null>(null);
  /* AI 끄기 확인 창의 '추적 항목 N개': 실제 모드면 그 메모의 추적 항목 수 (질문 제외), mock 은 예시 2개 */
  const offTimeline = useMemoTimeline(offFor?.id ?? '', real && !!offFor);
  const offItems = (offTimeline.data as { tracking_items?: { type: string }[] } | undefined)?.tracking_items;
  const offCount = real ? (offItems ?? []).filter((i) => i.type !== 'ask').length : 2;
  /* 다른 화면으로 가면 고르기 때문에 숨긴 탭바를 다시 보이게 */
  useFocusEffect(useCallback(() => () => setTabBarHidden(false), [setTabBarHidden]));
  const onSelectionChange = useCallback((n: number) => setTabBarHidden(n > 0), [setTabBarHidden]);

  if (tab === 'company') return <AppCompanyTab code={code} onBack={() => router.back()} onMore={() => notice('종목 메뉴')} onChangeTab={setTab} onNudge={() => notice('주간보고서')} />;

  return (
    <>
    <AppMemoBoard
      header={<TopBar preset="board" title={stock.name} onBack={() => router.back()} actions={[{ icon: 'moreV2', label: '종목 메뉴', onPress: () => notice('종목 메뉴') }]} />}
      stock={stock}
      priceNote={priceNote}
      memos={memos}
      checklist={checklist}
      notice={boardNotice}
      onOpenMemo={(id, t) => router.push({ pathname: '/memo/[id]', params: { id, tab: t } })}
      onOpenChecklist={() => router.push({ pathname: '/checklist/[id]', params: { id: checklist?.id ?? 'new' } })}
      onNewMemo={(first) => router.push({ pathname: '/memo/new', params: { code: stock.stock_code, name: stock.name, first_line: first ?? '' } })}
      onNewChecklist={() => router.push({ pathname: '/checklist/[id]', params: { id: 'new', code: stock.stock_code, name: stock.name } })}
      onToggleChecklistItem={(iid) => {
        const it = checklist?.items.find((i) => i.id === iid);
        if (checklist && it) bd.ops.checkItem(checklist.id, iid, !it.done);
        setChecklist((c) => (c ? { ...c, items: c.items.map((i) => (i.id === iid ? { ...i, done: !i.done } : i)) } : c));
      }}
      onPin={(ids, pinned) => {
        bd.ops.pin(ids, pinned);
        setMemos((all) => all.map((m) => (ids.includes(m.id) ? { ...m, pinned } : m)));
      }}
      onTogglePin={(pinned) => {
        if (checklist) bd.ops.pin([checklist.id], pinned);
        setChecklist((c) => (c ? { ...c, pinned } : c));
      }}
      onToggleAi={(id) => {
        const m = memos.find((x) => x.id === id);
        /* 원본 aiToggle: 켜져 있으면 해제 확인 시트, 꺼져 있으면 AI 연결 창 */
        if (m?.ai_linked && spent) askAiOff();               // 끄기 대기: '모두 끄기' 선택
        else if (m?.ai_linked) setOffFor(m);
        else if (m && spent) toast('AI 사용량을 다 써서 AI 연결을 켤 수 없어요. 일반 메모로는 계속 쓸 수 있어요');
        else if (m) router.push({ pathname: '/memo/link', params: { id: m.id } });
      }}
      onDelete={(ids) => {
        bd.ops.remove(ids);
        removed.current = [...removed.current, ...memos.filter((m) => ids.includes(m.id))];
        setMemos((all) => all.filter((m) => !ids.includes(m.id)));
      }}
      onUndoDelete={(ids) => {
        bd.ops.undoRemove(ids);
        const back = removed.current.filter((m) => ids.includes(m.id));
        removed.current = removed.current.filter((m) => !ids.includes(m.id));
        setMemos((all) => [...all.filter((m) => !ids.includes(m.id)), ...back]);
      }}
      onCopy={() => {}}
      onChangeColor={(ids, color) => {
        bd.ops.color(ids, color);
        setMemos((all) => all.map((m) => (ids.includes(m.id) ? { ...m, color } : m)));
      }}
      onReorder={() => {}}
      onChangeTab={setTab}
      onSelectionChange={onSelectionChange}
      aiSpent={spent}
      aiRefill={usage.usage_refill}
      aiCount={usage.ai_count}
      onSpentAction={(a) => (a === 'choice' ? askAiOff() : router.push(a === 'credit' ? '/studio-charge' : '/my-plans'))}
    />
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
        setMemos((all) => all.map((x) => (x.id === id ? { ...x, ai_linked: false } : x)));
      }}
    />
    </>
  );
}

/* 기업정보 (앱, 2026-11-21): 실제 API 4개 → 화면 props (useCompanyInfo). 주가 데이터도 없으면 '준비 중' */
function AppCompanyTab({ code, ...handlers }: { code: string } & Pick<CompanyInfoProps, 'onBack' | 'onMore' | 'onChangeTab' | 'onNudge'>) {
  const { data, error } = useCompanyInfo(code);
  if (error) return <AppCompanyInfo {...mockCompanyByCode(code)} stock={{ ...mockCompanyByCode(code).stock, stock_code: code }} preparing {...handlers} />;
  if (!data) return null;
  return <AppCompanyInfo {...data} {...handlers} />;
}
