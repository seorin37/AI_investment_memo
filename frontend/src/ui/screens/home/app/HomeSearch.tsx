import React, { useEffect, useRef, useState } from 'react';
import { Animated, BackHandler, Pressable, ScrollView, StyleSheet, View, useWindowDimensions, type TextInputInstance } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text, TextInput } from '@/components/ui/AppText';
import { SearchGlyph } from '@/ui/icons/HomeGlyphs';
import { useMotionK } from '@/ui/motion/useMotion';
import { StockLogo } from '@/ui/shared/StockLogo';
import { appColor, curve, ft } from '@/ui/theme';
import type { SearchStock } from '../Home.types';

/**
 * 앱 홈 검색 (원본 home.html #027 #092 .so): 돋보기 자리에서 검색칸이 늘어남 (오른쪽 90 → 64 · 폭 42 → 300 · .42s 반동)
 * 바탕 #F3F4F6 페이드 .25s · 결과는 .08s 뒤 8px 올라오며 · 없는 종목은 다시 찾는 법.
 */
export function HomeSearch({ open, onClose, recent, popular, all, onPick }: { open: boolean; onClose: () => void; recent: SearchStock[]; popular: SearchStock[]; all: SearchStock[]; onPick: (code: string) => void }) {
  const k = useMotionK();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const [q, setQ] = useState('');
  const [shown, setShown] = useState(open);
  const [v] = useState(() => new Animated.Value(0));
  const input = useRef<TextInputInstance>(null);
  if (open && !shown) setShown(true);
  useEffect(() => {
    if (!shown) return;
    const a = Animated.timing(v, { toValue: open ? 1 : 0, duration: 420 * k, easing: open ? curve.spring : curve.ease, useNativeDriver: false });
    a.start(({ finished }) => {
      if (finished && !open) setShown(false);
    });
    const t = open ? setTimeout(() => input.current?.focus(), 250 * k) : undefined;
    return () => {
      a.stop();
      if (t) clearTimeout(t);
    };
  }, [open, shown, v, k]);
  useEffect(() => {
    if (!open) return;
    const s = BackHandler.addEventListener('hardwareBackPress', () => {
      onClose();
      return true;
    });
    return () => s.remove();
  }, [open, onClose]);
  if (!shown) return null;
  const close = () => {
    setQ('');
    input.current?.blur();
    onClose();
  };
  const full = Math.max(160, width - 64 - 48);
  const t = q.trim();
  const hits = t ? all.filter((s) => s.name.toLowerCase().includes(t.toLowerCase()) || s.stock_code.includes(t)) : [];
  const pick = (code: string) => {
    close();
    onPick(code);
  };
  const row = (s: SearchStock) => {
    const i = t ? s.name.indexOf(t) : -1;
    return (
      <Pressable key={s.stock_code} onPress={() => pick(s.stock_code)} accessibilityRole="button" style={({ pressed }) => [st.sr, pressed && { backgroundColor: appColor.searchBg }]}>
        <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={40} variant="app" />
        <Text style={st.srB} numberOfLines={1}>
          {i >= 0 ? (
            <>
              {s.name.slice(0, i)}
              <Text style={{ color: appColor.deepPurple }}>{s.name.slice(i, i + t.length)}</Text>
              {s.name.slice(i + t.length)}
            </>
          ) : (
            s.name
          )}
          <Text style={st.srS}>{'  ' + s.stock_code}</Text>
        </Text>
      </Pressable>
    );
  };
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents={open ? 'auto' : 'none'}>
      <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor: appColor.bg, opacity: v.interpolate({ inputRange: [0, 0.6, 1], outputRange: [0, 1, 1], extrapolate: 'clamp' }) }]} />
      <Animated.View style={[st.sf, { top: insets.top + 9, right: v.interpolate({ inputRange: [0, 1], outputRange: [90, 64] }), width: v.interpolate({ inputRange: [0, 1], outputRange: [42, full] }), opacity: v.interpolate({ inputRange: [0, 0.35, 1], outputRange: [0, 1, 1], extrapolate: 'clamp' }), borderWidth: 2, borderColor: appColor.accent }]}>
        <SearchGlyph />
        <TextInput ref={input} value={q} onChangeText={setQ} placeholder="종목명·종목코드" placeholderTextColor={appColor.ink3} style={st.in} returnKeyType="search" autoCorrect={false} />
      </Animated.View>
      <Animated.View style={[st.scl, { top: insets.top + 9, opacity: v }]}>
        <Pressable onPress={close} accessibilityRole="button" style={st.sclBtn}>
          <Text style={st.sclT}>취소</Text>
        </Pressable>
      </Animated.View>
      <Animated.View style={[st.sres, { top: insets.top + 64, opacity: v.interpolate({ inputRange: [0, 0.4, 1], outputRange: [0, 0, 1], extrapolate: 'clamp' }), transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [8, 0], extrapolate: 'clamp' }) }] }]}>
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={st.sresIn}>
          {!t ? (
            <>
              <Text style={st.sl}>최근 찾은 종목</Text>
              <View style={st.chips}>
                {recent.map((s) => (
                  <Pressable key={s.stock_code} onPress={() => pick(s.stock_code)} accessibilityRole="button" style={st.chip}>
                    <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={20} variant="app" radius={6} fontSize={10} />
                    <Text style={st.chipT}>{s.name}</Text>
                  </Pressable>
                ))}
              </View>
              <Text style={[st.sl, { marginTop: 20 }]}>많이 찾는 종목</Text>
              {popular.map((s) => (
                row(s)
              ))}
            </>
          ) : hits.length ? (
            hits.map((s) => row(s))
          ) : (
            <View style={st.empty}>
              <Text style={st.emptyB}>‘{t}’ 종목을 찾지 못했어요</Text>
              <Text style={st.emptyT}>{'코스피 종목만 찾을 수 있어요.\n종목명이나 6자리 종목코드로 다시 찾아 보세요.'}</Text>
            </View>
          )}
        </ScrollView>
      </Animated.View>
    </View>
  );
}


const st = StyleSheet.create({
  sf: { position: 'absolute', height: 42, borderRadius: 21, backgroundColor: '#FFFFFF', flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, overflow: 'hidden' },
  in: { flex: 1, minWidth: 0, ...ft(15), color: appColor.ink, paddingVertical: 0 },
  scl: { position: 'absolute', right: 16, height: 42, justifyContent: 'center' },
  sclBtn: { minHeight: 42, justifyContent: 'center' },
  sclT: { ...ft(15), color: appColor.ink2 },
  sres: { position: 'absolute', left: 0, right: 0, bottom: 0 },
  sresIn: { paddingTop: 4, paddingHorizontal: 16, paddingBottom: 20 },
  sl: { ...ft(13), fontWeight: '700', color: appColor.ink3, marginTop: 10, marginHorizontal: 4, marginBottom: 8 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { minHeight: 32, paddingHorizontal: 12, borderRadius: 16, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: appColor.line, flexDirection: 'row', alignItems: 'center', gap: 6 },
  chipT: { ...ft(13.5), color: appColor.ink },
  sr: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, paddingHorizontal: 4, borderRadius: 12 },
  srB: { flexShrink: 1, ...ft(15), fontWeight: '700', color: appColor.ink },
  srS: { ...ft(12.5), fontWeight: '400', color: appColor.ink3 },
  empty: { alignItems: 'center', paddingVertical: 50, paddingHorizontal: 10 },
  emptyB: { ...ft(16), fontWeight: '700', color: appColor.ink, marginBottom: 4, textAlign: 'center' },
  emptyT: { ...ft(14, 1.7), color: appColor.ink2, textAlign: 'center' },
});
