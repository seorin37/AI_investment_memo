import React, { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View, useWindowDimensions, type ViewStyle } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { MenuIcon } from '@/ui/icons/BoardGlyphs';
import { curve, fpx, webColor } from '@/ui/theme';
import { useMotionK } from '@/ui/motion/useMotion';

export type MenuItem = { label: string; icon?: 'pin' | 'trash' | 'copy' | 'find' | 'select' | 'move' | 'info'; danger?: boolean; run: () => void } | '-';

/* 웹 전용 스타일: 화면 기준 위치 */
const FIXED = { position: 'fixed' } as unknown as ViewStyle;

type HoverState = { pressed: boolean; hovered?: boolean };

/**
 * 웹 메뉴 (원본 x.tsx CtxMenu · Lucian #038: 220 · 라운드 14 · 테두리 #E5E8EB · 흰 · 안쪽 6 · 그림자 0 16px 36px -12px .25
 * 항목 40 · 라운드 10 · 좌우 12 · 사이 10 · 15/23 500 (위험 #E5484D) · hover #F5F6F8 · 나눔 선 #EFEFF2
 * 화면 오른쪽·아래로 넘치면 반대쪽으로. 열릴 때 .85 → 1 (.4s spring) · 투명도 .15s)
 * 닫기: 바깥 누르기 · Esc (Esc 는 웹 화면의 키보드 처리에서)
 */
export function ContextMenu({ at, items, onClose }: { at: { x: number; y: number } | null; items: MenuItem[]; onClose: () => void }) {
  const { width: W, height: H } = useWindowDimensions();
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!at) return;
    v.setValue(0);
    const a = Animated.timing(v, { toValue: 1, duration: 400 * k, easing: curve.spring, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [at, v, k]);
  if (!at) return null;
  const h = items.reduce((s, it) => s + (it === '-' ? 9 : 40), 12) + 2;
  const flipX = at.x + 220 > W - 12;
  const flipY = at.y + h > H - 12;
  const left = flipX ? at.x - 220 : at.x;
  const top = flipY ? Math.max(12, at.y - h) : at.y;
  return (
    <>
      <Pressable style={[StyleSheet.absoluteFill, FIXED, { zIndex: 94 }]} onPress={onClose} accessibilityLabel="메뉴 닫기" />
      <Animated.View
        accessibilityRole="menu"
        style={[
          st.menu,
          FIXED,
          { left, top, transformOrigin: `${flipX ? 'right' : 'left'} ${flipY ? 'bottom' : 'top'}`, opacity: v.interpolate({ inputRange: [0, 0.3, 1], outputRange: [0, 1, 1] }), transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.85, 1] }) }] },
        ]}
      >
        {items.map((it, i) =>
          it === '-' ? (
            <View key={`d${i}`} style={st.div} />
          ) : (
            <Pressable
              key={it.label}
              accessibilityRole="menuitem"
              onPress={() => {
                onClose();
                it.run();
              }}
              style={({ hovered }: HoverState) => [st.item, hovered && { backgroundColor: webColor.row }]}
            >
              {it.icon ? (
                <View style={st.ic}>
                  <MenuIcon k={it.icon} color={it.danger ? '#E5484D' : webColor.ink} />
                </View>
              ) : null}
              <Text style={[st.t, { color: it.danger ? '#E5484D' : webColor.ink }]}>{it.label}</Text>
            </Pressable>
          ),
        )}
      </Animated.View>
    </>
  );
}

const st = StyleSheet.create({
  menu: { zIndex: 95, width: 220, borderRadius: 14, borderWidth: 1, borderColor: webColor.line2, backgroundColor: '#FFFFFF', padding: 6, shadowColor: '#111111', shadowOpacity: 0.25, shadowRadius: 24, shadowOffset: { width: 0, height: 16 }, elevation: 12 },
  item: { height: 40, flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 10, paddingHorizontal: 12 },
  ic: { width: 20, alignItems: 'center' },
  t: { ...fpx(15, 23), fontWeight: '500' },
  div: { marginHorizontal: 8, marginVertical: 4, height: 1, backgroundColor: '#EFEFF2' },
});
