import React, { useEffect, useState } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { AppIconButton } from '@/ui/shared/IconButton';
import { nf } from '@/ui/shared/app/nf';
import { appColor, curve, ft } from '@/ui/theme';

/**
 * 종목 상세 머리 (메모 보드 · 기업정보 두 탭이 같이 씀): 높이 56 · 제목 20 bold
 * compact: 위 카드가 지나가면 제목 자리에 종목명 + 종가 (원본 기업정보 .tt)
 */
export function StockBar({ name, price, pct, compact, line, onBack, onMore }: { name: string; price: number | null; pct: number; compact: boolean; line: boolean; onBack: () => void; onMore: () => void }) {
  const insets = useSafeAreaInsets();
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(compact ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: compact ? 1 : 0, duration: 280 * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [compact, v, k]);
  const up = pct >= 0;
  return (
    <View style={[st.bar, { paddingTop: insets.top, height: 56 + insets.top }]}>
      <AppIconButton label="뒤로" size={42} icon="back2" iconSize={22} color={appColor.ink} onPress={onBack} />
      <View style={st.tt}>
        <Animated.View style={[st.ttIn, { opacity: v.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }), transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [0, -40] }) }] }]}>
          <Text style={st.ttB} numberOfLines={1}>
            {name}
          </Text>
        </Animated.View>
        <Animated.View style={[st.ttIn, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [40, 0] }) }] }]}>
          <Text style={st.miniB} numberOfLines={1}>
            {name}
          </Text>
          {price === null ? null : (
            <Text style={[st.miniS, { color: up ? appColor.up : appColor.down }]}>
              {price.toLocaleString('ko-KR')}원 {up ? '+' : ''}
              {pct.toFixed(2)}%
            </Text>
          )}
        </Animated.View>
      </View>
      <AppIconButton label="종목 메뉴" size={42} icon="moreV2" iconSize={22} color={appColor.ink} onPress={onMore} />
      {line ? <View pointerEvents="none" style={st.line} /> : null}
    </View>
  );
}

const st = StyleSheet.create({
  bar: { flexDirection: 'row', alignItems: 'center', paddingLeft: 6, paddingRight: 8, backgroundColor: appColor.bg, zIndex: 2 },
  tt: { flex: 1, height: 40, marginLeft: 2, overflow: 'hidden' },
  ttIn: { position: 'absolute', left: 0, right: 0, top: 0, height: 40, justifyContent: 'center', alignItems: 'flex-start' },
  ttB: { ...nf(20), fontWeight: '700', color: appColor.ink },
  miniB: { ...ft(15.5, 1.2), fontWeight: '700', color: appColor.ink },
  miniS: { ...ft(13), fontWeight: '600', fontVariant: ['tabular-nums'] },
  line: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 1, backgroundColor: appColor.line },
});
