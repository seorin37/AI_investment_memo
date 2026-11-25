import React, { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View, BackHandler } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { MiniSpace } from '@/ui/screens/studio/app/MiniBar';
import { Text } from '@/components/ui/AppText';
import type { InboxItem } from '../My.mock';
import type { InboxProps } from '../My.types';
import { Chev, Grp, Head, Lb, MC, Rv } from './parts';

/**
 * 앱 알림함 = 원본 app/my.html inboxHTML() (홈 위쪽 종 버튼)
 * 머리 '알림' + [모두 읽음] · 칸(전체 · AI 업데이트 · 스튜디오 — 켠 알림만) · 오늘/어제 묶음 · 안 읽음 빨간 점 8
 * 비었을 때 · [알림 설정 · MY › 알림 ›]. 읽음은 화면 상태만.
 */
type F = 'all' | 'ai' | 'studio';

export function AppInbox({ items, unread, noti, onBack, onOpen, onReadAll, onSettings }: InboxProps) {
  const insets = useSafeAreaInsets();
  const [f, setF] = useState<F>('all');
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      onBack();
      return true;
    });
    return () => sub.remove();
  }, [onBack]);
  const fv: F = f !== 'all' && !noti[f] ? 'all' : f;
  const on = items.filter((n) => noti[n.kind] && (fv === 'all' || fv === n.kind));
  const groups = (['오늘', '어제', '이전'] as const).map((g) => [g, on.filter((n) => n.day === g)] as const).filter(([, l]) => l.length);
  const anyOn = noti.ai || noti.studio;
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <View style={st.hdRow}>
        <View style={{ flex: 1 }}><Head title="알림" onBack={onBack} /></View>
        <Pressable onPress={onReadAll} style={st.all} accessibilityRole="button"><Text style={st.allT}>모두 읽음</Text></Pressable>
      </View>
      <ScrollView contentContainerStyle={[st.w, { paddingBottom: 28 + insets.bottom }]} showsVerticalScrollIndicator={false}>
        {anyOn ? (
          <Rv i={0}>
            <View style={st.fch}>
              {([['all', '전체'], ['ai', 'AI 업데이트'], ['studio', '스튜디오']] as const).filter(([k]) => k === 'all' || noti[k]).map(([k, l]) => (
                <Pressable key={k} onPress={() => setF(k)} style={[st.fb, fv === k && st.fbOn]} accessibilityRole="tab" accessibilityState={{ selected: fv === k }}>
                  <Text style={[st.fbT, fv === k && { color: '#FFFFFF' }]}>{l}</Text>
                </Pressable>
              ))}
            </View>
          </Rv>
        ) : null}
        {groups.length ? (
          groups.map(([g, list], gi) => (
            <React.Fragment key={g}>
              <Rv i={gi * 2 + 1}><Lb style={gi === 0 ? { marginTop: 0 } : undefined}>{g}</Lb></Rv>
              <Rv i={gi * 2 + 2}>
                <Grp>{list.map((n, i) => <Row key={n.id} n={n} unread={unread.includes(n.id)} last={i === list.length - 1} onPress={() => onOpen(n)} />)}</Grp>
              </Rv>
            </React.Fragment>
          ))
        ) : (
          <View style={st.empt}>
            <View style={st.ok}>
              <Svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="#9A9EA7" strokeWidth={1.9}><Path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z" /><Path d="M10 20h4" /><Path d="M4 4l16 16" strokeLinecap="round" /></Svg>
            </View>
            <Text style={st.emptB}>{anyOn ? '새 알림이 없어요' : '알림을 모두 꺼 두었어요'}</Text>
            <Text style={st.emptS}>MY › 알림에서 켠 알림만 여기에 와요</Text>
          </View>
        )}
        <Rv i={6}>
          <Pressable onPress={onSettings} style={({ pressed }) => [st.set, pressed && { backgroundColor: '#F7F7F9' }]} accessibilityRole="button">
            <View style={{ flex: 1 }}>
              <Text style={st.setB}>알림 설정</Text>
              <Text style={st.setS}>AI 업데이트 {noti.ai ? '켜짐' : '꺼짐'} · 스튜디오 {noti.studio ? '켜짐' : '꺼짐'}</Text>
            </View>
            <Text style={st.setV}>MY › 알림</Text>
            <Chev />
          </Pressable>
        </Rv>
        <MiniSpace />
      </ScrollView>
    </View>
  );
}

