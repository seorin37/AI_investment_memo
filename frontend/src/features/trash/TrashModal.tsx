import React, { useMemo, useState } from 'react';
import { ScrollView, View } from 'react-native';
import { Icon, type IconName } from '@/components/icons/Icon';
import { Sheet } from '@/components/ui/Modal';
import { Button, EmptyState, Hoverable, IconButton, Loading, TextField } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { usePurgeTrash, useRestoreTrash, useTrash } from '@/hooks/queries';
import { useBreakpoint } from '@/hooks/useLayout';
import { deletedLabel } from '@/lib/format';
import { useUI } from '@/store/ui';
import { colors, shadow } from '@/theme/tokens';
import type { TrashKind } from '@/types/models';

const KIND_ICON: Record<TrashKind, IconName> = { memo: 'pencil', checklist: 'listChecks', reference: 'link', journal: 'fileText', stock: 'briefcase' };
const FILTERS: { key: 'all' | TrashKind; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'memo', label: '메모' },
  { key: 'checklist', label: '체크리스트' },
  { key: 'reference', label: '참고자료' },
  { key: 'journal', label: '투자 기록' },
  { key: 'stock', label: '종목' },
];

/** 10. 휴지통 — 검색 + 유형 필터 (최종 수정본) */
export function TrashModal({ onClose }: { onClose: () => void }) {
  const { height, isMobile } = useBreakpoint();
  const compact = height < 480;
  const modalHeight = Math.min(560, height * (isMobile ? 0.92 : 0.94), height - (isMobile ? 0 : 40));
  const { data, isLoading } = useTrash();
  const restore = useRestoreTrash();
  const purge = usePurgeTrash();
  const toast = useUI((s) => s.showToast);
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState<'all' | TrashKind>('all');
  const [menu, setMenu] = useState(false);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const list = useMemo(
    () => (data ?? []).filter((t) => (filter === 'all' || t.kind === filter) && (!q.trim() || t.title.includes(q.trim()) || t.context.includes(q.trim()))),
    [data, filter, q],
  );

  return (
    <Sheet visible onClose={onClose} width={560} padding={compact ? 16 : 24} radius={24} scroll={false} style={{ height: modalHeight }}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-start', flexShrink: 0 }}>
        <View style={{ flex: 1, gap: 4 }}>
          <T size={20} weight="bold">
            휴지통
          </T>
          <T size={compact ? 12 : 14} color={colors.textSub}>
            삭제한 항목을 확인하고 복원할 수 있어요.
          </T>
        </View>
        <IconButton name="x" label="닫기" onPress={onClose} size={20} color={colors.text} box={36} />
      </View>
      <TextField value={q} onChangeText={setQ} placeholder="휴지통에서 항목 검색" style={{ marginTop: compact ? 8 : 18, flexShrink: 0, backgroundColor: '#F7F8FA', borderColor: '#F7F8FA', height: 44 }} />
      <View style={{ marginTop: compact ? 8 : 16, zIndex: 10, flexShrink: 0, alignSelf: 'flex-start' }}>
        <Hoverable accessibilityLabel="유형 필터" accessibilityState={{ expanded: menu }} onPress={() => setMenu((m) => !m)} style={{ height: 32, paddingHorizontal: 12, borderRadius: 8, borderWidth: 1, borderColor: menu ? colors.brand : colors.border, flexDirection: 'row', alignItems: 'center', gap: 8 }} hoverStyle={{ backgroundColor: colors.brandSoft }}>
          <T size={13}>{filter === 'all' ? '유형' : FILTERS.find((f) => f.key === filter)?.label}</T>
          <Icon name="chevronDown" size={14} color={colors.text} />
        </Hoverable>
        {menu && (
          <View style={{ position: 'absolute', top: 36, left: 0, width: 140, backgroundColor: colors.surface, borderRadius: 10, borderWidth: 1, borderColor: colors.border, padding: 4, ...shadow.pop }}>
            <ScrollView style={{ maxHeight: Math.max(34, modalHeight - (compact ? 190 : 230)) }} keyboardShouldPersistTaps="handled">
              {FILTERS.map((f) => (
                <Hoverable
                  key={f.key}
                  accessibilityState={{ selected: filter === f.key }}
                  onPress={() => {
                    setFilter(f.key);
                    setMenu(false);
                  }}
                  style={{ height: 34, paddingHorizontal: 10, borderRadius: 6, justifyContent: 'center', backgroundColor: filter === f.key ? colors.brandSoft : undefined }}
                  hoverStyle={{ backgroundColor: colors.brandSoft }}
                >
                  <T size={13} weight={filter === f.key ? 'semibold' : 'regular'} color={filter === f.key ? colors.brand : colors.text}>
                    {f.label}
                  </T>
                </Hoverable>
              ))}
            </ScrollView>
          </View>
        )}
      </View>
      <View style={{ flexDirection: 'row', gap: 6, marginTop: compact ? 8 : 16, marginBottom: 6, flexShrink: 0 }}>
        <T size={12} color={colors.textSub}>
          삭제한 항목
        </T>
        <T size={12} weight="semibold">
          {list.length}
        </T>
      </View>
      <ScrollView style={{ flex: 1, minHeight: 0 }} keyboardShouldPersistTaps="handled">
        {isLoading && <Loading height={80} />}
        {data && list.length === 0 && <EmptyState title={q || filter !== 'all' ? '조건에 맞는 항목이 없어요' : '휴지통이 비어 있어요'} />}
        {list.map((t) => (
          <View key={t.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 12, paddingHorizontal: 8, flexWrap: 'wrap' }}>
            <Icon name={KIND_ICON[t.kind]} size={20} color={colors.textBody} />
            <View style={{ flex: 1, minWidth: 0 }}>
              <T numberOfLines={2} size={15} weight="medium">
                {t.title}
              </T>
              <T size={12} color={colors.textSub}>
                {t.context} · {deletedLabel(t.deleted_at)}
              </T>
            </View>
            {confirmId === t.id ? (
              <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center', flexWrap: 'wrap', width: isMobile ? '100%' : undefined, justifyContent: 'flex-end' }}>
                <T size={12} color={colors.danger}>
                  영구 삭제할까요?
                </T>
                <Button label="삭제" variant="danger" size="sm" onPress={() => purge.mutate(t.id, { onSuccess: () => toast('영구 삭제했어요') })} />
                <Button label="취소" variant="secondary" size="sm" onPress={() => setConfirmId(null)} />
              </View>
            ) : (
              <>
                <IconButton name="undo" label="복원" onPress={() => restore.mutate(t.id, { onSuccess: () => toast(`‘${t.title}’을(를) 복원했어요`) })} color={colors.text} />
                <IconButton name="trash" label="영구 삭제" onPress={() => setConfirmId(t.id)} color={colors.text} />
              </>
            )}
          </View>
        ))}
      </ScrollView>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexShrink: 0, marginTop: compact ? 8 : 20 }}>
        <T size={12} color={colors.textSub} style={{ flex: 1 }}>
          보관 기간과 자동 삭제 여부는 추후 안내합니다.
        </T>
        <Icon name="help" size={16} color={colors.textSub} />
      </View>
    </Sheet>
  );
}
