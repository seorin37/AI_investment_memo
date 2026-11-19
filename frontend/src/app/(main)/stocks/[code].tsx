import React, { useEffect, useRef, useState } from 'react';
import { View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Page } from '@/components/layout/Page';
import { Loading, PillTabs } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { CompanyInfo } from '@/features/company/CompanyInfo';
import { StockHeader } from '@/features/stock/StockHeader';
import { useMyStocks, useProfile, useStock } from '@/hooks/queries';
import { colors } from '@/theme/tokens';
import type { Checklist, Memo, MemoColor, MemoVersion } from '@/types/models';
import { mockBoardChecklist, mockBoardMemos, mockBoardOrder, mockBoardStock, mockEmptyStock } from '@/ui/screens/board/MemoBoard.mock';
import { WebMemoBoard } from '@/ui/screens/board/web/MemoBoard';
import { mockExtract, mockFeed, mockToday, mockTrackItems, mockVersions } from '@/ui/screens/memo/MemoDetail.mock';
import type { AiLinkState } from '@/ui/screens/memo/MemoDetail.types';
import { WebConnectDialog } from '@/ui/screens/memo/web/ConnectDialog';
import { WebMemoDialog } from '@/ui/screens/memo/web/MemoDialog';
import { WebNewMemoDialog } from '@/ui/screens/memo/web/NewMemoDialog';

/**
 * 웹 종목: 보드 = UI v2 (ui/screens/board/web) · 기업 정보 = 아직 옛 화면 (⑤에서 교체) — /stocks/000660?tab=info
 * mock 단계: 000660 은 예시 메모, 105560(KB금융) 은 빈 보드. 변화는 이 화면 안에서만.
 * 메모 창 · 새 메모 · AI 연결 창 = UI v2 (④ ui/screens/memo/web).
 */
export default function StockScreen() {
  const { code, tab } = useLocalSearchParams<{ code: string; tab?: 'board' | 'info' }>();
  const active = tab === 'info' ? 'info' : 'board';
  if (active === 'board') return <BoardTab code={code} />;
  return <InfoTab code={code} />;
}

type Connect = { id: string | null; title: string; body: string; color: MemoColor; fromNew: boolean };

function BoardTab({ code }: { code: string }) {
  const router = useRouter();
  const empty = code === mockEmptyStock.stock_code;
  const stock = empty ? mockEmptyStock : mockBoardStock;
  const [memos, setMemos] = useState<Memo[]>(empty ? [] : mockBoardMemos);
  const [checklist, setChecklist] = useState<Checklist | null>(empty ? null : mockBoardChecklist);
  const [order, setOrder] = useState<string[]>(mockBoardOrder);
  const [customized, setCustomized] = useState(false);
  const removed = useRef<Memo[]>([]);
  /* ④ 메모 창 · 새 메모 · AI 연결 창 (mock: 바꾼 내용은 이 화면 안에서만) */
  const [versions, setVersions] = useState<Record<string, MemoVersion[]>>(mockVersions);
  const [feed, setFeed] = useState(mockFeed);
  const [openId, setOpenId] = useState<string | null>(null);
  const [openTab, setOpenTab] = useState<'memo' | 'ai'>('memo');
  const [dlg, setDlg] = useState(false);
  const [newOpen, setNewOpen] = useState(false);
  const [newKey, setNewKey] = useState(0);
  const [first, setFirst] = useState<string | undefined>(undefined);
  const [connect, setConnect] = useState<Connect | null>(null);
  const [cState, setCState] = useState<AiLinkState>('loading');
  /* ?fail=1: AI 연결 창 첫 분석을 실패로 (분석 실패 화면 확인용) */
  const { fail } = useLocalSearchParams<{ fail?: string }>();
  const [failOnce, setFailOnce] = useState(fail === '1');
  const opened = memos.find((m) => m.id === openId);
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
        versions={versions[opened.id] ?? []}
        feed={feed[opened.id] ?? []}
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
      }}
    />
    <WebConnectDialog
      open={!!connect}
      stockName={stock.name}
      memo={connect ?? { title: '', body: '', color: 'yellow' }}
      state={cState}
      items={items}
      onCancel={() => setConnect(null)}
      onConfirm={() => {
        if (connect?.id) patch(connect.id, (m) => ({ ...m, ai_linked: true, ai_linked_at: mockToday }));
        setConnect(null);
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

/* 기업 정보: 옛 화면 그대로 (⑤에서 교체) */
function InfoTab({ code }: { code: string }) {
  const router = useRouter();
  const { data: mine } = useMyStocks();
  const { data: master, isError: masterFailed, error: masterError } = useStock(code);
  const { data: profile } = useProfile(code);
  const my = mine?.find((s) => s.code === code);
  const stock = my ?? master ?? (profile ? { code: profile.code, name: profile.name, market: profile.market } : null);
  if (!stock && masterFailed) {
    return (
      <Page>
        <T color={colors.danger}>{masterError instanceof Error ? masterError.message : '종목 정보를 불러오지 못했어요.'}</T>
      </Page>
    );
  }
  if (!stock) return <Loading height={400} />;
  return (
    <Page top={56}>
      <StockHeader stock={stock} mine={my} large />
      <View style={{ marginTop: 44, marginBottom: 24 }}>
        <PillTabs
          items={[
            { key: 'board', label: '보드' },
            { key: 'info', label: '기업 정보' },
          ]}
          value="info"
          onChange={(k) => router.setParams({ tab: k })}
        />
      </View>
      <CompanyInfo stockCode={code} stockName={stock.name} />
    </Page>
  );
}
