import React, { useEffect, useRef, useState } from 'react';
import { Linking, Platform } from 'react-native';
import { useLocalSearchParams, useNavigation, useRouter } from 'expo-router';
import { env } from '@/config/env';
import { useCoach } from '@/store/coach';
import { useStudioPlayer } from '@/store/studioPlayer';
import { useUI } from '@/store/ui';
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
import type { ChecklistDraft } from '@/ui/screens/memo/web/ChecklistTab';
import { WebNewMemoDialog } from '@/ui/screens/memo/web/NewMemoDialog';
import { useUsageView } from '@/ui/screens/my/useUsageView';
import { useMarkWatchAdded } from '@/ui/screens/studio/reportView';
import { feedOf, findMemo, versionsOf } from '@/ui/screens/updates/Updates.mock';

/**
 * 웹 종목: 보드 = UI v2 (ui/screens/board/web) · 기업 정보 = UI v2 (ui/screens/company/web · ⑤) — /stocks/000660?tab=info
 * mock 모드: 000660 은 예시 메모, 105560(KB금융) 은 빈 보드. 변화는 이 화면 안에서만.
 * 실제 모드(2026-11-22): 보드·메모 창 데이터와 저장은 useBoardData (GET board · timeline, 쓰기 API).
 * 메모 창 · 새 메모 · AI 연결 창 = UI v2 (④ ui/screens/memo/web).
 */
export default function StockScreen() {
  /* memo · ev: 업데이트(⑥)의 '근거 자세히 보기' → 메모 창을 그 소식 근거로 열기 */
  /* new=1: 스튜디오 실험 결과 '메모 쓰기' → 새 메모 창 바로 열기 (엑셀 웹 #11) */
  const { code, tab, memo, ev, first, new: newParam, nt, nb, wr, wk, stock_name, onboarding_selected, onboarding_home_mode } = useLocalSearchParams<{ code: string; tab?: 'board' | 'info'; memo?: string; ev?: string; first?: string; new?: string; nt?: string; nb?: string; wr?: string; wk?: string; stock_name?: string; onboarding_selected?: string; onboarding_home_mode?: string }>();
  const active = tab === 'info' ? 'info' : 'board';
  if (active === 'board') return <BoardTab key={memo ?? 'board'} code={code} memoParam={memo} ev={ev} firstFlow={first === '1'} newParam={newParam} pre={nt ? { text: nb ? `${nt}\n${nb}` : nt, wr, wk } : undefined} stockName={stock_name} onboardingSelected={onboarding_selected} onboardingHomeMode={onboarding_home_mode} />;
  return <InfoTab code={code} />;
}

type Connect = { id: string | null; title: string; body: string; color: MemoColor; fromNew: boolean };

/** pre: 주간보고서 '메모에 추가'로 왔을 때 새 메모 창에 채울 글과 '추가됨'을 남길 보고서 id·키 (2026-11-24) */
type Pre = { text: string; wr?: string; wk?: string };

