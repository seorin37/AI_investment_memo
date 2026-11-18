/* eslint-disable react-hooks/refs, react-hooks/set-state-in-effect -- RN Animated 관용 패턴. React Compiler 켜면 이 파일부터 정리 필요 */
/**
 * 아래에서 올라오는 시트 (Lucian #336 bottom-sheet) — 체험판 .gsh 값.
 *  - 열기: 아래에서 .45s cubic-bezier(.3,1.25,.5,1) (살짝 넘쳤다 멈춤) · 뒤 막 .3s
 *  - 닫기: .3s 로 내려감 · 막 .25s
 *  - 손잡이(또는 시트 전체)를 아래로 끌면 따라 내려오고, 1/4 넘게 또는 빠르게 내리면 닫힘. 위로 끌면 1/4 만큼만 버팀.
 * React Native 기본 Modal + PanResponder 만 사용.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Animated, Modal, PanResponder, Pressable, StyleSheet, View, type StyleProp, type ViewStyle, type LayoutChangeEvent } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { EASE, ND, SHEET, tween, useValue } from '@/components/motion/motion';

const M = { scrim: 'rgba(17,19,24,0.45)', bg: '#FFFFFF', grip: '#D5D8DD' } as const;
const R = 24;

export interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  /** 'sheet': 시트 어디를 끌어도 닫힘(짧은 시트) · 'handle': 손잡이 줄만(안에 스크롤 · 입력칸이 있을 때) */
  drag?: 'sheet' | 'handle';
  style?: StyleProp<ViewStyle>;
  accessibilityLabel?: string;
}

export function BottomSheet({ open, onClose, children, drag = 'sheet', style, accessibilityLabel }: BottomSheetProps) {
  const inset = useSafeAreaInsets();
  const [mounted, setMounted] = useState(open);
  const [h, setH] = useState(0);
  const y = useValue(2000);
  const scrim = useValue(0);
  const hRef = useRef(0);
  hRef.current = h;
  const entered = useRef(false);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (open) { setMounted(true); return; }
    entered.current = false;
    if (!mounted) return;
    const a = Animated.parallel([tween(y, hRef.current || 600, 300, EASE, ND), tween(scrim, 0, 250, EASE, ND)]);
    a.start(({ finished }) => { if (finished) { setMounted(false); setH(0); } });
    return () => a.stop();
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open || !mounted || h === 0 || entered.current) return;
    entered.current = true;
    y.setValue(h);
    const a = Animated.parallel([tween(y, 0, 450, SHEET, ND), tween(scrim, 1, 300, EASE, ND)]);
    a.start();
  }, [open, mounted, h, y, scrim]);

  const pan = useRef(PanResponder.create({
    onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 4 && Math.abs(g.dy) > Math.abs(g.dx),
    onPanResponderMove: (_, g) => { y.setValue(g.dy > 0 ? g.dy : g.dy / 4); },
    onPanResponderRelease: (_, g) => {
      if (g.dy > hRef.current * 0.25 || g.vy > 0.9) closeRef.current();
      else tween(y, 0, 350, SHEET, ND).start();
    },
    onPanResponderTerminate: () => { tween(y, 0, 350, SHEET, ND).start(); },
  })).current;

  if (!mounted) return null;
  return (
    <Modal visible transparent animationType="none" onRequestClose={onClose} statusBarTranslucent>
      <Animated.View style={[StyleSheet.absoluteFill, st.scrim, { opacity: scrim }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="닫기" />
      </Animated.View>
      <Animated.View accessibilityViewIsModal accessibilityLabel={accessibilityLabel}
        onLayout={(e: LayoutChangeEvent) => { const nh = Math.round(e.nativeEvent.layout.height); if (nh !== h) setH(nh); }}
        style={[st.sheet, { paddingBottom: Math.max(inset.bottom, 16), transform: [{ translateY: y }] }, style]}
        {...(drag === 'sheet' ? pan.panHandlers : {})}>
        <View style={st.gripZone} {...(drag === 'handle' ? pan.panHandlers : {})}><View style={st.grip} /></View>
        {children}
      </Animated.View>
    </Modal>
  );
}

const st = StyleSheet.create({
  scrim: { backgroundColor: M.scrim },
  sheet: { position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: M.bg, borderTopLeftRadius: R, borderTopRightRadius: R, paddingHorizontal: 18 },
  gripZone: { height: 24, alignItems: 'center', justifyContent: 'center' },
  grip: { width: 40, height: 5, borderRadius: 3, backgroundColor: M.grip },
});
