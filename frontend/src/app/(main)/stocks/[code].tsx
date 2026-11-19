import React, { useRef, useState } from 'react';
import { View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Page } from '@/components/layout/Page';
import { Loading, PillTabs } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { CompanyInfo } from '@/features/company/CompanyInfo';
import { StockHeader } from '@/features/stock/StockHeader';
import { useMyStocks, useProfile, useStock } from '@/hooks/queries';
import { colors } from '@/theme/tokens';
import type { Checklist, Memo } from '@/types/models';
import { mockBoardChecklist, mockBoardMemos, mockBoardOrder, mockBoardStock, mockEmptyStock } from '@/ui/screens/board/MemoBoard.mock';
import { WebMemoBoard } from '@/ui/screens/board/web/MemoBoard';

/**
 * 웹 종목: 보드 = UI v2 (ui/screens/board/web) · 기업 정보 = 아직 옛 화면 (⑤에서 교체) — /stocks/000660?tab=info
 * mock 단계: 000660 은 예시 메모, 105560(KB금융) 은 빈 보드. 변화는 이 화면 안에서만. 메모 창은 ④에서.
 */
export default function StockScreen() {
  const { code, tab } = useLocalSearchParams<{ code: string; tab?: 'board' | 'info' }>();
  const active = tab === 'info' ? 'info' : 'board';
  if (active === 'board') return <BoardTab code={code} />;
  return <InfoTab code={code} />;
}

function BoardTab({ code }: { code: string }) {
  const router = useRouter();
  const empty = code === mockEmptyStock.stock_code;
  const [memos, setMemos] = useState<Memo[]>(empty ? [] : mockBoardMemos);
  const [checklist, setChecklist] = useState<Checklist | null>(empty ? null : mockBoardChecklist);
  const [order, setOrder] = useState<string[]>(mockBoardOrder);
  const [customized, setCustomized] = useState(false);
  const removed = useRef<Memo[]>([]);
  return (
    <WebMemoBoard
      stock={empty ? mockEmptyStock : mockBoardStock}
      memos={memos}
      checklist={checklist}
      order={order}
      orderCustomized={customized}
      onOpenMemo={() => {}}
      onOpenChecklist={() => {}}
      onNewMemo={() => {}}
      onNewChecklist={() => {}}
      onToggleChecklistItem={(iid) => setChecklist((c) => (c ? { ...c, items: c.items.map((i) => (i.id === iid ? { ...i, done: !i.done } : i)) } : c))}
      onPin={(ids, pinned) => setMemos((all) => all.map((m) => (ids.includes(m.id) ? { ...m, pinned } : m)))}
      onToggleAi={(id) => setMemos((all) => all.map((m) => (m.id === id ? { ...m, ai_linked: !m.ai_linked } : m)))}
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
