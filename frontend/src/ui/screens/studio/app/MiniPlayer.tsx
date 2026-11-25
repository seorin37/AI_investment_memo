import React, { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { AUDIO_OFF_BG, audioOff } from '../appAudio';
import { curve } from '@/ui/theme';

/**
 * 앱 미니 플레이어 = 원본 studio.html .mini (탭 바 위 10 · 좌우 10 · 높이 62 · 라운드 16 · 그림자)
 * 검정 아이콘 42 · 제목 14 · '챕터 · 지금 / 길이' 11.5 · 재생 40 · 닫기 34 · 아래 진행 줄 3. 올라올 때 스프링(.5s)
 * 탭 레이아웃(app/(main)/_layout.native.tsx)에 놓여 탭을 바꿔도 남음. 위로 쌓이는 화면·시트가 덮으면 자연히 가려짐
 */
export function AppMiniPlayer({ visible, bottom, title, sub, progress, playing, onOpen, onToggle, onClose }: {
  visible: boolean; bottom: number; title: string; sub: string; progress: number; playing: boolean;
  onOpen: () => void; onToggle: () => void; onClose: () => void;
}) {
  const k = useMotionK();
  const [y] = useState(() => new Animated.Value(visible ? 0 : 1));
  const [shown, setShown] = useState(visible);
  if (visible && !shown) setShown(true);
  useEffect(() => {
    const a = Animated.timing(y, { toValue: visible ? 0 : 1, duration: 500 * k, easing: curve.spring, useNativeDriver: NATIVE });
    a.start(({ finished }) => { if (finished && !visible) setShown(false); });
    return () => a.stop();
  }, [visible, y, k]);
  if (!shown) return null;
  return (
    <Animated.View style={[st.mini, { bottom, transform: [{ translateY: y.interpolate({ inputRange: [0, 1], outputRange: [0, 160 + bottom] }) }] }]}>
      <View style={st.mic}>
        <Svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2} strokeLinecap="round"><Path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2" /></Svg>
      </View>
      <Pressable onPress={onOpen} accessibilityRole="button" accessibilityLabel={`${title} 플레이어 열기`} style={{ flex: 1, minWidth: 0 }}>
        <Text style={st.b} numberOfLines={1}>{title}</Text>
        <Text style={st.s} numberOfLines={1}>{sub}</Text>
      </Pressable>
      <Pressable onPress={onToggle} accessibilityRole="button" accessibilityLabel={playing ? '일시정지' : '재생'} accessibilityState={{ disabled: audioOff }} style={[st.pp, audioOff && { backgroundColor: AUDIO_OFF_BG }]}>
        <Svg width={18} height={18} viewBox="0 0 26 26"><Path d={playing ? 'M6 4 L6 22 L11 22 L11 4 Z M15 4 L15 22 L20 22 L20 4 Z' : 'M7 4 L7 22 L13 18.5 L13 7.5 Z M13 7.5 L13 18.5 L22 13 L22 13 Z'} fill="#fff" /></Svg>
      </Pressable>
      <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="닫기" style={st.xb}>
        <Svg width={18} height={18} viewBox="0 0 24 24" stroke="#575B63" strokeWidth={2.2} strokeLinecap="round"><Path d="M6 6l12 12M18 6 6 18" /></Svg>
      </Pressable>
      <View pointerEvents="none" style={[st.ln, { width: `${Math.min(100, progress * 100)}%` }]} />
    </Animated.View>
  );
}

const st = StyleSheet.create({
  mini: { position: 'absolute', left: 10, right: 10, height: 62, backgroundColor: '#FFFFFF', borderRadius: 16, flexDirection: 'row', alignItems: 'center', gap: 11, paddingLeft: 10, paddingRight: 8, overflow: 'hidden', shadowColor: '#000', shadowOpacity: 0.25, shadowRadius: 22, shadowOffset: { width: 0, height: 6 }, elevation: 8, zIndex: 44 },
  mic: { width: 42, height: 42, borderRadius: 11, backgroundColor: '#16171A', alignItems: 'center', justifyContent: 'center' },
  b: { fontSize: 14, lineHeight: 19, fontWeight: '700', color: '#16171A' },
  s: { fontSize: 11.5, lineHeight: 16, color: '#9A9EA7' },
  pp: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#16171A', alignItems: 'center', justifyContent: 'center' },
  xb: { width: 34, height: 34, alignItems: 'center', justifyContent: 'center' },
  ln: { position: 'absolute', left: 0, bottom: 0, height: 3, backgroundColor: '#16171A' },
});
