/**
 * 단계 넘기기 (Lucian #042 wizard-stepper) — 서비스 소개 3장 · 가입 단계.
 * 다음으로 가면 새 내용이 오른쪽 40% 에서, 이전으로 가면 왼쪽 40% 에서 밀려 들어옴 (.55s ease · 투명도 .35s).
 * step 이 바뀔 때만 움직임. 폭은 부모 폭을 재서 씀.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Animated, View, type StyleProp, type ViewStyle, type LayoutChangeEvent } from 'react-native';
import { EASE, ND, tween, useValue } from '@/components/motion/motion';

export function StepSlide({ step, children, style }: { step: number; children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const [w, setW] = useState(0);
  const x = useValue(0);
  const o = useValue(1);
  const prev = useRef(step);
  useEffect(() => {
    if (prev.current === step) return;
    const dir = step > prev.current ? 1 : -1;
    prev.current = step;
    x.setValue(dir * w * 0.4);
    o.setValue(0);
    Animated.parallel([tween(x, 0, 550, EASE, ND), tween(o, 1, 350, EASE, ND)]).start();
  }, [step, w, x, o]);
  return (
    <View style={style} onLayout={(e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width)}>
      <Animated.View style={{ flex: 1, opacity: o, transform: [{ translateX: x }] }}>{children}</Animated.View>
    </View>
  );
}
