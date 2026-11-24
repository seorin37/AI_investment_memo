import React, { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import { Text, TextInput } from '@/components/ui/AppText';
import { AppSnackbar } from '@/ui/shared/Snackbar';
import type { TrashItem } from '../My.mock';
import type { TrashProps } from '../My.types';
import { ConfirmSheet, Foot, Grp, MC, OkIcon, Page, Rv } from './parts';

/**
 * 앱 휴지통 = 원본 app/my.html openTrash()
 * 검색 칸 · 칸 고르기(전체 N · 메모 · 투자 기록 · 종목) · 목록(아이콘 36 · 제목 14.5 · '어디 · 언제 삭제' · [복원] [영구 삭제]) · 비었을 때 · 안내
 * 복원: 목록에서 빠지고 5초 되돌리기 · 영구 삭제: 확인 시트까지만 (mock 에서도 지우지 않음)
 */
type Filter = '전체' | TrashItem['kind'];

export function AppTrash({ items, onBack, onRestore, onUndo, onPurge }: TrashProps) {
  const [q, setQ] = useState('');
  const [f, setF] = useState<Filter>('전체');
  const [ask, setAsk] = useState<TrashItem | null>(null);
  const [snack, setSnack] = useState<TrashItem | null>(null);
  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack(null), 5000);
    return () => clearTimeout(t);
  }, [snack]);
  const closeAsk = useCallback(() => {
    if (!ask) return false;
    setAsk(null);
    return true;
  }, [ask]);
  const count = (k: Filter) => items.filter((t) => k === '전체' || t.kind === k).length;
  const list = items.filter((t) => (f === '전체' || t.kind === f) && (!q.trim() || t.title.includes(q.trim()) || t.sub.includes(q.trim())));
  return (
    <View style={{ flex: 1 }}>
      <Page title="휴지통" lead="삭제한 항목을 확인하고 복원할 수 있어요." onBack={onBack} onHardwareBack={closeAsk}>
        <Rv i={0}>
          <View style={st.search}>
            <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="#9A9EA7" strokeWidth={2}><Circle cx={11} cy={11} r={7} /><Path d="M20 20l-4-4" /></Svg>
            <TextInput value={q} onChangeText={setQ} placeholder="휴지통에서 항목 검색" placeholderTextColor={MC.ink3} style={st.searchIn} accessibilityLabel="휴지통에서 항목 검색" returnKeyType="search" />
          </View>
        </Rv>
        <Rv i={1}>
          <View style={st.fch}>
            {(['전체', '메모', '투자 기록', '종목'] as Filter[]).map((k) => (
              <Pressable key={k} onPress={() => setF(k)} style={[st.fb, f === k && st.fbOn]} accessibilityRole="tab" accessibilityState={{ selected: f === k }}>
                <Text style={[st.fbT, f === k && { color: '#FFFFFF' }]}>{k} {count(k)}</Text>
              </Pressable>
            ))}
          </View>
        </Rv>
        <Rv i={2}>
          {list.length ? (
            <Grp>
              {list.map((t, i) => (
                <View key={t.id} style={[st.tr, i === list.length - 1 && { borderBottomWidth: 0 }]}>
                  <View style={st.ic2}>{t.kind === '종목' ? <BagIcon /> : <NoteIcon />}</View>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={st.trB} numberOfLines={1}>{t.title}</Text>
                    <Text style={st.trS} numberOfLines={1}>{t.sub} · {t.ago} 삭제</Text>
                  </View>
                  <View style={st.acts}>
                    <Pressable onPress={() => { onRestore(t); setSnack(t); }} style={({ pressed }) => [st.act, pressed && { backgroundColor: '#F1F2F4' }]} accessibilityRole="button" accessibilityLabel={`${t.title} 복원`}><RestoreIcon /></Pressable>
                    <Pressable onPress={() => setAsk(t)} style={({ pressed }) => [st.act, pressed && { backgroundColor: '#FFF5F5' }]} accessibilityRole="button" accessibilityLabel={`${t.title} 영구 삭제`}><TrashIcon /></Pressable>
                  </View>
                </View>
              ))}
            </Grp>
          ) : (
            <View style={st.empt}>
              <View style={st.ok}><OkIcon size={28} /></View>
              <Text style={st.emptB}>{items.length ? '찾는 항목이 없어요' : '휴지통이 비어 있어요'}</Text>
              <Text keepAll style={st.emptS}>{items.length ? '다른 말로 찾아보세요' : '삭제한 메모·기록·종목이 여기에 30일 동안 보관돼요'}</Text>
            </View>
          )}
        </Rv>
        <Rv i={3}><Foot>영구 삭제하기 전까지 복원할 수 있어요.</Foot></Rv>
      </Page>
      <AppSnackbar visible={!!snack} message="원래 자리로 복원했어요" onUndo={() => { if (snack) onUndo(snack); setSnack(null); }} style={st.snack} />
      <ConfirmSheet
        open={!!ask}
        red
        title="영구 삭제할까요?"
        /* 종목: 원본 웹에 종목용 문구가 없어 새로 씀 */
        body={ask?.kind === '종목' ? '이 종목과 메모를 영구 삭제할까요? 되돌릴 수 없어요.' : '삭제하면 되돌릴 수 없어요. 이 메모의 수정 이력과 받은 소식도 함께 지워져요.'}
        ok="영구 삭제"
        onCancel={() => setAsk(null)}
        onOk={() => { const t = ask; setAsk(null); onPurge(t); }}
      />
    </View>
  );
}

