import React, { useEffect, useRef, useState } from 'react';
import { Animated, Modal, PanResponder, Pressable, StyleSheet, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, dur, ft, shadow } from '@/ui/theme';
import type { SheetProps } from './Sheet.types';

/**
 * 앱 바텀 시트 (원본 home.html #sheet: 흰 바탕 · 위 라운드 26 · 손잡이 40×5 #D5D8DD 라운드 3 (위 10 · 아래 14) · 제목 17px 800 · 좌우 22
 * 막 rgba(12,12,22,.4)). 올라옴 .5s sheet 곡선. 끌기는 터치 시작부터(규칙 5) — 아래로 끌면 닫힘. 안드로이드 뒤로 = 닫기.
 */
export function Sheet({ open, onClose, title, children, label }: SheetProps) {
  const k = useMotionK();
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();
  const [shown, setShown] = useState(open);
  const [y] = useState(() => new Animated.Value(height));
  const [drag] = useState(() => new Animated.Value(0));
  if (open && !shown) setShown(true);
  useEffect(() => {
    if (!shown) return;
    const a = Animated.timing(y, { toValue: open ? 0 : height, duration: (open ? dur.sheet : dur.base) * k, easing: open ? curve.sheet : curve.ease, useNativeDriver: NATIVE });
    a.start(({ finished }) => {
      if (finished && !open) {
        drag.setValue(0);
        setShown(false);
      }
    });
    return () => a.stop();
  }, [open, shown, y, drag, height, k]);
  /* 끌어서 닫기: 처리기는 처음 한 번만 만들고, 닫기 요청은 숫자로 알려 effect 에서 onClose */
  const [dismiss, setDismiss] = useState(0);
  const handled = useRef(0);
  useEffect(() => {
    if (dismiss > handled.current) {
      handled.current = dismiss;
      onClose();
    }
  }, [dismiss, onClose]);
  const [pan] = useState(() =>
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 4 && Math.abs(g.dy) > Math.abs(g.dx),
      onPanResponderMove: (_, g) => drag.setValue(Math.max(0, g.dy)),
      onPanResponderRelease: (_, g) => {
        if (g.dy > 90 || g.vy > 0.9) setDismiss((n) => n + 1);
        else Animated.timing(drag, { toValue: 0, duration: dur.base, easing: curve.spring, useNativeDriver: NATIVE }).start();
      },
    }),
  );
  if (!shown) return null;
  return (
    <Modal transparent visible animationType="none" onRequestClose={onClose} statusBarTranslucent navigationBarTranslucent>
      <Animated.View style={[StyleSheet.absoluteFill, st.scrim, { opacity: y.interpolate({ inputRange: [0, height], outputRange: [1, 0] }) }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="닫기" />
      </Animated.View>
      <Animated.View style={[st.sheet, { paddingBottom: 14 + insets.bottom, transform: [{ translateY: Animated.add(y, drag) }] }]} accessibilityViewIsModal accessibilityLabel={label}>
        <View {...pan.panHandlers} style={st.grab}>
          <View style={st.handle} />
          {title ? <Text style={st.title}>{title}</Text> : null}
        </View>
        {children}
      </Animated.View>
    </Modal>
  );
}

const st = StyleSheet.create({
  scrim: { backgroundColor: 'rgba(12,12,22,0.4)' },
  sheet: { position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: appColor.surface, borderTopLeftRadius: 26, borderTopRightRadius: 26, ...shadow.sheet },
  grab: { paddingTop: 10, paddingHorizontal: 22, paddingBottom: 4 },
  handle: { alignSelf: 'center', width: 40, height: 5, borderRadius: 3, backgroundColor: '#D5D8DD', marginBottom: 14 },
  title: { ...ft(17), fontWeight: '800', color: appColor.ink },
});
