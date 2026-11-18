/**
 * 체크 상자 (Lucian #014 checkbox-ink + 체험판 체크리스트 .ckr2 .cc)
 *  - 체크하면 안쪽이 가운데에서 번지며 채워지고(.35s spring) 상자가 .6 → 1.15 → 1 로 톡 (.38s)
 *  - 둘레로 잉크 고리가 퍼지며 사라짐 (.5s)
 *  - 체크 표시는 .3s 로 그려짐 (.08s 뒤)
 *  - burst 를 켜면 점 8개(#093 DotBurst)도 같이 튐
 * 원형(라운드 = 크기 절반)과 모서리 둥근 네모 둘 다.
 */
import { useEffect, useRef, useState } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { DotBurst } from '@/components/motion/Celebrate';
import { EASE, ND, SPRING, tween, useProgress, useValue } from '@/components/motion/motion';

const M = { mark: '#FFFFFF' } as const;

export interface InkCheckProps {
  checked: boolean;
  color: string;
  lineColor: string;
  size?: number;
  radius?: number;
  bg?: string;
  burst?: boolean;
}

export function InkCheck({ checked, color, lineColor, size = 24, radius = 8, bg = 'transparent', burst }: InkCheckProps) {
  const fill = useValue(checked ? 1 : 0);
  const pop = useValue(1);
  const ink = useValue(0);
  const [fire, setFire] = useState(0);
  const was = useRef(checked);
  const draw = useProgress(checked ? fire || 'on' : 'off', checked ? 300 : 0, EASE, checked ? 80 : 0);

  useEffect(() => {
    if (was.current === checked) return;
    was.current = checked;
    tween(fill, checked ? 1 : 0, checked ? 350 : 200, checked ? SPRING : EASE, ND).start();
    if (!checked) return;
    pop.setValue(0.6);
    ink.setValue(0);
    Animated.parallel([tween(pop, 1, 380, SPRING, ND), tween(ink, 1, 500, EASE, ND)]).start();
    if (burst) setFire((f) => f + 1);
  }, [checked, burst, fill, pop, ink]);

  const s = size * 0.62, L = 20;
  return (
    <View style={{ width: size, height: size }}>
      <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, { borderRadius: radius, borderWidth: 2, borderColor: color,
        opacity: ink.interpolate({ inputRange: [0, 0.01, 1], outputRange: [0, 0.35, 0] }),
        transform: [{ scale: ink.interpolate({ inputRange: [0, 1], outputRange: [1, 2] }) }] }]} />
      <Animated.View style={[StyleSheet.absoluteFill, st.box, { borderRadius: radius, borderColor: lineColor, backgroundColor: bg, transform: [{ scale: pop }] }]}>
        <Animated.View style={[StyleSheet.absoluteFill, { borderRadius: radius, backgroundColor: color, opacity: fill.interpolate({ inputRange: [0, 0.2, 1], outputRange: [0, 1, 1], extrapolate: 'clamp' }), transform: [{ scale: fill }] }]} />
        {checked && (
          <Svg width={s} height={s} viewBox="0 0 16 16">
            <Path d="M3.2 8.4l3.1 3.1 6.5-6.8" stroke={M.mark} strokeWidth={2.4} fill="none" strokeLinecap="round" strokeLinejoin="round" strokeDasharray={`${L} ${L}`} strokeDashoffset={L * (1 - draw)} />
          </Svg>
        )}
      </Animated.View>
      {burst && <DotBurst fire={fire} size={size} />}
    </View>
  );
}

const st = StyleSheet.create({
  box: { borderWidth: 1.6, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
});