function BoardTab({ code, memoParam, ev, firstFlow, newParam, pre, stockName, onboardingSelected, onboardingHomeMode }: { code: string; memoParam?: string; ev?: string; firstFlow: boolean; newParam?: string; pre?: Pre; stockName?: string; onboardingSelected?: string; onboardingHomeMode?: string }) {
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
  const [preNew, setPreNew] = useState<Pre | null>(null);
  const markWatch = useMarkWatchAdded();
  /* 새 메모 창의 처음 탭 (0 메모 · 1 체크리스트 — '체크리스트 만들기' · 체크리스트 카드 열기) */
  const [newTab, setNewTab] = useState<0 | 1>(0);
  /* ?new=1 이 들어오면 새 메모 창(메모 탭)을 열고, 주소에서 new 를 지움 — 닫은 뒤 새로고침·뒤로가기로 다시 열리지 않게.
     온보딩(?first=1)은 위 firstFlow 그대로 · 이미 이 보드에 있을 때 다시 들어와도 열림 (2026-11-24, 엑셀 웹 #11) */
  const [seenNew, setSeenNew] = useState<string | undefined>(undefined);
  if (newParam !== seenNew) {
    setSeenNew(newParam);
    if (newParam === '1' && !firstFlow) {
      setPreNew(pre ?? null);
      setDlg(false);
      setNewTab(0);
      setNewKey((n) => n + 1);
      setNewOpen(true);
    }
  }
  /* router.setParams 는 앱 전체 기준이라 막 열린 이 화면 값을 못 지웠음 → 이 화면의 navigation 으로 지우고,
     웹은 주소창도 직접 정리 (보드는 다시 그리지 않아서 열린 창은 그대로) */
  const navigation = useNavigation();
  useEffect(() => {
    if (newParam !== '1') return;
    navigation.setParams({ new: undefined, nt: undefined, nb: undefined, wr: undefined, wk: undefined } as never);
    if (Platform.OS !== 'web') return;
    /* 다음 틈에 (라우터가 주소를 먼저 쓴 뒤) · 위 setParams 로 값이 바뀌어도 취소하지 않음 */
    setTimeout(() => {
      const u = new URL(window.location.href);
      if (!u.searchParams.has('new')) return;
      for (const k of ['new', 'nt', 'nb', 'wr', 'wk']) u.searchParams.delete(k);
      window.history.replaceState(window.history.state, '', u.pathname + u.search + u.hash);
    }, 0);
  }, [newParam, navigation]);
  const toast = useUI((s) => s.showToast);
  const [first, setFirst] = useState<string | undefined>(undefined);
  const [connect, setConnect] = useState<Connect | null>(null);
  const [cState, setCState] = useState<AiLinkState>('loading');
  /* 실제 모드: 서버 보드가 오면(또는 저장 뒤 다시 받으면) 화면 상태를 서버 값으로 */
  const bd = useBoardData(code, openId);
  /* AI 사용량을 다 쓰면 보드·메모 창에 안내 상자 (스튜디오와 같은 기준: 정지 또는 100% 이상). 버튼은 셸의 충전 창·설정 사용량 탭 (2026-11-24) */
  const usage = useUsageView();
  const aiSpent = usage.paused || usage.usage_pct >= 100;
  const requestSpent = useUI((s) => s.requestSpent);
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
  /* 지금 열려 있는 연결 창의 메모 id — 분석(LLM, 몇 초)이 끝났을 때 사용자가 창을 이미 닫았는지 본다 */
  const connectFor = useRef<string | null>(null);
  /* 실제 모드: AI 켜기 → 분석 결과를 창에. 그사이 '일반 메모로 두기'로 닫았으면 다시 끈다 */
  const analyze = (id: string) => {
    connectFor.current = id;
    setCItems([]);
    setCState('loading');
    void bd.ops.aiOn(id).then((r) => {
      if (connectFor.current !== id) return void bd.ops.aiOff(id);
      setCItems(r.items);
      setCState(r.state);
    });
  };
  const startConnect = (c: Connect) => {
    setCState('loading');
    setConnect(c);
    /* 실제 모드: 연결 창이 열릴 때 AI 켜기 → 분석 결과 (결정 7 임시안) */
    if (real && c.id) analyze(c.id);
  };
  const openChecklist = () => {
    setFirst(undefined);
    setNewTab(1);
    setNewKey((n) => n + 1);
    setNewOpen(true);
  };
  /** 체크리스트 저장 (종목당 하나: 있으면 고치고 없으면 만들기). mock 모드는 화면 안에서만.
   *  보드 순서는 체크리스트를 'cl' 칸으로 따로 두고, 순서에 없으면 맨 앞이라 순서는 건드리지 않음 */
  const saveChecklist = (d: ChecklistDraft) => {
    setNewOpen(false);
    const had = checklist;
    const ok = had ? '체크리스트를 저장했어요' : '체크리스트를 만들었어요';
    if (!real) {
      const items = d.items.map((i, n) => ({ id: i.id ?? `c${Date.now()}${n}`, text: i.text, done: i.done }));
      const next: Checklist = had ? { ...had, title: d.title, items } : { ...mockBoardChecklist, id: `cl${Date.now()}`, stock_code: code, title: d.title, items, pinned: false };
      setChecklist(next);
      return toast(ok);
    }
    void bd.ops.saveChecklist(had?.id ?? null, d).then((saved) => {
      if (!saved) return toast('체크리스트를 저장하지 못했어요 · 잠시 뒤 다시 해 주세요');
      setChecklist(saved);
      toast(ok);
    });
  };
  /** 항목을 모두 지우고 저장 → 있던 체크리스트는 휴지통으로 (원본 6.2) */
  const emptyChecklist = () => {
    setNewOpen(false);
    if (!checklist) return toast('빈 체크리스트는 저장하지 않았어요');
    const id = checklist.id;
    bd.ops.remove([id]);
    setChecklist(null);
    toast('체크리스트를 휴지통으로 옮겼어요');
  };
  const remove = (ids: string[]) => {
    bd.ops.remove(ids);
    removed.current = [...removed.current, ...memos.filter((m) => ids.includes(m.id))];
    setMemos((all) => all.filter((m) => !ids.includes(m.id)));
  };
  return (
    <>
    <WebMemoBoard
      aiSpent={aiSpent}
      aiRefill={usage.usage_refill}
      onSpentAction={requestSpent}
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
      onOpenChecklist={openChecklist}
      onNewMemo={(line) => {
        setNewTab(0);
        setFirst(line);
        setNewKey((n) => n + 1);
        setNewOpen(true);
      }}
      onNewChecklist={openChecklist}
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
        aiSpent={aiSpent}
        aiRefill={usage.usage_refill}
        onSpentAction={(a) => {
          setDlg(false);
          requestSpent(a);
        }}
        memo={opened}
        stockName={stock.name}
        versions={real ? bd.detail?.versions ?? [] : versions[opened.id] ?? versionsOf(opened.id)}
        feed={real ? bd.detail?.feed ?? [] : feed[opened.id] ?? feedOf(opened.id)}
        initialEvidence={opened.id === memoParam ? ev : undefined}
        trackItems={real ? bd.detail?.trackItems ?? [] : mockTrackItems[opened.id] ?? []}
        initialTab={openTab}
        onBack={() => setDlg(false)}
        /* 메모 창 넛지: 메모 창을 닫고 주간보고서 만들기 창 · 이 메모의 종목만 (원본 board.tsx setDlg(null) 후 report) */
        onNudge={() => {
          setDlg(false);
          useStudioPlayer.getState().askStudio('report', [opened.stock_code]);
        }}
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
          if (opened.unread_updates > 0) bd.ops.seenUpdates(opened.id);
          setFeed((f) => ({ ...f, [opened.id]: (f[opened.id] ?? []).map((x) => ({ ...x, unread: false })) }));
          patch(opened.id, (m) => ({ ...m, unread_updates: 0 }));
        }}
        onOpenSource={(f) => {
          if (f.url) void Linking.openURL(f.url);
        }}
      />
    ) : null}
    <WebNewMemoDialog
      key={newKey}
      open={newOpen}
      stockName={stock.name}
      initialText={preNew?.text ?? first}
      initialAi={!!preNew}
      tab0={newTab}
      checklist={checklist}
      onSaveChecklist={saveChecklist}
      onEmptyChecklist={emptyChecklist}
      onCancel={() => {
        setNewOpen(false);
        setPreNew(null);
      }}
      onSave={({ title, body, color, ai }) => {
        const fromReport = preNew;
        setPreNew(null);
        if (real) {
          /* 실제 모드: 일반 메모로 먼저 저장(빠름) → AI 를 켰으면 연결 창을 바로 '분석 중'으로 띄우고 그 메모로 분석 */
          setNewOpen(false);
          if (ai) {
            connectFor.current = null;
            setCItems([]);
            setCState('loading');
            setConnect({ id: null, title, body, color, fromNew: true });
          }
          void bd.ops.create({ title, body, color, ai: false }).then((r) => {
            if (!r) {
              if (ai) setCState('error');
              return;
            }
            setMemos((all) => [...all, r.memo]);
            setOrder((o) => [...o, r.memo.id]);
            if (fromReport) markWatch(fromReport.wr, fromReport.wk, r.memo.id);
            if (ai) {
              setConnect((c) => (c && !c.id ? { ...c, id: r.memo.id } : c));
              analyze(r.memo.id);
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
        connectFor.current = null;
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
      onRetry={() => {
        if (!real || !connect) return setCState('loading');
        if (connect.id) return startConnect(connect);
        /* 새 메모 저장 자체가 실패했던 경우: 다시 저장 → 분석 */
        setCState('loading');
        void bd.ops.create({ title: connect.title, body: connect.body, color: connect.color, ai: false }).then((r) => {
          if (!r) return setCState('error');
          setMemos((all) => [...all, r.memo]);
          setOrder((o) => [...o, r.memo.id]);
          setConnect((c) => (c ? { ...c, id: r.memo.id } : c));
          analyze(r.memo.id);
        });
      }}
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
  return <WebCompanyInfo {...data} onBack={() => router.back()} onChangeTab={onChangeTab} onNudge={() => useStudioPlayer.getState().askStudio('report', [code])} />;
}
