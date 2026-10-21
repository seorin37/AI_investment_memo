import React, { useMemo, useState } from 'react';
import { View } from 'react-native';
import { Button, EmptyState, ErrorState, Loading } from '@/components/ui/primitives';
import { useBoard, useSetAiLink, useUpdateBoardItem } from '@/hooks/queries';
import { useBreakpoint } from '@/hooks/useLayout';
import { useUI } from '@/store/ui';
import { layout } from '@/theme/tokens';
import type { BoardItem } from '@/types/models';
import { AiUpdatePanel } from './AiUpdatePanel';
import { ChecklistCard, MemoCard, NewMemoCard, ReferenceCard } from './BoardCards';

const COL_MIN = 220;
const GAP = 16;

/** 6. 기업 메모장 · 보드 — 위치(position) 순서대로 열에 번갈아 배치(메이슨리) + 우측 AI 업데이트 */
export function BoardScreen({ stockCode }: { stockCode: string }) {
  const { data, isLoading, error, refetch } = useBoard(stockCode);
  const { isMobile, isDesktop } = useBreakpoint();
  const openModal = useUI((s) => s.openModal);
  const setAi = useSetAiLink(stockCode);
  const update = useUpdateBoardItem(stockCode);
  const [boardW, setBoardW] = useState(0);

  const cols = Math.max(1, Math.min(4, Math.floor((boardW + GAP) / (COL_MIN + GAP))));
  const columns = useMemo(() => {
    const out: (BoardItem | 'new')[][] = Array.from({ length: cols }, () => []);
    const items: (BoardItem | 'new')[] = [...(data ?? []).slice().sort((a, b) => a.position - b.position), 'new'];
    items.forEach((it, i) => out[i % cols].push(it));
    return out;
  }, [data, cols]);

  const render = (it: BoardItem | 'new') => {
    if (it === 'new') return <NewMemoCard key="new" onOpen={() => openModal({ type: 'newBoardItem', stockCode })} />;
    if (it.kind === 'memo')
      return (
        <MemoCard
          key={it.id}
          memo={it}
          onPress={() => openModal({ type: 'memoDetail', stockCode, memoId: it.id })}
          onToggleAi={(v) => setAi.mutate({ memoId: it.id, enabled: v })}
        />
      );
    if (it.kind === 'checklist')
      return (
        <ChecklistCard
          key={it.id}
          item={it}
          onPress={() => openModal({ type: 'editBoardItem', stockCode, itemId: it.id })}
          onToggle={(itemId, done) => update.mutate({ id: it.id, patch: { items: it.items.map((x) => (x.id === itemId ? { ...x, done } : x)) } })}
        />
      );
    return <ReferenceCard key={it.id} item={it} onPress={() => openModal({ type: 'editBoardItem', stockCode, itemId: it.id })} />;
  };

  return (
    <View style={{ flexDirection: isDesktop ? 'row' : 'column', gap: 40, alignItems: 'flex-start' }}>
      <View style={{ flex: isDesktop ? 1 : undefined, alignSelf: 'stretch', minWidth: 0 }} onLayout={(e) => setBoardW(e.nativeEvent.layout.width)}>
        {isLoading && <Loading height={300} />}
        {error && <ErrorState message="보드를 불러오지 못했어요." onRetry={() => void refetch()} />}
        {data && data.length === 0 && (
          <EmptyState
            title="아직 메모가 없어요"
            desc="관심 이유, 확인할 것, 매수·매도 생각을 자유롭게 적어 보세요."
            action={<Button label="새 메모" icon="plus" size="sm" onPress={() => openModal({ type: 'newBoardItem', stockCode })} style={{ marginTop: 8 }} />}
          />
        )}
        {data && boardW > 0 && (
          <View style={{ flexDirection: 'row', gap: GAP, alignItems: 'flex-start' }}>
            {columns.map((col, i) => (
              <View key={i} style={{ flex: 1, gap: GAP, minWidth: 0 }}>
                {col.map(render)}
              </View>
            ))}
          </View>
        )}
      </View>
      <View style={{ width: isDesktop ? layout.aiPanelWidth : '100%', marginTop: isMobile ? 8 : 0 }}>
        <AiUpdatePanel stockCode={stockCode} />
      </View>
    </View>
  );
}
