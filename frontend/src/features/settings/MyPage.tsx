/* eslint-disable react-hooks/set-state-in-effect -- RN Animated 관용 패턴. React Compiler 켜면 이 파일부터 정리 필요 */
/**
 * MY — 프로필 카드 · AI 사용량(%) · 계정(알림) · 화면(다크 모드) · 서비스(사용량) · 기타(데이터 · 휴지통 · 정보) · 지원(피드백 · 도움말).
 * 체험판 my.html — 움직임:
 *  - 다크 모드: 낮·밤 하늘 스위치(Lucian #021) · 누르면 스위치 자리에서 새 바탕색 원이 번지며 바뀜(#219 · .7s)
 *    → 원이 화면을 다 덮은 순간 onToggleDark (앱 전체 테마 바꾸기는 호스트)
 *  - AI 사용량 막대가 차오르고(.6s) % 숫자가 올라감(#098) · 카드가 차례로 떠오름
 */
import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions, type LayoutChangeEvent, type NativeScrollEvent, type NativeSyntheticEvent } from 'react-native';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { Appear } from '@/components/motion/Appear';
import { CountUp } from '@/components/motion/CountUp';
import { SPRING, tween, useValue } from '@/components/motion/motion';
import { SkySwitch } from '@/components/motion/SkySwitch';
import { ThemeReveal } from '@/components/motion/ThemeReveal';
import type { MyMenuKey, MyPageProps } from '@/features/settings/MyPage.types';

const C = {
  appBg: '#F3F4F6',
  card: '#FFFFFF',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  line: '#EEF0F3',
  accent: '#8569E3',
  accentDeep: '#6A42AB',
  accentSoft: '#EEE9FB',
  track: '#EEF0F3',
  swOff: '#E3E5EA',
  white: '#FFFFFF',
  tagBg: '#F3F4F6',
  revealDark: '#121316',
  revealLight: '#F3F4F6',
} as const;
const PAD = 16;
const GAP = 12;
const R = { card: 16 };

type Row = { key: MyMenuKey; label: string; value?: string };

