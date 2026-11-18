/**
 * 사용법 안내 스포트라이트 (Lucian #197 guided-spotlight) — 체험판 x/app 스타일의 .u197 값.
 *  - 어두운 막(.66)에 둥근 구멍 → 다음 대상으로 옮겨 가며 살짝 넘쳤다 멈춤 (.52s)
 *  - 구멍 둘레 흰 고리가 1.5초마다 퍼짐 · 말풍선은 꼬리와 함께 따라옴 (.45s cubic-bezier(.3,1.15,.4,1))
 *  - 말풍선 글은 바뀔 때 4px 아래에서 떠오름 (.35s) · 단계 점은 현재 단계만 18px 로 늘어남
 * 대상 위치(target)는 화면이 measureInWindow 등으로 재서 넘김. 화면 전체를 덮는 자리(Modal 등)에 둠.
 */
import { useEffect } from 'react';
import { Animated, Pressable, StyleSheet, View, useWindowDimensions } from 'react-native';
import { Text } from '@/components/ui/AppText';
import Svg, { Path } from 'react-native-svg';
import { Appear } from '@/components/motion/Appear';
import { EASE, MOVE, ND, SPRING, tween, useReduceMotion, useTweenNumber, useValue } from '@/components/motion/motion';

const M = { dim: 'rgba(10,12,22,0.66)', ring: '#FFFFFF', tip: '#FFFFFF', text: '#16171A', sub: '#575B63', muted: '#9A9EA7', dot: '#D5D8DD', dotOn: '#6A42AB', next: '#8569E3', skip: '#F2F2F5', white: '#FFFFFF' } as const;
/** 구멍이 옮겨 갈 때 살짝 넘쳤다 멈춤 */
const HOLE = SPRING;

export interface CoachStep { target: { x: number; y: number; width: number; height: number } | null; kicker: string; title: string; body: string }

export interface CoachSpotlightProps {
  steps: CoachStep[];
  index: number;
  onNext: () => void;
  onPrev: () => void;
  onSkip: () => void;
}

