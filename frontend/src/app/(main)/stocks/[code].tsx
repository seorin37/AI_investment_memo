import React, { useEffect, useRef, useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import type { Checklist, Memo, MemoColor, MemoVersion } from '@/types/models';
import { mockCompanyByCode } from '@/ui/screens/company/CompanyInfo.mock';
import { WebCompanyInfo } from '@/ui/screens/company/web/CompanyInfo';
import { mockBoardChecklist, mockBoardMemos, mockBoardOrder, mockBoardStock, mockEmptyStock } from '@/ui/screens/board/MemoBoard.mock';
import { WebMemoBoard } from '@/ui/screens/board/web/MemoBoard';
import { mockExtract, mockFeed, mockToday, mockTrackItems, mockVersions } from '@/ui/screens/memo/MemoDetail.mock';
import type { AiLinkState } from '@/ui/screens/memo/MemoDetail.types';
import { WebConnectDialog } from '@/ui/screens/memo/web/ConnectDialog';
import { WebMemoDialog } from '@/ui/screens/memo/web/MemoDialog';
import { WebNewMemoDialog } from '@/ui/screens/memo/web/NewMemoDialog';
import { feedOf, findMemo, versionsOf } from '@/ui/screens/updates/Updates.mock';

/**
 * 웹 종목: 보드 = UI v2 (ui/screens/board/web) · 기업 정보 = UI v2 (ui/screens/company/web · ⑤) — /stocks/000660?tab=info
 * mock 단계: 000660 은 예시 메모, 105560(KB금융) 은 빈 보드. 변화는 이 화면 안에서만.
 * 메모 창 · 새 메모 · AI 연결 창 = UI v2 (④ ui/screens/memo/web).
 */
export default function StockScreen() {
  /* memo · ev: 업데이트(⑥)의 '근거 자세히 보기' → 메모 창을 그 소식 근거로 열기 */
  const { code, tab, memo, ev, first, stock_name, onboarding_selected, onboarding_home_mode } = useLocalSearchParams<{ code: string; tab?: 'board' | 'info'; memo?: string; ev?: string; first?: string; stock_name?: string; onboarding_selected?: string; onboarding_home_mode?: string }>();
  const active = tab === 'info' ? 'info' : 'board';
  if (active === 'board') return <BoardTab key={memo ?? 'board'} code={code} memoParam={memo} ev={ev} firstFlow={first === '1'} stockName={stock_name} onboardingSelected={onboarding_selected} onboardingHomeMode={onboarding_home_mode} />;
  return <InfoTab code={code} />;
}

type Connect = { id: string | null; title: string; body: string; color: MemoColor; fromNew: boolean };

function BoardTab({ code, memoParam, ev, firstFlow, stockName, onboardingSelected, onboardingHomeMode }: { code: string; memoParam?: string; ev?: string; firstFlow: boolean; stockName?: string; onboardingSelected?: string; onboardingHomeMode?: string }) {
  const router = useRouter();
  const empty = firstFlow || code === mockEmptyStock.stock_code;
  const stock = firstFlow && stockName ? { ...mockEmptyStock, stock_code: code, name: stockName } : empty ? mockEmptyStock : mockBoardStock;
  const [memos, setMemos] = useState<Memo[]>(empty ? [] : mockBoardMemos);
  const [checklist, setChecklist] = useState<Checklist | null>(empty ? null : mockBoardChecklist);
  const [order, setOrder] = useState<string[]>(mockBoardOrder);
  const [customized, setCustomized] = useState(false);
  const removed = useRef<Memo[]>([]);
  /* ④ 메모 창 · 새 메모 · AI 연결 창 (mock: 바꾼 내용은 이 화면 안에서만) */
  const [versions, setVersions] = useState<Record<string, MemoVersion[]>>(mockVersions);
  const [feed, setFeed] = useState(mockFeed);
  const [openId, setOpenId] = useState<string | null>(memoParam ?? null);
  const [openTab, setOpenTab] = useState<'memo' | 'ai'>('memo');
  const [dlg, setDlg] = useState(!!memoParam);
  const [newOpen, setNewOpen] = useState(firstFlow);
  const [newKey, setNewKey] = useState(0);
  const [first, setFirst] = useState<string | undefined>(undefined);
  const [connect, setConnect] = useState<Connect | null>(null);
  const [cState, setCState] = useState<AiLinkState>('loading');
  /* ?fail=1: AI 연결 창 첫 분석을 실패로 (분석 실패 화면 확인용) */
  const { fail } = useLocalSearchParams<{ fail?: string }>();
  const [failOnce, setFailOnce] = useState(fail === '1');
  const opened = memos.find((m) => m.id === openId) ?? (openId && openId === memoParam ? findMemo(openId) : undefined);
  const patch = (id: string, f: (m: Memo) => Memo) => setMemos((all) => all.map((m) => (m.id === id ? f(m) : m)));
  const items = connect ? (connect.id && mockTrackItems[connect.id]?.length ? mockTrackItems[connect.id] : mockExtract(connect.title, connect.body)) : [];
  /* 분석 중 0.7초 (원본 웹 ConnectDialog) → 항목 있음 / 없음 */
  useEffect(() => {
    if (!connect || cState !== 'loading') return;
    const t = setTimeout(() => {
      if (failOnce) {
        setFailOnce(false);
        setCState('error');
      } else setCState(items.length ? 'items' : 'empty');
    }, 700);
    return () => clearTimeout(t);
  }, [connect, cState, items.length, failOnce]);
  const startConnect = (c: Connect) => {
    setCState('loading');
    setConnect(c);
  };
  const remove = (ids: string[]) => {
    removed.current = [...removed.current, ...memos.filter((m) => ids.includes(m.id))];
    setMemos((all) => all.filter((m) => !ids.includes(m.id)));
  };
  return (
    <>
    <WebMemoBoard
      stock={stock}
      memos={memos}
      checklist={checklist}
      order={order}
      orderCustomized={customized}
      onOpenMemo={(id, t) => {
        setOpenId(id);
        setOpenTab(t);
        setDlg(true);
      }}
      onOpenChecklist={() => {}}
      onNewMemo={(line) => {
        setFirst(line);
        setNewKey((n) => n + 1);
        setNewOpen(true);
      }}
      onNewChecklist={() => {}}
      onToggleChecklistItem={(iid) => setChecklist((c) => (c ? { ...c, items: c.items.map((i) => (i.id === iid ? { ...i, done: !i.done } : i)) } : c))}
      onPin={(ids, pinned) => setMemos((all) => all.map((m) => (ids.includes(m.id) ? { ...m, pinned } : m)))}
      onTogglePin={(pinned) => setChecklist((c) => (c ? { ...c, pinned } : c))}
      onToggleAi={(id) => {
        const m = memos.find((x) => x.id === id);
        if (!m) return;
        if (m.ai_linked) patch(id, (x) => ({ ...x, ai_linked: false }));
        else startConnect({ id, title: m.title, body: m.body, color: m.color, fromNew: false });
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
      onReorder={(o) => {
        setOrder(o);
        setCustomized(true);
      }}
      onChangeTab={(t) => router.setParams({ tab: t === 'company' ? 'info' : 'board' })}
    />
    {opened ? (
      <WebMemoDialog
        key={opened.id}
        open={dlg}
        memo={opened}
        stockName={stock.name}
        versions={versions[opened.id] ?? versionsOf(opened.id)}
        feed={feed[opened.id] ?? feedOf(opened.id)}
        initialEvidence={opened.id === memoParam ? ev : undefined}
        trackItems={mockTrackItems[opened.id] ?? []}
        initialTab={openTab}
        onBack={() => setDlg(false)}
        onSave={({ title, body }) => {
          setVersions((v) => ({ ...v, [opened.id]: [{ version: (v[opened.id]?.[0]?.version ?? 0) + 1, title, body, saved_at: mockToday }, ...(v[opened.id] ?? [])] }));
          patch(opened.id, (m) => ({ ...m, title, body, updated_at: mockToday }));
        }}
        onChangeColor={(color) => patch(opened.id, (m) => ({ ...m, color }))}
        onTogglePin={(pinned) => patch(opened.id, (m) => ({ ...m, pinned }))}
        onDelete={() => {
          setDlg(false);
          remove([opened.id]);
        }}
        onCopy={() => {}}
        onConnectAi={() => startConnect({ id: opened.id, title: opened.title, body: opened.body, color: opened.color, fromNew: false })}
        onDisconnectAi={() => patch(opened.id, (m) => ({ ...m, ai_linked: false }))}
        onSeenUpdates={() => {
          setFeed((f) => ({ ...f, [opened.id]: (f[opened.id] ?? []).map((x) => ({ ...x, unread: false })) }));
          patch(opened.id, (m) => ({ ...m, unread_updates: 0 }));
        }}
      />
    ) : null}
    <WebNewMemoDialog
      key={newKey}
      open={newOpen}
      stockName={stock.name}
      initialText={first}
      onCancel={() => setNewOpen(false)}
      onSave={({ title, body, color, ai }) => {
        const id = `n${Date.now()}`;
        setMemos((all) => [...all, { ...mockBoardMemos[0], id, title, body, color, pinned: false, ai_linked: false, ai_linked_at: null, unread_updates: 0, created_at: mockToday, updated_at: mockToday }]);
        setVersions((v) => ({ ...v, [id]: [{ version: 1, title, body, saved_at: mockToday }] }));
        setOrder((o) => [...o, id]);
        setNewOpen(false);
        if (ai) startConnect({ id, title, body, color, fromNew: true });
        else if (firstFlow) router.replace({ pathname: '/', params: { onboarding: 'first_saved', selected: onboardingSelected ?? '', home_mode: onboardingHomeMode ?? 'template' } });
      }}
    />
    <WebConnectDialog
      open={!!connect}
      stockName={stock.name}
      memo={connect ?? { title: '', body: '', color: 'yellow' }}
      state={cState}
      items={items}
      onCancel={() => {
        setConnect(null);
        /* 첫 메모 흐름: 메모는 일반 메모로 저장됐으니 첫 홈으로 (고른 종목·홈 구성 유지) */
        if (firstFlow) router.replace({ pathname: '/', params: { onboarding: 'first_saved', selected: onboardingSelected ?? '', home_mode: onboardingHomeMode ?? 'template' } });
      }}
      onConfirm={() => {
        if (connect?.id) patch(connect.id, (m) => ({ ...m, ai_linked: true, ai_linked_at: mockToday }));
        setConnect(null);
        if (firstFlow) router.replace({ pathname: '/', params: { onboarding: 'first_saved', selected: onboardingSelected ?? '', home_mode: onboardingHomeMode ?? 'template' } });
      }}
      onEditMemo={() => {
        const id = connect?.id;
        setConnect(null);
        if (id) {
          setOpenId(id);
          setOpenTab('memo');
          setDlg(true);
        }
      }}
      onRetry={() => setCState('loading')}
    />
    </>
  );
}

/* 기업 정보 = UI v2 (ui/screens/company/web · ⑤). mock: 000660 일반 종목 · 105560 금융업 */
function InfoTab({ code }: { code: string }) {
  const router = useRouter();
  return <WebCompanyInfo {...mockCompanyByCode(code)} onBack={() => router.back()} onChangeTab={(t) => router.setParams({ tab: t === 'company' ? 'info' : 'board' })} onNudge={() => {}} />;
}