export function MyPage({ name, initial, sub, usage_percent, usage_reset_label, dark_mode, onToggleDark, onOpen }: MyPageProps) {
  const groups: { title: string; rows: Row[] }[] = [
    { title: '계정', rows: [{ key: 'notifications', label: '알림' }] },
    { title: '서비스', rows: [{ key: 'usage', label: '사용량', value: `${usage_percent}%` }, { key: 'plan', label: '플랜 살펴보기' }] },
    { title: '기타', rows: [{ key: 'data', label: '데이터' }, { key: 'trash', label: '휴지통' }, { key: 'about', label: '정보' }] },
    { title: '지원', rows: [{ key: 'feedback', label: '피드백 보내기' }, { key: 'help', label: '도움말' }] },
  ];
  const { width: W } = useWindowDimensions();
  const scrollY = useRef(0);
  const rowY = useRef(0);
  const [reveal, setReveal] = useState<{ x: number; y: number; color: string; id: number } | null>(null);
  const next = useRef(dark_mode);
  /** 스위치는 누르자마자 움직이고, 화면 테마는 원이 다 덮은 뒤 바뀜 */
  const [sw, setSw] = useState(dark_mode);
  useEffect(() => { setSw(dark_mode); }, [dark_mode]);
  const fill = useValue(0);
  useEffect(() => { tween(fill, Math.min(100, usage_percent) / 100, 600, SPRING, false, 200).start(); }, [usage_percent, fill]);
  const toggle = (v: boolean) => {
    next.current = v;
    setSw(v);
    setReveal({ x: W - PAD - 16 - 32, y: rowY.current + 28 - scrollY.current, color: v ? C.revealDark : C.revealLight, id: Date.now() });
  };
  return (
    <View style={st.root}>
    <ScrollView style={st.root} contentContainerStyle={st.body} scrollEventThrottle={16}
      onScroll={(e: NativeSyntheticEvent<NativeScrollEvent>) => { scrollY.current = e.nativeEvent.contentOffset.y; }}>
      <Appear kind="up" index={0}>
      <Pressable style={[st.card, st.profile]} onPress={() => onOpen('profile')} accessibilityRole="button">
        <View style={st.avatar}><Text style={st.avatarText}>{initial}</Text></View>
        <View style={st.flex}>
          <Text style={st.name}>{name}</Text>
          <Text style={st.sub}>{sub}</Text>
        </View>
        <MobileIcon name="chevron_right" size={18} color={C.muted} />
      </Pressable>
      </Appear>

      <Appear kind="up" index={1}>
      <Pressable style={[st.card, st.usage]} onPress={() => onOpen('usage')} accessibilityRole="button">
        <View style={st.usageHead}>
          <Text style={st.usageTitle}>AI 사용량</Text>
          <View style={st.tag}><Text style={st.tagText}>예시</Text></View>
          <View style={st.flex} />
          <Text style={st.more}>자세히 ›</Text>
        </View>
        <View style={st.track}><Animated.View style={[st.fill, { width: fill.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'], extrapolate: 'clamp' }) }]} /></View>
        <View style={st.usageFoot}>
          <Text style={st.usageText}>이번 기간 <Text style={st.bold}><CountUp value={usage_percent} style={st.bold} />%</Text> 사용</Text>
          <Text style={st.usageText}>{usage_reset_label}</Text>
        </View>
      </Pressable>
      </Appear>

      <Group title={groups[0].title} rows={groups[0].rows} onOpen={onOpen} />
      <Text style={st.gTitle}>화면</Text>
      <View style={[st.card, st.row]} onLayout={(e: LayoutChangeEvent) => { rowY.current = e.nativeEvent.layout.y; }}>
        <MobileIcon name={sw ? 'moon' : 'sun'} size={20} color={C.text} />
        <Text style={st.rowLabel}>다크 모드</Text>
        <SkySwitch value={sw} onChange={toggle} />
      </View>
      {groups.slice(1).map((g) => <Group key={g.title} title={g.title} rows={g.rows} onOpen={onOpen} />)}
    </ScrollView>
    <ThemeReveal fire={reveal} onCovered={() => onToggleDark(next.current)} />
    </View>
  );
}

function Group({ title, rows, onOpen }: { title: string; rows: Row[]; onOpen: (k: MyMenuKey) => void }) {
  return (
    <>
      <Text style={st.gTitle}>{title}</Text>
      <View style={st.card}>
        {rows.map((r, i) => (
          <Pressable key={r.key} style={[st.row, i > 0 && st.rowLine]} onPress={() => onOpen(r.key)} accessibilityRole="button">
            <Text style={st.rowLabel}>{r.label}</Text>
            {!!r.value && <Text style={st.rowValue}>{r.value}</Text>}
            <MobileIcon name="chevron_right" size={18} color={C.muted} />
          </Pressable>
        ))}
      </View>
    </>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.appBg },
  flex: { flex: 1, minWidth: 0 },
  body: { paddingHorizontal: PAD, paddingBottom: 40, gap: GAP },
  card: { backgroundColor: C.card, borderRadius: R.card, paddingHorizontal: 16 },
  profile: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 18 },
  avatar: { width: 52, height: 52, borderRadius: 26, backgroundColor: C.accentSoft, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 20, fontWeight: '800', color: C.accentDeep },
  name: { fontSize: 19, fontWeight: '800', color: C.text },
  sub: { fontSize: 13, color: C.sub, marginTop: 3 },
  usage: { paddingVertical: 16 },
  usageHead: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  usageTitle: { fontSize: 15, fontWeight: '800', color: C.text },
  tag: { backgroundColor: C.tagBg, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1 },
  tagText: { fontSize: 11, fontWeight: '700', color: C.sub },
  more: { fontSize: 14, fontWeight: '700', color: C.accentDeep },
  track: { height: 8, borderRadius: 4, backgroundColor: C.track, marginTop: 12, overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4, backgroundColor: C.accent },
  usageFoot: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  usageText: { fontSize: 12.5, color: C.sub },
  bold: { fontWeight: '800', color: C.text },
  gTitle: { fontSize: 13, color: C.muted, marginTop: 6, marginLeft: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 54 },
  rowLine: { borderTopWidth: 1, borderTopColor: C.line },
  rowLabel: { flex: 1, fontSize: 16, color: C.text },
  rowValue: { fontSize: 14, color: C.muted },
});
