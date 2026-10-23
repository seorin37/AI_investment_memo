import React, { useMemo, useState } from 'react';
import { ScrollView, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Icon } from '@/components/icons/Icon';
import { EmptyState, Hoverable, IconButton, Loading, TextField } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { JournalEditor } from '@/features/journal/JournalEditor';
import { useCreateJournal, useDeleteJournal, useJournal } from '@/hooks/queries';
import { useBreakpoint } from '@/hooks/useLayout';
import { korMonthDay, uid } from '@/lib/format';
import { useUI } from '@/store/ui';
import { colors } from '@/theme/tokens';
import type { JournalEntry } from '@/types/models';

const preview = (j: JournalEntry) =>
  j.blocks
    .map((b) => ('text' in b ? b.text : ''))
    .find((t) => t.trim()) ?? '';

/** 5. 투자 기록 — 아이폰 메모처럼: 목록 + 편집기 + 떠 있는 도구 막대 */
export default function JournalScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const router = useRouter();
  const { data, isLoading } = useJournal();
  const create = useCreateJournal();
  const remove = useDeleteJournal();
  const toast = useUI((s) => s.showToast);
  const { isMobile } = useBreakpoint();
  const [q, setQ] = useState('');
  const [picked, setSelected] = useState<string | null>(id ?? null);
  // 검색 결과 등에서 ?id= 로 들어오면 그 기록을 선택 (렌더 중 상태 조정 패턴)
  const [lastId, setLastId] = useState(id);
  if (id !== lastId) {
    setLastId(id);
    setSelected(id ?? null);
  }

  const list = useMemo(() => {
    const k = q.trim().toLowerCase();
    return (data ?? []).filter((j) => !k || j.title.toLowerCase().includes(k) || preview(j).toLowerCase().includes(k));
  }, [data, q]);

  // 데스크톱은 선택이 없으면 첫 기록을 보여줌
  const selected = picked ?? (!isMobile ? (list[0]?.id ?? null) : null);
  const entry = data?.find((j) => j.id === selected) ?? null;

  const newEntry = () =>
    create.mutate({ title: '', stock_code: null, blocks: [{ id: uid('b'), type: 'paragraph', text: '' }] }, { onSuccess: (e) => setSelected(e.id) });

  const del = (j: JournalEntry) =>
    remove.mutate(j.id, {
      onSuccess: () => {
        toast('기록을 휴지통으로 옮겼어요');
        setSelected(null);
        if (id) router.setParams({ id: undefined });
      },
    });

  const searchBox = (
      <TextField
        icon="search"
        value={q}
        onChangeText={setQ}
        placeholder="검색"
        placeholderTextColor={colors.textMuted}
        accessibilityLabel="투자 기록 검색"
        style={{ height: 36, width: isMobile ? undefined : 240, flex: isMobile ? 1 : undefined, borderRadius: 18, backgroundColor: colors.surfaceSubtle, borderColor: colors.surfaceSubtle }}
        inputStyle={{ fontSize: 13 }}
      />
  );

  const listView = (
    <View style={{ width: isMobile ? '100%' : 260, paddingHorizontal: 10, paddingTop: isMobile ? 12 : 16, flex: isMobile ? 1 : undefined }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12, marginBottom: 16 }}>
        <View>
          <T size={16} weight="bold">
            투자 기록
          </T>
          <T size={11} color={colors.textSub}>
            {data?.length ?? 0}개의 기록
          </T>
        </View>
        <IconButton name="pencil" label="새 기록" onPress={newEntry} color={colors.brand} size={16} box={36} style={{ borderRadius: 18, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface }} />
      </View>
      {isMobile && <View style={{ flexDirection: 'row', paddingHorizontal: 8, marginBottom: 12 }}>{searchBox}</View>}
      {isLoading && <Loading />}
      <ScrollView contentContainerStyle={{ gap: 2, paddingBottom: 40 }}>
        {list.map((j) => {
          const on = j.id === selected;
          return (
            <Hoverable
              key={j.id}
              accessibilityState={{ selected: on }}
              onPress={() => setSelected(j.id)}
              style={[{ paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10, gap: 4 }, on && { backgroundColor: colors.brandSoft }]}
              hoverStyle={!on && { backgroundColor: colors.brandSoft }}
            >
              <T size={14} weight="bold" color={on ? colors.brand : colors.text} numberOfLines={1}>
                {j.title || '새로운 기록'}
              </T>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <T size={12} weight="semibold">
                  {korMonthDay(j.created_at)}
                </T>
                <T size={12} color={colors.textSub} numberOfLines={1} style={{ flex: 1 }}>
                  {preview(j) || '추가 텍스트 없음'}
                </T>
              </View>
            </Hoverable>
          );
        })}
        {data && list.length === 0 && <EmptyState title={q ? '검색 결과가 없어요' : '아직 기록이 없어요'} desc={q ? undefined : '연필 버튼으로 오늘의 판단을 남겨 보세요.'} />}
      </ScrollView>
    </View>
  );

  if (isMobile) {
    if (!entry) return <View style={{ flex: 1 }}>{listView}</View>;
    return (
      <View style={{ flex: 1 }}>
        <View style={{ height: 48, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8 }}>
          <Hoverable onPress={() => setSelected(null)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, padding: 8 }}>
            <Icon name="chevronLeft" size={18} color={colors.brand} />
            <T size={15} color={colors.brand}>
              투자 기록
            </T>
          </Hoverable>
        </View>
        <JournalEditor key={entry.id} entry={entry} onDelete={() => del(entry)} />
      </View>
    );
  }

  return (
    <View style={{ flex: 1, flexDirection: 'row' }}>
      {listView}
      <View style={{ flex: 1 }}>
        <View style={{ position: 'absolute', top: 15, right: 24, zIndex: 5 }}>{searchBox}</View>
        {entry ? (
          <JournalEditor key={entry.id} entry={entry} onDelete={() => del(entry)} />
        ) : (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <EmptyState title="기록을 선택하거나 새로 작성해 보세요" />
          </View>
        )}
      </View>
    </View>
  );
}