export function CoachSpotlight({ steps, index, onNext, onPrev, onSkip }: CoachSpotlightProps) {
  const { width: W, height: H } = useWindowDimensions();
  const step = steps[index];
  const tg = step.target ?? { x: W / 2, y: H / 2, width: 0, height: 0 };
  const pad = step.target ? 6 : 0;
  const hx = useTweenNumber(tg.x - pad, 520, HOLE), hy = useTweenNumber(tg.y - pad, 520, HOLE);
  const hw = useTweenNumber(tg.width + pad * 2, 520, HOLE), hh = useTweenNumber(tg.height + pad * 2, 520, HOLE);
  const r = Math.min(14, hw / 2, hh / 2);
  const hole = hw > 0 ? `M${hx + r},${hy}H${hx + hw - r}Q${hx + hw},${hy} ${hx + hw},${hy + r}V${hy + hh - r}Q${hx + hw},${hy + hh} ${hx + hw - r},${hy + hh}H${hx + r}Q${hx},${hy + hh} ${hx},${hy + hh - r}V${hy + r}Q${hx},${hy} ${hx + r},${hy}Z` : '';
  const below = tg.y + tg.height / 2 < H * 0.55;
  const tipTop = step.target ? (below ? tg.y + tg.height + pad + 14 : undefined) : H / 2 - 110;
  const tipBottom = step.target && !below ? H - tg.y + pad + 14 : undefined;
  const tipX = Math.max(16, Math.min(W - 16 - Math.min(320, W - 32), tg.x + tg.width / 2 - 160));
  const arrowX = Math.max(22, Math.min(Math.min(320, W - 32) - 22, tg.x + tg.width / 2 - tipX));
  const ax = useTweenNumber(arrowX, 450, MOVE);
  const ov = useValue(0);
  const pulse = useValue(0);
  const still = useReduceMotion();
  useEffect(() => { tween(ov, 1, 350, EASE, ND).start(); }, [ov]);
  useEffect(() => {
    if (still) return;
    const loop = Animated.loop(tween(pulse, 1, 1500, EASE, ND));
    loop.start();
    return () => loop.stop();
  }, [pulse, still]);

  return (
    <Animated.View style={[StyleSheet.absoluteFill, { opacity: ov }]} accessibilityViewIsModal>
      <Svg width={W} height={H} style={StyleSheet.absoluteFill}>
        <Path d={`M0,0H${W}V${H}H0Z${hole}`} fill={M.dim} fillRule="evenodd" />
      </Svg>
      <Pressable style={StyleSheet.absoluteFill} onPress={() => {}} accessible={false} />
      {step.target && (
        <>
          <View pointerEvents="none" style={[st.ring, { left: hx, top: hy, width: hw, height: hh, borderRadius: r }]} />
          <Animated.View pointerEvents="none" style={[st.ring, { left: hx, top: hy, width: hw, height: hh, borderRadius: r,
            opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.9, 0] }),
            transform: [{ scaleX: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1 + 20 / Math.max(hw, 1)] }) }, { scaleY: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1 + 20 / Math.max(hh, 1)] }) }] }]} />
        </>
      )}
      <Appear kind="pop" replay={index} style={[st.tip, { left: tipX, top: tipTop, bottom: tipBottom, width: Math.min(320, W - 32) }]}>
        {step.target && <View style={[st.arrow, below ? st.arrowUp : st.arrowDown, { left: ax - 7 }]} />}
        <Pressable onPress={onSkip} style={st.skipX} hitSlop={6} accessibilityRole="button"><Text style={st.skipXText}>건너뛰기</Text></Pressable>
        <Appear kind="up" replay={index}>
          <Text style={st.kicker}>{step.kicker}</Text>
          <Text style={st.title}>{step.title}</Text>
          <Text style={st.body}>{step.body}</Text>
        </Appear>
        <View style={st.foot}>
          <View style={st.dots}>{steps.map((_, i) => <Dot key={i} on={i === index} />)}</View>
          {index > 0 && <Pressable onPress={onPrev} style={[st.btn, st.prev]} accessibilityRole="button"><Text style={st.prevText}>이전</Text></Pressable>}
          <Pressable onPress={onNext} style={[st.btn, st.next]} accessibilityRole="button"><Text style={st.nextText}>{index === steps.length - 1 ? '시작하기' : '다음'}</Text></Pressable>
        </View>
      </Appear>
    </Animated.View>
  );
}

function Dot({ on }: { on: boolean }) {
  const w = useTweenNumber(on ? 18 : 6, 300, SPRING);
  return <View style={[st.dot, { width: w, backgroundColor: on ? M.dotOn : M.dot }]} />;
}

const st = StyleSheet.create({
  ring: { position: 'absolute', borderWidth: 2, borderColor: M.ring },
  tip: { position: 'absolute', backgroundColor: M.tip, borderRadius: 18, paddingHorizontal: 20, paddingTop: 18, paddingBottom: 16 },
  arrow: { position: 'absolute', width: 14, height: 14, backgroundColor: M.tip, borderRadius: 2, transform: [{ rotate: '45deg' }] },
  arrowUp: { top: -6 },
  arrowDown: { bottom: -6 },
  skipX: { position: 'absolute', right: 10, top: 10, height: 32, paddingHorizontal: 8, justifyContent: 'center', zIndex: 1 },
  skipXText: { fontSize: 13, fontWeight: '700', color: M.muted },
  kicker: { fontSize: 13, lineHeight: 20, fontWeight: '700', color: M.muted },
  title: { marginTop: 2, fontSize: 19, lineHeight: 27, fontWeight: '800', color: M.text },
  body: { marginTop: 4, marginBottom: 14, fontSize: 14.5, lineHeight: 22, color: M.sub },
  foot: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  dots: { flexDirection: 'row', gap: 5, marginRight: 'auto' },
  dot: { height: 6, borderRadius: 3 },
  btn: { height: 44, paddingHorizontal: 16, borderRadius: 12, justifyContent: 'center' },
  prev: { backgroundColor: M.skip },
  prevText: { fontSize: 15, fontWeight: '700', color: M.text },
  next: { backgroundColor: M.next },
  nextText: { fontSize: 15, fontWeight: '700', color: M.white },
});
