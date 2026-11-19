import React, { useEffect, useState } from 'react';
import { Animated, Modal, Pressable, StyleSheet, View } from 'react-native';
import { useMotionK } from '@/ui/motion/useMotion';
import { curve, dur } from '@/ui/theme';
import type { SheetProps } from './Sheet.types';

/**
 * 웹 가운데 창 (원본 kit.tsx Modal: 막 rgba(0,0,0,.45) .3s · 창은 translateY 40 · scale .96 → 제자리 .5s sheet 곡선 · Esc 로 닫힘)
 * 창의 흰 상자·제목은 각 화면이 children 으로 그림 (원본도 같음).
 */
export function Sheet({ open, onClose, children, width, label }: SheetProps) {
  const k = useMotionK();
  const [shown, setShown] = useState(open);
  const [v] = useState(() => new Animated.Value(0));
  if (open && !shown) setShown(true);
  useEffect(() => {
    if (!shown) return;
    const a = Animated.timing(v, { toValue: open ? 1 : 0, duration: (open ? dur.sheet : 260) * k, easing: open ? curve.sheet : curve.ease, useNativeDriver: false });
    a.start(({ finished }) => {
      if (finished && !open) setShown(false);
    });
    return () => a.stop();
  }, [open, shown, v, k]);
  if (!shown) return null;
  return (
    <Modal transparent visible animationType="none" onRequestClose={onClose}>
      <Animated.View style={[StyleSheet.absoluteFill, st.scrim, { opacity: v }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="닫기" />
      </Animated.View>
      <View style={st.center} pointerEvents="box-none">
        <Animated.View
          accessibilityViewIsModal
          accessibilityLabel={label}
          style={[{ width, maxWidth: '100%' }, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [40, 0] }) }, { scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.96, 1] }) }] }]}
        >
          {children}
        </Animated.View>
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  scrim: { backgroundColor: 'rgba(0,0,0,0.45)' },
  center: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, alignItems: 'center', justifyContent: 'center', padding: 16 },
});