function Row({ n, unread, last, onPress }: { n: InboxItem; unread: boolean; last: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [st.tr, last && { borderBottomWidth: 0 }, pressed && { backgroundColor: '#F7F7F9' }]} accessibilityRole="button" accessibilityLabel={`${unread ? '안 읽음 ' : ''}${n.title}`}>
      <View style={[st.ic2, { backgroundColor: n.kind === 'ai' ? MC.aSoft : '#FFF1D6' }]}>
        {n.kind === 'ai' ? (
          <Svg width={18} height={18} viewBox="0 0 24 24" fill="none"><Path d="M9 3V7M15 3V7" stroke="#6A42AB" strokeWidth={2.4} strokeLinecap="round" /><Path d="M6.5 7H17.5V11C17.5 12.46 16.92 13.86 15.89 14.89C14.86 15.92 13.46 16.5 12 16.5C10.54 16.5 9.14 15.92 8.11 14.89C7.08 13.86 6.5 12.46 6.5 11V7Z" fill="#6A42AB" /><Path d="M12 16.5V21" stroke="#6A42AB" strokeWidth={2.4} strokeLinecap="round" /></Svg>
        ) : (
          <Svg width={18} height={18} viewBox="0 0 24 24" fill="#C98A00"><Path d="M12 4l1.6 4.4L18 10l-4.4 1.6L12 16l-1.6-4.4L6 10l4.4-1.6z" /></Svg>
        )}
      </View>
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={st.trB} numberOfLines={1}>{n.title}</Text>
        <Text keepAll style={st.trS}>{n.sub}</Text>
        <Text style={st.trS}>{n.when}</Text>
      </View>
      {unread ? <View style={st.udot} /> : null}
    </Pressable>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: MC.bg },
  hdRow: { flexDirection: 'row', alignItems: 'center', paddingRight: 10 },
  all: { padding: 8, minHeight: 44, justifyContent: 'center' },
  allT: { fontSize: 13.5, lineHeight: 20, fontWeight: '700', color: MC.a2 },
  w: { paddingHorizontal: 16 },
  fch: { flexDirection: 'row', gap: 6, marginBottom: 12 },
  fb: { borderWidth: 1, borderColor: '#DADDE2', backgroundColor: '#FFFFFF', borderRadius: 999, paddingVertical: 7, paddingHorizontal: 12, minHeight: 34, justifyContent: 'center' },
  fbOn: { backgroundColor: MC.a, borderColor: MC.a },
  fbT: { fontSize: 13, lineHeight: 18, fontWeight: '600', color: MC.ink },
  tr: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, paddingHorizontal: 14, borderBottomWidth: 1, borderBottomColor: '#F1F2F4' },
  ic2: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  trB: { fontSize: 14.5, lineHeight: 21, fontWeight: '700', color: MC.ink },
  trS: { fontSize: 12, lineHeight: 17, color: MC.ink3 },
  udot: { width: 8, height: 8, borderRadius: 4, backgroundColor: MC.red },
  empt: { alignItems: 'center', paddingVertical: 26, paddingHorizontal: 20 },
  ok: { width: 70, height: 70, borderRadius: 35, backgroundColor: '#F1F2F4', alignItems: 'center', justifyContent: 'center', marginBottom: 22 },
  emptB: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: MC.ink },
  emptS: { fontSize: 12.5, lineHeight: 18, color: MC.ink3, marginTop: 4 },
  set: { marginTop: 12, flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 52, paddingVertical: 12, paddingHorizontal: 16, backgroundColor: '#FFFFFF', borderRadius: 18 },
  setB: { fontSize: 14, lineHeight: 20, fontWeight: '500', color: MC.ink },
  setS: { fontSize: 12, lineHeight: 17.4, color: MC.ink3, marginTop: 2 },
  setV: { fontSize: 13, lineHeight: 19, color: MC.ink3 },
});
