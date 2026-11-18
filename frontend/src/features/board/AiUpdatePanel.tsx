import React from 'react';
import { View } from 'react-native';
import { Icon, type IconName } from '@/components/icons/Icon';
import { EmptyState, Hoverable, Loading } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useMarkAiUpdateRead, useStockAiUpdates } from '@/hooks/queries';
import { relative } from '@/lib/format';
import { useUI } from '@/store/ui';
import { colors, panelIconTone } from '@/theme/tokens';
import type { AiUpdate, UpdateType } from '@/types/models';

const typeIcon: Record<UpdateType, IconName> = { disclosure: 'fileText', news: 'newspaper', price: 'trendingUp' };

/** 보드 우측 '내 메모에 연결된 소식 · AI 업데이트' 패널 */
export function AiUpdatePanel({ stockCode }: { stockCode: string }) {
  const { data, isLoading } = useStockAiUpdates(stockCode);
  const markRead = useMarkAiUpdateRead(stockCode);
  const openModal = useUI((s) => s.openModal);
  const unread = (data ?? []).filter((u) => !u.read);
  const read = (data ?? []).filter((u) => u.read);

  const open = (u: AiUpdate) => {
    if (!u.read) markRead.mutate(u.id);
    openModal({ type: 'memoDetail', stockCode, memoId: u.memo_id, tab: 'ai' });
  };

  return (
    <View style={{ backgroundColor: colors.surface, borderRadius: 28, borderWidth: 1, borderColor: colors.border, padding: 18, paddingTop: 22, minHeight: 640, gap: 8 }}>
      <T size={11} color={colors.textSub}>
        내 메모에 연결된 소식
      </T>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <T size={24} weight="bold">
          AI 업데이트
        </T>
        {unread.length > 0 && (
          <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: '#FDECEC', alignItems: 'center', justifyContent: 'center' }}>
            <T size={11} weight="semibold" color={colors.danger} lh={1}>
              {unread.length}
            </T>
          </View>
        )}
      </View>
      {isLoading && <Loading />}
      {!isLoading && data?.length === 0 && <EmptyState title="아직 도착한 소식이 없어요" desc="메모의 AI 연결을 켜면 관련 공시·뉴스·주가 변화가 여기에 모여요." />}
      {unread.map((u) => (
        <PanelItem key={u.id} u={u} onPress={() => open(u)} />
      ))}
      {read.length > 0 && (
        <>
          <T size={11} color={colors.textSub} style={{ marginTop: 14, marginBottom: 2 }}>
            읽은 업데이트
          </T>
          {read.map((u) => (
            <PanelItem key={u.id} u={u} onPress={() => open(u)} compact />
          ))}
        </>
      )}
    </View>
  );
}

function PanelItem({ u, onPress, compact }: { u: AiUpdate; onPress: () => void; compact?: boolean }) {
  const tone = panelIconTone[u.type];
  return (
    <Hoverable onPress={onPress} style={{ backgroundColor: '#FAFAFA', borderRadius: 14, padding: 12, gap: 6 }} hoverStyle={{ backgroundColor: '#F4F4F6' }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <View style={{ width: 22, height: 22, borderRadius: 6, backgroundColor: tone.bg, alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={typeIcon[u.type]} size={13} color="#FFF" strokeWidth={2} />
        </View>
        <T size={11} color={colors.textSub} style={{ flex: 1 }}>
          {tone.label} · {relative(u.published_at)}
        </T>
        {!u.read && <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: colors.danger }} />}
      </View>
      <T size={14} weight="bold" numberOfLines={2}>
        {u.title}
      </T>
      {!compact && (
        <View style={{ backgroundColor: colors.surface, borderRadius: 8, paddingHorizontal: 8, height: 26, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <Icon name="link" size={11} color={colors.textSub} />
          <T size={11} weight="medium" numberOfLines={1} style={{ flex: 1 }}>
            {u.memo_title}
          </T>
        </View>
      )}
    </Hoverable>
  );
}
