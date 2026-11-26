import React, { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { AppIcon, type AppIconName } from '@/ui/icons/Icon';
import { useMotionK } from '@/ui/motion/useMotion';
import { TabBadge } from '@/ui/shared/app/TabBadge';
import { appColor, curve, ft, size } from '@/ui/theme';
import type { AppTab, BottomTabBarProps } from './BottomTabBar.types';

const TABS: { key: AppTab; label: string; icon: AppIconName }[] = [
  { key: 'home', label: '홈', icon: 'tabHome' },
  { key: 'updates', label: '업데이트', icon: 'tabUpdates' },
  { key: 'stocks', label: '내 종목', icon: 'stocks' },
  { key: 'journal', label: '투자 기록', icon: 'journal' },
  { key: 'studio', label: '스튜디오', icon: 'tabStudio' },
];

/** 원본 .tabbar 숨김: transform .35s ease 로 아래로 */
const HIDE_MS = 350;

/**
 * 앱 아래 탭 (원본 home.html .tabbar)
 * 높이 80 = 위 선 1 + 탭 65 + 아래 여백 14. 기기 아래 안전 영역이 14보다 크면 그만큼.
 * 숨기면 아래로 내려가면서 자리도 접혀 빈 공간이 남지 않음 (규칙 5).
 */
export function BottomTabBar({ current, onPress, badges, dots, hidden = false }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const k = useMotionK();
  const padB = Math.max(size.tabBarPadBottom, insets.bottom);
  const full = 1 + 65 + padB;
  const [v] = useState(() => new Animated.Value(hidden ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: hidden ? 1 : 0, duration: HIDE_MS * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [hidden, v, k]);
  return (
    <Animated.View style={{ height: v.interpolate({ inputRange: [0, 1], outputRange: [full, 0] }), overflow: 'hidden', backgroundColor: appColor.surface }}>
      <Animated.View style={[st.bar, { height: full, paddingBottom: padB, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [0, full] }) }] }]} accessibilityRole="tablist">
        {TABS.map((t) => {
          const on = t.key === current;
          const ink = on ? appColor.deepPurple : appColor.tabInk;
          return (
            <Pressable key={t.key} style={st.tab} onPress={() => onPress(t.key)} accessibilityRole="tab" accessibilityState={{ selected: on }} accessibilityLabel={dots?.[t.key] ? `${t.label} · 새로 완성된 항목` : t.label}>
              <View collapsable={false} style={[st.ic, on && st.icOn]}>
                <AppIcon name={t.icon} color={ink} />
                <TabBadge count={badges?.[t.key] ?? 0} style={st.badge} />
                {dots?.[t.key] ? <View style={st.dot} /> : null}
              </View>
              <Text style={[st.label, { color: ink, fontWeight: on ? '700' : '400' }]} numberOfLines={1}>
                {t.label}
              </Text>
            </Pressable>
          );
        })}
      </Animated.View>
    </Animated.View>
  );
}

const st = StyleSheet.create({
  bar: { flexDirection: 'row', backgroundColor: appColor.surface, borderTopWidth: 1, borderTopColor: appColor.line },
  tab: { flex: 1, height: 65, alignItems: 'center', justifyContent: 'center', gap: 3 },
  /* 아이콘 칸은 collapsable={false} — 꺼진 탭(배경 없음)이 합쳐졌다가 켜지며 다시 생길 때 안드로이드(New Arch)에서 둥근 모서리가 빠져 네모로 그려짐 */
  ic: { width: 50, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  icOn: { backgroundColor: appColor.accentSoft },
  badge: { position: 'absolute', top: -4, right: 4 },
  dot: { position: 'absolute', top: 2, right: 9, width: 8, height: 8, borderRadius: 4, backgroundColor: '#E5484D' },
  label: { ...ft(11.5), textAlign: 'center', flexShrink: 1 },
});
