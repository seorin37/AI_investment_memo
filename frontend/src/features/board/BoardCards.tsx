import React, { useRef } from 'react';
import { Linking, Platform, Pressable, View } from 'react-native';
import { Icon, type IconName } from '@/components/icons/Icon';
import { AiToggle, CircleCheck, Hoverable, ProgressRing } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { dotDate } from '@/lib/format';
import { colors, memoPalette, shadow } from '@/theme/tokens';
import type { Checklist, Memo, ReferenceBoard, ReferenceType } from '@/types/models';

/** 색 메모 카드 (보드) */
export function MemoCard({ memo, onPress, onToggleAi }: { memo: Memo; onPress: () => void; onToggleAi: (v: boolean) => void }) {
  const tone = memoPalette[memo.color];
  return (
    <Hoverable
      accessibilityRole="button"
      accessibilityLabel={`메모 ${memo.title}`}
      onPress={onPress}
      style={{
        backgroundColor: tone.bg,
        borderRadius: 6,
        borderWidth: 1,
        borderColor: tone.border,
        paddingHorizontal: 22,
        paddingTop: 20,
        paddingBottom: 22,
        gap: 8,
        ...shadow.card,
      }}
      hoverStyle={{ transform: [{ translateY: -2 }], shadowOpacity: 0.1 }}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <T size={12} color="#8E8A97" tabular>
          {dotDate(memo.created_at)}
        </T>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          {memo.pinned && <Icon name="pin" size={14} color="#8E8A97" />}
          <AiToggle value={memo.ai_linked} onChange={onToggleAi} />
        </View>
      </View>
      <T size={19} weight="bold" color="#16151B" lh={1.35}>
        {memo.title}
      </T>
      {memo.body ? (
        <T size={15} color={colors.textWarm} lh={1.5} numberOfLines={6}>
          {memo.body}
        </T>
      ) : null}
      {memo.tags.length > 0 && (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 6 }}>
          {memo.tags.map((t) => (
            <T key={t} size={11} weight="medium" color="#504B58">
              #{t}
            </T>
          ))}
        </View>
      )}
      {memo.unread_updates > 0 && memo.ai_linked && (
        <View style={{ position: 'absolute', top: -6, right: -6, minWidth: 18, height: 18, borderRadius: 9, backgroundColor: colors.danger, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4 }}>
          <T size={10} weight="bold" color="#FFF" lh={1}>
            {memo.unread_updates}
          </T>
        </View>
      )}
    </Hoverable>
  );
}

/** 체크리스트 카드 */
export function ChecklistCard({ item, onPress, onToggle }: { item: Checklist; onPress: () => void; onToggle: (itemId: string, done: boolean) => void }) {
  const done = item.items.filter((i) => i.done).length;
  return (
    <View style={{ backgroundColor: colors.surface, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 4, ...shadow.card }}>
      <Pressable onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <View>
          <T size={15} weight="bold">
            {item.title}
          </T>
          <T size={10} color={colors.textMuted}>
            하나씩 확인해 보세요
          </T>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          {item.pinned && <Icon name="pin" size={14} color="#8E8A97" />}
          <ProgressRing done={done} total={item.items.length} size={32} />
        </View>
      </Pressable>
      {item.items.map((it, i) => (
        <View key={it.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 7, borderTopWidth: i === 0 ? 1 : 0, borderBottomWidth: 1, borderColor: colors.borderSoft }}>
          <CircleCheck checked={it.done} onPress={() => onToggle(it.id, !it.done)} size={18} />
          <T size={12} color={it.done ? colors.textMuted : colors.textBody} strike={it.done} style={{ flex: 1 }}>
            {it.text}
          </T>
        </View>
      ))}
      {item.items.length === 0 && (
        <T size={12} color={colors.textMuted} style={{ paddingVertical: 8 }}>
          눌러서 확인할 항목을 추가하세요
        </T>
      )}
    </View>
  );
}

const refIcon: Record<ReferenceType, IconName> = { ir: 'link', news: 'newspaper', report: 'file', disclosure: 'fileText', etc: 'link' };
export const refTypeLabel: Record<ReferenceType, string> = { ir: '기업 IR', news: '뉴스 모음', report: '산업 분석', disclosure: '공시', etc: '기타' };

/** 참고 자료 카드 */
export function ReferenceCard({ item, onPress }: { item: ReferenceBoard; onPress: () => void }) {
  return (
    <View style={{ backgroundColor: colors.surface, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 6, ...shadow.card }}>
      <Pressable onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <T size={15} weight="bold">
          {item.title}
        </T>
        <T size={10} color={colors.textMuted}>
          {item.links.length}개
        </T>
      </Pressable>
      {item.links.map((l) => (
        <Hoverable
          key={l.id}
          onPress={() => void Linking.openURL(l.url)}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6, borderRadius: 8 }}
          hoverStyle={{ backgroundColor: '#F8F9FA' }}
        >
          <View style={{ width: 28, height: 28, borderRadius: 8, backgroundColor: '#F3F4F6', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name={refIcon[l.ref_type]} size={14} color={colors.textSub} />
          </View>
          <View style={{ flex: 1 }}>
            <T size={12} weight="medium" numberOfLines={1}>
              {l.title}
            </T>
            <T size={9} color={colors.textMuted}>
              {refTypeLabel[l.ref_type]} · {l.source === 'file' ? '파일' : l.ref_type === 'report' ? '리포트' : '링크'}
            </T>
          </View>
          <Icon name="external" size={12} color={colors.textMuted} />
        </Hoverable>
      ))}
    </View>
  );
}

/** 새 메모 (웹: 더블클릭 / 모바일: 탭) */
export function NewMemoCard({ onOpen }: { onOpen: () => void }) {
  const last = useRef(0);
  const handle = () => {
    if (Platform.OS !== 'web') return onOpen();
    const now = Date.now();
    if (now - last.current < 350) onOpen();
    last.current = now;
  };
  return (
    <Hoverable
      accessibilityRole="button"
      accessibilityLabel="새 메모"
      accessibilityHint={Platform.OS === 'web' ? '더블클릭하면 새 메모를 만들어요' : undefined}
      onPress={handle}
      style={{
        height: 120,
        borderRadius: 16,
        borderWidth: 1.2,
        borderStyle: 'dashed',
        borderColor: '#D5D8DE',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      hoverStyle={{ backgroundColor: '#FAFAFB', borderColor: '#B9BEC7' }}
    >
      <T size={12} color={colors.textSub} align="center">
        + 새 메모{'\n'}
        {Platform.OS === 'web' ? '(더블클릭)' : '(탭해서 만들기)'}
      </T>
    </Hoverable>
  );
}
