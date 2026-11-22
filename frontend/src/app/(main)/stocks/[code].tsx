import React, { useEffect, useRef, useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { env } from '@/config/env';
import { useCoach } from '@/store/coach';
import type { Checklist, Memo, MemoColor, MemoVersion } from '@/types/models';
import { mockCompanyByCode } from '@/ui/screens/company/CompanyInfo.mock';
import { WebCompanyInfo } from '@/ui/screens/company/web/CompanyInfo';
import { useCompanyInfo } from '@/ui/screens/company/useCompanyInfo';
import { mockBoardChecklist, mockBoardMemos, mockBoardOrder, mockBoardStock, mockEmptyStock } from '@/ui/screens/board/MemoBoard.mock';
import { useBoardData } from '@/ui/screens/board/useBoardData';
import { useBoardStock } from '@/ui/screens/board/useBoardStock';
import { WebMemoBoard } from '@/ui/screens/board/web/MemoBoard';
import { mockExtract, mockFeed, mockToday, mockTrackItems, mockVersions } from '@/ui/screens/memo/MemoDetail.mock';
import type { AiLinkState, AiTrackItem } from '@/ui/screens/memo/MemoDetail.types';
import { WebConnectDialog } from '@/ui/screens/memo/web/ConnectDialog';
import { WebMemoDialog } from '@/ui/screens/memo/web/MemoDialog';
import { WebNewMemoDialog } from '@/ui/screens/memo/web/NewMemoDialog';
import { feedOf, findMemo, versionsOf } from '@/ui/screens/updates/Updates.mock';

/**
 * 웹 종목: 보드 = UI v2 (ui/screens/board/web) · 기업 정보 = UI v2 (ui/screens/company/web · ⑤) — /stocks/000660?tab=info
 * mock 모드: 000660 은 예시 메모, 105560(KB금융) 은 빈 보드. 변화는 이 화면 안에서만.
 * 실제 모드(2026-11-22): 보드·메모 창 데이터와 저장은 useBoardData (GET board · timeline, 쓰기 API).
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
  const baseStock = firstFlow && stockName ? { ...mockEmptyStock, stock_code: code, name: stockName } : empty ? mockEmptyStock : mockBoardStock;
  /* 종목 머리 시세: 실제 모드면 GET /stocks/{code}/quote (2026-11-21), mock 모드면 위 mock 그대로 */
  const { stock, priceNote } = useBoardStock(code, baseStock);
  const real = !env.useMock;
  const [memos, setMemos] = useState<Memo[]>(real || empty ? [] : mockBoardMemos);
  const [checklist, setChecklist] = useState<Checklist | null>(real || empty ? null : mockBoardChecklist);
  const [order, setOrder] = useState<string[]>(real ? [] : mockBoardOrder);
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
  /* 실제 모드: 서버 보드가 오면(또는 저장 뒤 다시 받으면) 화면 상태를 서버 값으로 */
  const bd = useBoardData(code, openId);
  const [cItems, setCItems] = useState<AiTrackItem[]>([]);
  const [seenVersion, setSeenVersion] = useState(0);
  if (bd.data && bd.version !== seenVersion) {
    setSeenVersion(bd.version);
    setMemos(bd.data.memos);
    setChecklist(bd.data.checklist);
    setOrder(bd.data.order);
  }
  /* ?fail=1: AI 연결 창 첫 분석을 실패로 (분석 실패 화면 확인용) */
  const { fail } = useLocalSearchParams<{ fail?: string }>();
  const [failOnce, setFailOnce] = useState(__DEV__ && fail === '1');
  /* 사용법 안내 (원본 board.tsx): ② 새 메모 창의 AI 연결 칸 · ③ 소식이 붙은 메모 창 · 그 밖에는 닫음 */
  const coachStep = useCoach((s) => s.step);
  const [coachSeen, setCoachSeen] = useState<number | null>(coachStep);
  if (coachStep !== coachSeen) {
    setCoachSeen(coachStep);
    if (coachStep === 1) {
      setDlg(false);
      setNewKey((n) => n + 1);
      setNewOpen(true);
    } else if (coachStep === 2) {
      setNewOpen(false);
      setOpenId('m1');
      setOpenTab('ai');
      setDlg(true);
    } else if (coachSeen === 1 || coachSeen === 2) {
      setNewOpen(false);
      setDlg(false);
    }
  }
  const opened = memos.find((m) => m.id === openId) ?? (!real && openId && openId === memoParam ? findMemo(openId) : undefined);
  const patch = (id: string, f: (m: Memo) => Memo) => setMemos((all) => all.map((m) => (m.id === id ? f(m) : m)));
  const items = real ? cItems : connect ? (connect.id && mockTrackItems[connect.id]?.length ? mockTrackItems[connect.id] : mockExtract(connect.title, connect.body)) : [];
  /* 분석 중 0.7초 (원본 웹 ConnectDialog) → 항목 있음 / 없음 */
  useEffect(() => {
    if (real || !connect || cState !== 'loading') return;
    const t = setTimeout(() => {
      if (failOnce) {
        setFailOnce(false);
        setCState('error');
      } else setCState(items.length ? 'items' : 'empty');
    }, 700);
    return () => clearTimeout(t);
  }, [real, connect, cState, items.length, failOnce]);
  const startConnect = (c: Connect) => {
    setCState('loading');
    setConnect(c);
    /* 실제 모드: 연결 창이 열릴 때 AI 켜기 → 분석 결과 (결정 7 임시안) */
    if (real && c.id)
      void bd.ops.aiOn(c.id).then((r) => {
        setCItems(r.items);
        setCState(r.state);
      });
  };
  const remove = (ids: string[]) => {
    bd.ops.remove(ids);
    removed.current = [...removed.current, ...memos.filter((m) => ids.includes(m.id))];
    setMemos((all) => all.filter((m) => !ids.includes(m.id)));
  };
  return (
    <>
    <WebMemoBoard
      stock={stock}
      priceNote={priceNote}
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
        if (!m) return;
        if (m.ai_linked) {
          bd.ops.aiOff(id);
          patch(id, (x) => ({ ...x, ai_linked: false }));
        } else startConnect({ id, title: m.title, body: m.body, color: m.color, fromNew: false });
      }}
      onDelete={remove}
      onUndoDelete={(ids) => {
        bd.ops.undoRemove(ids);
        const back = removed.current.filter((m) => ids.includes(m.id));
        removed.current = removed.current.filter((m) => !ids.includes(m.id));
        setMemos((all) => [...all.filter((m) => !ids.includes(m.id)), ...back]);
        /* 실제 모드는 삭제 뒤 서버 보드를 다시 받아 순서에서 빠져 있음 → 되살린 메모를 순서 끝에 */
        setOrder((o) => [...o, ...ids.filter((id) => !o.includes(id))]);
      }}
      onCopy={() => {}}
      onChangeColor={(ids, color) => {
        bd.ops.color(ids, color);
        setMemos((all) => all.map((m) => (ids.includes(m.id) ? { ...m, color } : m)));
      }}
      onReorder={(o) => {
        bd.ops.reorder(o);
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
        versions={real ? bd.detail?.versions ?? [] : versions[opened.id] ?? versionsOf(opened.id)}
        feed={real ? bd.detail?.feed ?? [] : feed[opened.id] ?? feedOf(opened.id)}
        initialEvidence={opened.id === memoParam ? ev : undefined}
        trackItems={real ? bd.detail?.trackItems ?? [] : mockTrackItems[opened.id] ?? []}
        initialTab={openTab}
        onBack={() => setDlg(false)}
        onSave={({ title, body }) => {
          bd.ops.save(opened.id, { title, body });
          setVersions((v) => ({ ...v, [opened.id]: [{ version: (v[opened.id]?.[0]?.version ?? 0) + 1, title, body, saved_at: mockToday }, ...(v[opened.id] ?? [])] }));
          patch(opened.id, (m) => ({ ...m, title, body, updated_at: mockToday }));
        }}
        onChangeColor={(color) => {
          bd.ops.color([opened.id], color);
          patch(opened.id, (m) => ({ ...m, color }));
        }}
        onTogglePin={(pinned) => {
          bd.ops.pin([opened.id], pinned);
          patch(opened.id, (m) => ({ ...m, pinned }));
        }}
        onDelete={() => {
          setDlg(false);
          remove([opened.id]);
        }}
        onCopy={() => {}}
        onConnectAi={() => startConnect({ id: opened.id, title: opened.title, body: opened.body, color: opened.color, fromNew: false })}
        onDisconnectAi={() => {
          bd.ops.aiOff(opened.id);
          patch(opened.id, (m) => ({ ...m, ai_linked: false }));
        }}
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
        if (real) {
          /* 실제 모드: 서버에 저장한 뒤 그 id 로. AI 를 켰으면 저장 응답의 분석을 연결 창에 */
          setNewOpen(false);
          void bd.ops.create({ title, body, color, ai }).then((r) => {
            if (!r) return;
            setMemos((all) => [...all, r.memo]);
            setOrder((o) => [...o, r.memo.id]);
            if (ai) {
              setConnect({ id: r.memo.id, title, body, color, fromNew: true });
              setCItems(r.connect.items);
              setCState(r.connect.state);
            } else if (firstFlow) router.replace({ pathname: '/', params: { onboarding: 'first_saved', selected: onboardingSelected ?? '', home_mode: onboardingHomeMode ?? 'template' } });
          });
          return;
        }
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
        /* 실제 모드: 연결 창을 열 때 켰으므로 '일반 메모로 두기' = 끄기 */
        if (real && connect?.id) bd.ops.aiOff(connect.id);
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
      onRetry={() => (real && connect ? startConnect(connect) : setCState('loading'))}
    />
    </>
  );
}

/* 기업 정보 = UI v2 (ui/screens/company/web · ⑤). 2026-11-21: profile·quote·candles·financials API (mock 모드는 같은 함수의 mock) */
function InfoTab({ code }: { code: string }) {
  const router = useRouter();
  const { data, error } = useCompanyInfo(code);
  const onChangeTab = (t: 'board' | 'company') => router.setParams({ tab: t === 'company' ? 'info' : 'board' });
  /* 주가 데이터도 없는 종목: 예시 값을 지어내지 않고 '준비 중' (머리는 예시 틀에 종목코드만) */
  if (error) return <WebCompanyInfo {...mockCompanyByCode(code)} stock={{ ...mockCompanyByCode(code).stock, stock_code: code }} preparing onBack={() => router.back()} onChangeTab={onChangeTab} />;
  if (!data) return null;
  return <WebCompanyInfo {...data} onBack={() => router.back()} onChangeTab={onChangeTab} onNudge={() => {}} />;
}