function NoteIcon() {
  return <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="#575B63" strokeWidth={1.8} strokeLinejoin="round"><Path d="M5 4h14v11l-5 5H5z" /><Path d="M14 20v-5h5" /></Svg>;
}
function BagIcon() {
  return <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="#575B63" strokeWidth={1.8}><Rect x={3} y={7} width={18} height={13} rx={2.5} /><Path d="M9 7V5h6v2" /></Svg>;
}
function RestoreIcon() {
  return <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="#575B63" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><Path d="M9 14L4 9l5-5" /><Path d="M4 9h10a6 6 0 0 1 0 12h-3" /></Svg>;
}
function TrashIcon() {
  return <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={MC.red} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><Path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></Svg>;
}

const st = StyleSheet.create({
  search: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#FFFFFF', borderRadius: 14, paddingHorizontal: 14, minHeight: 46 },
  searchIn: { flex: 1, fontSize: 14, lineHeight: 20, color: MC.ink, paddingVertical: 12 },
  fch: { flexDirection: 'row', gap: 6, marginTop: 1, marginBottom: 12, flexWrap: 'wrap' },
  fb: { borderWidth: 1, borderColor: '#DADDE2', backgroundColor: '#FFFFFF', borderRadius: 999, paddingVertical: 7, paddingHorizontal: 12, minHeight: 34, justifyContent: 'center' },
  fbOn: { backgroundColor: MC.a, borderColor: MC.a },
  fbT: { fontSize: 13, lineHeight: 18, fontWeight: '600', color: MC.ink },
  tr: { flexDirection: 'row', alignItems: 'center', gap: 12, height: 60, paddingHorizontal: 14, borderBottomWidth: 1, borderBottomColor: '#F1F2F4' },
  ic2: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#F1F2F4', alignItems: 'center', justifyContent: 'center' },
  trB: { fontSize: 14.5, lineHeight: 21, fontWeight: '700', color: MC.ink },
  trS: { fontSize: 12, lineHeight: 17, color: MC.ink3 },
  acts: { flexDirection: 'row', gap: 4 },
  act: { width: 40, height: 40, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  empt: { alignItems: 'center', paddingVertical: 26, paddingHorizontal: 20 },
  ok: { width: 70, height: 70, borderRadius: 35, backgroundColor: MC.aSoft, alignItems: 'center', justifyContent: 'center', marginBottom: 22 },
  emptB: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: MC.ink },
  emptS: { fontSize: 12.5, lineHeight: 18, color: MC.ink3, marginTop: 4, textAlign: 'center' },
  snack: { position: 'absolute', left: 12, right: 12, bottom: 28 },
});
