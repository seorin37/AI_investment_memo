import React, { useMemo, useState } from 'react';
import { View } from 'react-native';
import { Icon, type IconName } from '@/components/icons/Icon';
import { Sheet } from '@/components/ui/Modal';
import { EmptyState, Hoverable, IconButton, Loading, TextField } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { usePurgeTrash, useRestoreTrash, useTrash } from '@/hooks/queries';
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
    <Sheet visible onClose={onClose} width={560} padding={24} radius={24}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
        <View style={{ flex: 1, gap: 4 }}>
          <T size={20} weight="bold">
            휴지통
          </T>
          <T size={14} color={colors.textSub}>
            삭제한 항목을 확인하고 복원할 수 있어요.
          </T>
        </View>
        <IconButton name="x" label="닫기" onPress={onClose} size={20} color={colors.text} box={36} />
      </View>
      <TextField value={q} onChangeText={setQ} placeholder="휴지통에서 항목 검색" style={{ marginTop: 18, backgroundColor: '#F7F8FA', borderColor: '#F7F8FA', height: 44 }} />
      <View style={{ marginTop: 16, zIndex: 10, alignSelf: 'flex-start' }}>
        <Hoverable onPress={() => setMenu((m) => !m)} style={{ height: 32, paddingHorizontal: 12, borderRadius: 8, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <T size={13}>{filter === 'all' ? '유형' : FILTERS.find((f) => f.key === filter)?.label}</T>
          <Icon name="chevronDown" size={14} color={colors.text} />
        </Hoverable>
        {menu && (
          <View style={{ position: 'absolute', top: 36, left: 0, width: 140, backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: colors.border, padding: 4, ...shadow.pop }}>
            {FILTERS.map((f) => (
              <Hoverable
                key={f.key}
                onPress={() => {
                  setFilter(f.key);
                  setMenu(false);
                }}
                style={{ height: 34, paddingHorizontal: 10, borderRadius: 6, justifyContent: 'center' }}
                hoverStyle={{ backgroundColor: '#F4F5F7' }}
              >
                <T size={13} weight={filter === f.key ? 'semibold' : 'regular'}>
                  {f.label}
                </T>
              </Hoverable>
            ))}
          </View>
        )}
      </View>
      <View style={{ flexDirection: 'row', gap: 6, marginTop: 16, marginBottom: 6 }}>
        <T size={12} color={colors.textSub}>
          삭제한 항목
        </T>
        <T size={12} weight="semibold">
          {list.length}
        </T>
      </View>
      {isLoading && <Loading />}
      {data && list.length === 0 && <EmptyState title={q || filter !== 'all' ? '조건에 맞는 항목이 없어요' : '휴지통이 비어 있어요'} />}
      {list.map((t) => (
        <View key={t.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 12, paddingHorizontal: 8 }}>
          <Icon name={KIND_ICON[t.kind]} size={20} color={colors.textBody} />
          <View style={{ flex: 1 }}>
            <T size={15} weight="medium">
              {t.title}
            </T>
            <T size={12} color={colors.textSub}>
              {t.context} · {deletedLabel(t.deleted_at)}
            </T>
          </View>
          {confirmId === t.id ? (
            <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
              <T size={12} color={colors.danger}>
                영구 삭제할까요?
              </T>
              <Hoverable onPress={() => purge.mutate(t.id, { onSuccess: () => toast('영구 삭제했어요') })} style={{ paddingHorizontal: 10, height: 28, borderRadius: 6, backgroundColor: colors.danger, justifyContent: 'center' }}>
                <T size={12} color="#FFF" weight="semibold">
                  삭제
                </T>
              </Hoverable>
              <Hoverable onPress={() => setConfirmId(null)} style={{ paddingHorizontal: 10, height: 28, borderRadius: 6, backgroundColor: '#F2F3F5', justifyContent: 'center' }}>
                <T size={12}>취소</T>
              </Hoverable>
            </View>
          ) : (
            <>
              <IconButton name="undo" label="복원" onPress={() => restore.mutate(t.id, { onSuccess: () => toast(`‘${t.title}’을(를) 복원했어요`) })} color={colors.text} />
              <IconButton name="trash" label="영구 삭제" onPress={() => setConfirmId(t.id)} color={colors.text} />
            </>
          )}
        </View>
      ))}
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 20 }}>
        <T size={12} color={colors.textSub}>
          보관 기간과 자동 삭제 여부는 추후 안내합니다.
        </T>
        <Icon name="help" size={16} color={colors.textSub} />
      </View>
    </Sheet>
  );
}
