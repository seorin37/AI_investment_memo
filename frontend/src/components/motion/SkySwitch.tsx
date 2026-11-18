/**
 * 낮·밤 하늘 스위치 (Lucian #021 sun-moon toggle) — MY › 다크 모드.
 * 원본 224×94 를 체험판처럼 64×27(0.2857배)로. 값은 원본 그대로:
 *  - 해가 오른쪽으로 130 굴러가며 200° 돌고 달이 덮임 (.9s spring / 달 .8s ease · .4s 투명도)
 *  - 하늘이 밤색으로 (.8s) · 구름은 아래로 사라지고 (.8s / .6s) · 별이 내려오며 반짝임 (2.4s 반복)
 * 그라데이션 대신 원본 두 색의 중간색 한 가지씩.
 */
import { useEffect } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { EASE, ND, SPRING, tween, useReduceMotion, useValue } from '@/components/motion/motion';

const M = {
  day: '#7DC7FF',
  night: '#1B2349',
  halo: '#FFFFFF',
  sun: '#FFD23F',
  sunHi: '#FFF1A8',
  moon: '#D7DBE6',
  crater: '#A3AABC',
  cloud: '#FFFFFF',
  cloud2: '#E3F1FF',
  star: '#FFFFFF',
} as const;
const S = 64 / 224;
const z = (v: number) => v * S;
const STARS = [[40, 22], [70, 52], [104, 18], [128, 64], [150, 30]];

export function SkySwitch({ value, onChange, accessibilityLabel = '다크 모드' }: { value: boolean; onChange: (v: boolean) => void; accessibilityLabel?: string }) {
  const sun = useValue(value ? 1 : 0);     // .9s spring
  const sky = useValue(value ? 1 : 0);     // .8s ease
  const moonO = useValue(value ? 1 : 0);   // .4s
  const tw = useValue(0);
  const still = useReduceMotion();

  useEffect(() => {
    const to = value ? 1 : 0;
    Animated.parallel([tween(sun, to, 900, SPRING, ND), tween(sky, to, 800, EASE, ND), tween(moonO, to, 400, EASE, ND)]).start();
  }, [value, sun, sky, moonO]);
  useEffect(() => {
    if (still || !value) return;
    const loop = Animated.loop(Animated.sequence([tween(tw, 1, 1200, EASE, ND), tween(tw, 0, 1200, EASE, ND)]));
    loop.start();
    return () => loop.stop();
  }, [tw, still, value]);

  const roll = sun.interpolate({ inputRange: [0, 1], outputRange: [0, z(130)] });
  const spin = sun.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '200deg'] });
  const moonX = sky.interpolate({ inputRange: [0, 1], outputRange: [z(78), 0] });
  const cloudY = sky.interpolate({ inputRange: [0, 1], outputRange: [0, z(80)] });
  const cloudO = sky.interpolate({ inputRange: [0, 0.75, 1], outputRange: [1, 0, 0] });
  const starY = sky.interpolate({ inputRange: [0, 1], outputRange: [z(-30), 0] });
  const starO = sky.interpolate({ inputRange: [0, 0.75, 1], outputRange: [0, 1, 1] });
  const twO = tw.interpolate({ inputRange: [0, 1], outputRange: [1, 0.3] });

  return (
    <Pressable onPress={() => onChange(!value)} hitSlop={9} accessibilityRole="switch" accessibilityState={{ checked: value }} accessibilityLabel={accessibilityLabel}>
      <View style={st.track}>
        <Animated.View style={[StyleSheet.absoluteFill, st.night, { opacity: sky }]} />
        <Animated.View style={[st.haloBox, { transform: [{ translateX: roll }] }]}>
          {[222, 176, 130].map((d) => <View key={d} style={[st.halo, { width: z(d), height: z(d), borderRadius: z(d) / 2, marginLeft: -z(d) / 2, marginTop: -z(d) / 2 }]} />)}
        </Animated.View>
        <Animated.View style={[StyleSheet.absoluteFill, { opacity: starO, transform: [{ translateY: starY }] }]}>
          {STARS.map(([sx, sy]) => <Animated.View key={sx} style={[st.star, { left: z(sx), top: z(sy), opacity: twO }]} />)}
        </Animated.View>
        <Animated.View style={[StyleSheet.absoluteFill, { opacity: cloudO, transform: [{ translateY: cloudY }] }]}>
          <View style={[st.cloud, st.cloudBack]} />
          <View style={[st.cloud, st.cloudA]} />
          <View style={[st.cloud, st.cloudB]} />
          <View style={[st.cloud, st.cloudC]} />
        </Animated.View>
        <Animated.View style={[st.knob, { transform: [{ translateX: roll }, { rotate: spin }] }]}>
          <View style={st.sunHi} />
          <Animated.View style={[StyleSheet.absoluteFill, st.moon, { opacity: moonO, transform: [{ translateX: moonX }] }]}>
            <View style={[st.crater, { left: z(20), top: z(16), width: z(20), height: z(20) }]} />
            <View style={[st.crater, { left: z(46), top: z(40), width: z(14), height: z(14) }]} />
            <View style={[st.crater, { left: z(24), top: z(48), width: z(9), height: z(9) }]} />
          </Animated.View>
        </Animated.View>
      </View>
    </Pressable>
  );
}

const st = StyleSheet.create({
  track: { width: 64, height: 27, borderRadius: 14, overflow: 'hidden', backgroundColor: M.day },
  night: { backgroundColor: M.night },
  haloBox: { position: 'absolute', left: z(47), top: z(47), width: 0, height: 0 },
  halo: { position: 'absolute', backgroundColor: M.halo, opacity: 0.12 },
  star: { position: 'absolute', width: z(5), height: z(5), borderRadius: z(3), backgroundColor: M.star },
  cloud: { position: 'absolute', borderRadius: 99, backgroundColor: M.cloud },
  cloudBack: { right: z(20), bottom: z(-30), width: z(96), height: z(52), backgroundColor: M.cloud2 },
  cloudA: { right: z(-10), bottom: z(-18), width: z(120), height: z(56) },
  cloudB: { right: z(50), bottom: z(-26), width: z(90), height: z(46) },
  cloudC: { right: z(84), bottom: z(-32), width: z(70), height: z(40) },
  knob: { position: 'absolute', left: z(8), top: z(8), width: z(78), height: z(78), borderRadius: z(39), overflow: 'hidden', backgroundColor: M.sun },
  sunHi: { position: 'absolute', left: z(14), top: z(10), width: z(34), height: z(30), borderRadius: z(17), backgroundColor: M.sunHi, opacity: 0.8 },
  moon: { borderRadius: z(39), backgroundColor: M.moon },
  crater: { position: 'absolute', borderRadius: 99, backgroundColor: M.crater },
});
