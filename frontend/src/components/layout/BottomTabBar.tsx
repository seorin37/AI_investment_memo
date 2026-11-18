/**
 * 모바일 하단 탭바 (5개 탭). 현재 탭은 props로 받고, 누르면 onPress로 알려 줌.
 * 높이 80 + 기기 아래 안전 영역. 숫자 배지는 최소 11px.
 * 움직임: 고른 탭 뒤 연보라 알약이 다음 탭으로 미끄러짐(#039 · .5s spring) · 누른 아이콘이 톡 · 숫자 배지가 바뀌면 톡
 *        · hidden 이면 아래로 내려가 숨음(메모 고르기 중 · .38s)
 */
import { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, Text, type LayoutChangeEvent } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MobileIcon, type MobileIconName } from '@/components/icons/MobileIcons';
import { PopWhen } from '@/components/motion/Appear';
import { EASE, ND, SPRING, tween, useValue } from '@/components/motion/motion';

const C = {
  bg: '#FFFFFF',
  line: '#EEF0F3',
  text: '#575B63',
  active: '#6A42AB',
  activeBg: '#EEE9FB',
  badge: '#E5484D',
  badgeText: '#FFFFFF',
} as const;
const H = 80;
const PILL_W = 50;

export type MobileTab = 'home' | 'updates' | 'stocks' | 'journal' | 'studio';

export interface BottomTabBarProps {
  current: MobileTab;
  onPress: (tab: MobileTab) => void;
  /** 탭 오른쪽 위 숫자 배지. 0이거나 없으면 숨김 (예: { updates: 5 }) */
  badges?: Partial<Record<MobileTab, number>>;
  /** true 면 아래로 내려가 숨음 (메모 고르기 막대가 그 자리를 씀) */
  hidden?: boolean;
}

const TABS: { key: MobileTab; label: string; icon: MobileIconName }[] = [
  { key: 'home', label: '홈', icon: 'home' },
  { key: 'updates', label: '업데이트', icon: 'updates' },
  { key: 'stocks', label: '내 종목', icon: 'stocks' },
  { key: 'journal', label: '투자 기록', icon: 'journal' },
  { key: 'studio', label: '스튜디오', icon: 'studio' },
];

export function BottomTabBar({ current, onPress, badges, hidden }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const [w, setW] = useState(0);
  const idx = TABS.findIndex((t) => t.key === current);
  const pill = useValue(idx);
  const hide = useValue(hidden ? 1 : 0);
  useEffect(() => { tween(pill, idx, 500, SPRING, ND).start(); }, [idx, pill]);
  useEffect(() => { tween(hide, hidden ? 1 : 0, 380, hidden ? EASE : SPRING, ND).start(); }, [hidden, hide]);
  const tabW = w / TABS.length;
  return (
    <Animated.View onLayout={(e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width)} accessibilityRole="tablist" pointerEvents={hidden ? 'none' : 'auto'}
      style={[st.bar, { height: H + insets.bottom, paddingBottom: insets.bottom, transform: [{ translateY: hide.interpolate({ inputRange: [0, 1], outputRange: [0, H + insets.bottom] }) }] }]}>
      {w > 0 && (
        <Animated.View pointerEvents="none" style={[st.pill, { left: (tabW - PILL_W) / 2, transform: [{ translateX: pill.interpolate({ inputRange: [0, TABS.length - 1], outputRange: [0, tabW * (TABS.length - 1)] }) }] }]} />
      )}
      {TABS.map((t) => <Tab key={t.key} label={t.label} icon={t.icon} on={t.key === current} n={badges?.[t.key] ?? 0} onPress={() => onPress(t.key)} />)}
    </Animated.View>
  );
}

function Tab({ label, icon, on, n, onPress }: { label: string; icon: MobileIconName; on: boolean; n: number; onPress: () => void }) {
  const s = useValue(1);
  const tap = () => {
    Animated.sequence([tween(s, 0.86, 90, EASE, ND), tween(s, 1, 400, SPRING, ND)]).start();
    onPress();
  };
  return (
    <Pressable style={st.tab} onPress={tap} accessibilityRole="tab" accessibilityState={{ selected: on }} accessibilityLabel={n ? `${label}, 새 소식 ${n}건` : label}>
      <Animated.View style={[st.icWrap, { transform: [{ scale: s }] }]}>
        <MobileIcon name={icon} size={22} color={on ? C.active : C.text} strokeWidth={1.8} />
        <PopWhen show={n > 0} replay={n} style={st.badge}>
          <Text style={st.badgeText}>{n > 99 ? '99+' : n}</Text>
        </PopWhen>
      </Animated.View>
      <Text style={[st.label, on && st.labelOn]} numberOfLines={1}>{label}</Text>
    </Pressable>
  );
}

const st = StyleSheet.create({
  bar: { flexDirection: 'row', backgroundColor: C.bg, borderTopWidth: 1, borderTopColor: C.line, paddingTop: 8 },
  pill: { position: 'absolute', top: 8, width: PILL_W, height: 30, borderRadius: 15, backgroundColor: C.activeBg },
  tab: { flex: 1, alignItems: 'center', minHeight: 44, gap: 4 },
  icWrap: { width: PILL_W, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  badge: { position: 'absolute', top: -4, right: 6, minWidth: 18, height: 18, borderRadius: 9, paddingHorizontal: 4, backgroundColor: C.badge, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: C.bg },
  badgeText: { color: C.badgeText, fontSize: 11, fontWeight: '700' },
  label: { fontSize: 12, color: C.text },
  labelOn: { color: C.active, fontWeight: '700' },
});
