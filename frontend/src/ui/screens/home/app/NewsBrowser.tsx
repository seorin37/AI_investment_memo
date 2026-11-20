import React, { useEffect, useState } from 'react';
import { Animated, Easing, Modal, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { BrowserClose, BrowserExternal } from '@/ui/icons/HomeGlyphs';
import { Skeleton } from '@/ui/motion/Skeleton';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, ft } from '@/ui/theme';
import type { HomeNewsItem } from '../Home.types';
import { hm } from '../homeFormat';
import { DarkLayer } from '@/ui/shared/Dark';

/**
 * 앱 안 브라우저 (원본 home.html .brow: 아래에서 올라옴 .38s · 위 56 · 아래 선 · 진행선 2px 보라 .9s)
 * 실제 앱에서는 언론사 페이지(WebView)가 열리는 자리 — mock 단계라 원본처럼 0.95초 뼈대 뒤 제목만 보여 줌.
 */
export function NewsBrowser({ item, onClose, onOpenExternal }: { item: HomeNewsItem | null; onClose: () => void; onOpenExternal: (url: string) => void }) {
  const k = useMotionK();
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();
  const [last, setLast] = useState(item);
  if (item && item !== last) setLast(item);
  const [shown, setShown] = useState(!!item);
  if (item && !shown) setShown(true);
  const [y] = useState(() => new Animated.Value(height));
  const [prog] = useState(() => new Animated.Value(0));
  const [loadedId, setLoadedId] = useState<string | null>(null);
  useEffect(() => {
    if (!shown) return;
    const a = Animated.timing(y, { toValue: item ? 0 : height, duration: 380 * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start(({ finished }) => {
      if (finished && !item) setShown(false);
    });
    return () => a.stop();
  }, [item, shown, y, height, k]);
  useEffect(() => {
    if (!item) return;
    prog.setValue(0);
    const a = Animated.timing(prog, { toValue: 1, duration: 900 * k, easing: Easing.bezier(0.2, 0.7, 0.3, 1), useNativeDriver: false });
    a.start();
    const id = item.id;
    const t = setTimeout(() => setLoadedId(id), 950 * k);
    return () => {
      a.stop();
      clearTimeout(t);
    };
  }, [item, prog, k]);
  if (!shown || !last) return null;
  const loaded = loadedId === last.id;
  const host = /^https?:\/\/([^/?#]+)/.exec(last.url)?.[1]?.replace(/^www\./, '') ?? '';
  return (
    <Modal transparent visible animationType="none" onRequestClose={onClose} statusBarTranslucent navigationBarTranslucent>
      <DarkLayer>
      <Animated.View style={[st.brow, { paddingTop: insets.top, transform: [{ translateY: y }] }]}>
        <View style={st.bt}>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="닫기" style={st.ib}>
            <BrowserClose />
          </Pressable>
          <View style={st.u}>
            <Text style={st.uB} numberOfLines={1}>
              {last.src}
            </Text>
            <Text style={st.uS} numberOfLines={1}>
              {host}
            </Text>
          </View>
          <Pressable onPress={() => onOpenExternal(last.url)} accessibilityRole="button" accessibilityLabel="브라우저로 열기" style={st.ib}>
            <BrowserExternal />
          </Pressable>
          <Animated.View style={[st.bprog, { width: prog.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] }), opacity: loaded ? 0 : 1 }]} />
        </View>
        <ScrollView contentContainerStyle={[st.bc, { paddingBottom: 20 + insets.bottom }]}>
          {!loaded ? (
            <>
              <Skeleton style={{ height: 14, width: '30%' }} />
              <Skeleton style={{ height: 24, marginVertical: 14 }} />
              <Skeleton style={{ height: 24, width: '70%' }} />
              <Skeleton style={{ height: 12, marginTop: 22 }} />
              <Skeleton style={{ height: 12, marginTop: 10 }} />
              <Skeleton style={{ height: 12, marginTop: 10, width: '85%' }} />
            </>
          ) : (
            <>
              <Text style={st.meta}>
                {last.src} · {last.at.slice(0, 10).replace(/-/g, '.')} {hm(last.at)}
              </Text>
              <Text style={st.h2}>{last.title}</Text>
              <Text style={st.p}>여기에는 언론사 페이지가 그대로 열려요. memo&apos;s 화면이 아니라 원문 사이트예요.</Text>
            </>
          )}
        </ScrollView>
      </Animated.View>
      </DarkLayer>
    </Modal>
  );
}

const st = StyleSheet.create({
  brow: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, backgroundColor: '#FFFFFF' },
  bt: { height: 56, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 6, borderBottomWidth: 1, borderBottomColor: appColor.line },
  ib: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  u: { flex: 1, minWidth: 0 },
  uB: { ...ft(14.5), fontWeight: '700', color: appColor.ink },
  uS: { ...ft(12), color: appColor.ink3 },
  bprog: { position: 'absolute', left: 0, bottom: -1, height: 2, backgroundColor: appColor.accent },
  bc: { padding: 20 },
  meta: { ...ft(12), color: appColor.ink3 },
  h2: { ...ft(21, 1.45), fontWeight: '700', color: appColor.ink, marginTop: 6, marginBottom: 10 },
  p: { ...ft(15, 1.85), color: '#3F434A' },
});
