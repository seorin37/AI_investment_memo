import React, { useEffect, useState } from 'react';
import { Animated, KeyboardAvoidingView, Modal, Pressable, StyleSheet, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { DarkLayer, SCRIM_DARK, useDark } from '@/ui/shared/Dark';
import { appColor, curve, dur } from '@/ui/theme';
import type { SheetProps } from '../Sheet.types';

/** 전체 높이 시트: 상태 바 아래부터 화면 끝까지 (키보드가 올라오면 그 위까지) */
export function FullSheet({ open, onClose, children, label }: Pick<SheetProps, 'open' | 'onClose' | 'children' | 'label'>) {
  const k = useMotionK();
  const dark = useDark();
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();
  const [shown, setShown] = useState(open);
  const [y] = useState(() => new Animated.Value(height));
  if (open && !shown) setShown(true);
  useEffect(() => {
    if (!shown) return;
    const a = Animated.timing(y, { toValue: open ? 0 : height, duration: (open ? dur.sheet : dur.base) * k, easing: open ? curve.sheet : curve.ease, useNativeDriver: NATIVE });
    a.start(({ finished }) => {
      if (finished && !open) setShown(false);
    });
    return () => a.stop();
  }, [open, shown, y, height, k]);
  if (!shown) return null;
  return (
    <Modal transparent visible animationType="none" onRequestClose={onClose} statusBarTranslucent navigationBarTranslucent>
      <DarkLayer>
      <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.45)' }, dark && { backgroundColor: SCRIM_DARK }, { opacity: y.interpolate({ inputRange: [0, height], outputRange: [1, 0] }) }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="닫기" />
      </Animated.View>
      <Animated.View accessibilityViewIsModal accessibilityLabel={label} style={[st.full, { top: insets.top, paddingBottom: insets.bottom, transform: [{ translateY: y }] }]}>
        <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding" keyboardVerticalOffset={insets.top}>{children}</KeyboardAvoidingView>
      </Animated.View>
      </DarkLayer>
    </Modal>
  );
}

const st = StyleSheet.create({
  full: { position: 'absolute', left: 0, right: 0, bottom: 0, overflow: 'hidden', backgroundColor: appColor.bg, borderTopLeftRadius: 26, borderTopRightRadius: 26 },
});
