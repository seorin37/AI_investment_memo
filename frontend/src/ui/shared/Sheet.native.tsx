import React, { useEffect, useRef, useState } from 'react';
import { Animated, KeyboardAvoidingView, Modal, PanResponder, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, dur, ft, shadow } from '@/ui/theme';
import type { SheetProps } from './Sheet.types';
import { DarkLayer, SCRIM_DARK, useDark } from '@/ui/shared/Dark';

/**
 * 앱 바텀 시트 (원본 home.html #sheet: 흰 바탕 · 위 라운드 26 · 손잡이 40×5 #D5D8DD 라운드 3 (위 10 · 아래 14) · 제목 17px 800 · 좌우 22
 * 막 rgba(12,12,22,.4)). 올라옴 .5s sheet 곡선. 끌기는 터치 시작부터(규칙 5) — 아래로 끌면 닫힘. 안드로이드 뒤로 = 닫기.
 */
/** 웹 창을 앱에서 그대로 쓸 때 (width 를 주는 웹 컴포넌트): 바텀 시트가 아니라 웹처럼 가운데 창 */
export function Sheet(p: SheetProps) {
  if (p.full) return <FullSheet {...p} />;
  return p.width && !p.title ? <CenterSheet {...p} /> : <BottomSheet {...p} />;
}

function CenterSheet({ open, onClose, children, width, label, scrim }: SheetProps) {
  const k = useMotionK();
  const dark = useDark();
  const [shown, setShown] = useState(open);
  const [v] = useState(() => new Animated.Value(0));
  if (open && !shown) setShown(true);
  useEffect(() => {
    if (!shown) return;
    const a = Animated.timing(v, { toValue: open ? 1 : 0, duration: (open ? dur.sheet : 260) * k, easing: open ? curve.sheet : curve.ease, useNativeDriver: NATIVE });
    a.start(({ finished }) => {
      if (finished && !open) setShown(false);
    });
    return () => a.stop();
  }, [open, shown, v, k]);
  if (!shown) return null;
  return (
    <Modal transparent visible animationType="none" onRequestClose={onClose} statusBarTranslucent navigationBarTranslucent>
      <DarkLayer>
      <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor: scrim ?? 'rgba(0,0,0,0.45)' }, dark && { backgroundColor: SCRIM_DARK }, { opacity: v }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="닫기" />
      </Animated.View>
      <View style={st.center} pointerEvents="box-none">
        <Animated.View accessibilityViewIsModal accessibilityLabel={label} style={[{ width, maxWidth: '100%', maxHeight: '100%' }, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [40, 0] }) }, { scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.96, 1] }) }] }]}>
          {/* 종목이 많아 화면보다 길면 창 안에서 스크롤 */}
          <ScrollView style={st.centerScroll} showsVerticalScrollIndicator={false}>{children}</ScrollView>
        </Animated.View>
      </View>
      </DarkLayer>
    </Modal>
  );
}

/** 전체 높이 시트: 상태 바 아래부터 화면 끝까지 (키보드가 올라오면 그 위까지) */
function FullSheet({ open, onClose, children, label, scrim }: SheetProps) {
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
      <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor: scrim ?? 'rgba(0,0,0,0.45)' }, dark && { backgroundColor: SCRIM_DARK }, { opacity: y.interpolate({ inputRange: [0, height], outputRange: [1, 0] }) }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="닫기" />
      </Animated.View>
      <Animated.View accessibilityViewIsModal accessibilityLabel={label} style={[st.full, { top: insets.top, paddingBottom: insets.bottom, transform: [{ translateY: y }] }]}>
        <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding" keyboardVerticalOffset={insets.top}>{children}</KeyboardAvoidingView>
      </Animated.View>
      </DarkLayer>
    </Modal>
  );
}

function BottomSheet({ open, onClose, title, children, label }: SheetProps) {
  const k = useMotionK();
  const dark = useDark();
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
      <DarkLayer>
      <Animated.View style={[StyleSheet.absoluteFill, st.scrim, dark && { backgroundColor: SCRIM_DARK }, { opacity: y.interpolate({ inputRange: [0, height], outputRange: [1, 0] }) }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="닫기" />
      </Animated.View>
      <Animated.View style={[st.sheet, { paddingBottom: 14 + insets.bottom, transform: [{ translateY: Animated.add(y, drag) }] }]} accessibilityViewIsModal accessibilityLabel={label}>
        <View {...pan.panHandlers} style={st.grab}>
          <View style={st.handle} />
          {title ? <Text style={st.title}>{title}</Text> : null}
        </View>
        {children}
      </Animated.View>
      </DarkLayer>
    </Modal>
  );
}

const st = StyleSheet.create({
  center: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, alignItems: 'center', justifyContent: 'center', padding: 16 },
  full: { position: 'absolute', left: 0, right: 0, bottom: 0, overflow: 'hidden', backgroundColor: appColor.surface, borderTopLeftRadius: 26, borderTopRightRadius: 26 },
  centerScroll: { flexGrow: 0, borderRadius: 28 },
  scrim: { backgroundColor: 'rgba(12,12,22,0.4)' },
  sheet: { position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: appColor.surface, borderTopLeftRadius: 26, borderTopRightRadius: 26, ...shadow.sheet },
  grab: { paddingTop: 10, paddingHorizontal: 22, paddingBottom: 4 },
  handle: { alignSelf: 'center', width: 40, height: 5, borderRadius: 3, backgroundColor: '#D5D8DD', marginBottom: 14 },
  title: { ...ft(17), fontWeight: '800', color: appColor.ink },
});
