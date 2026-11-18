/**
 * 스튜디오 — "쌓인 소식을 듣고, 읽고, 실험해 보세요" · AI 사용량 칩 · 기능 카드 4개 · 만든 항목(맨 위 라디오 카드 + 목록).
 * 체험판 studio.html. 상단 바(스튜디오 · 알림 · 프로필)는 TopBar 로 따로.
 * 움직임: 기능 카드가 차례로 떠오름 · 누르면 spring · 재생 ↔ 멈춤 모양 바뀜(#007) · 재생 중엔 소리 막대가 춤춤
 *        · 사용량 %가 올라감(#098)
 */
import { useEffect, useRef } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { Appear } from '@/components/motion/Appear';
import { CountUp } from '@/components/motion/CountUp';
import { EASE, ND, tween, useReduceMotion } from '@/components/motion/motion';
import { PlayPause } from '@/components/motion/PlayPause';
import { usePressScale } from '@/components/motion/StateMotion';
import type { StudioFeatureKey, StudioHomeProps } from '@/features/studio/StudioHome.types';

const C = {
  appBg: '#F3F4F6',
  card: '#FFFFFF',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  line: '#EEF0F3',
  white: '#FFFFFF',
  accent: '#8569E3',
  accentDeep: '#6A42AB',
  accentSoft: '#EEE9FB',
  warnBg: '#FFF1C9',
  warnText: '#8A5A00',
  wave: '#C9D6F5',
  waveOn: '#3D73F0',
  play: '#3D73F0',
} as const;
const FEAT: Record<StudioFeatureKey, { bg: string; fg: string }> = {
  audio: { bg: '#DCE7FF', fg: '#3D73F0' },
  report: { bg: '#FFE1E1', fg: '#E5484D' },
  lab: { bg: '#FFEDB8', fg: '#B07800' },
  quiz: { bg: '#D9F2E2', fg: '#1F8A4C' },
};
const PAD = 16;
const GAP = 12;
const R = { card: 20, icon: 16 };
const WAVE = [8, 14, 10, 18, 12, 20, 9, 16, 22, 13, 17, 10, 19, 12, 8, 15, 11, 18, 9, 14, 12, 7];

export function StudioHome({ usage_percent, usage_spent, features, featured_audio, made, onOpenUsage, onOpenFeature, onPlayAudio, playing_id, onOpenMade, onScroll }: StudioHomeProps) {
  const playing = !!featured_audio && playing_id === featured_audio.id;
  return (
    <ScrollView style={st.root} contentContainerStyle={st.body} onScroll={onScroll} scrollEventThrottle={16}>
      <View style={st.subRow}>
        <Text style={st.sub} numberOfLines={2}>쌓인 소식을 듣고, 읽고, 실험해 보세요</Text>
        <Pressable onPress={onOpenUsage} hitSlop={{ top: 8, bottom: 8, left: 4, right: 4 }} accessibilityRole="button">
          <View style={[st.usage, usage_spent && st.usageSpent]}>
            <Text style={[st.usageText, usage_spent && st.usageTextSpent]}>⚡ AI 사용량 <CountUp value={usage_spent ? 100 : usage_percent} style={[st.usageText, usage_spent && st.usageTextSpent]} />%</Text>
          </View>
        </Pressable>
      </View>

      {features.map((f, i) => (
        <Appear key={f.key} kind="up" index={i}>
          <FeatureCard title={f.title} desc={f.desc} k={f.key} onPress={() => onOpenFeature(f.key)} />
        </Appear>
      ))}

      <View style={st.madeHead}>
        <Text style={st.madeTitle}>만든 항목</Text>
        <Text style={st.madeSub}>30일 보관 · 다시 보기 무료</Text>
      </View>

      {featured_audio && (
        <Appear kind="up" index={features.length} style={st.mfeat}>
          <View style={st.mfHead}><MobileIcon name="audio" size={14} color={C.play} /><Text style={st.mfTag}>AI 오디오 · 최신</Text></View>
          <Text style={st.mfTitle}>{featured_audio.title}</Text>
          <Text style={st.mfSub}>{featured_audio.sub}</Text>
          <View style={st.player}>
            <PlayPause playing={playing} onPress={() => onPlayAudio(featured_audio.id)} bg={C.play} fg={C.white} />
            <View style={st.wave}>
              {WAVE.map((h, i) => <WaveBar key={i} h={h} i={i} on={i / WAVE.length < featured_audio.progress} playing={playing} />)}
            </View>
            <Text style={st.dur}>{featured_audio.duration}</Text>
          </View>
          <View style={st.mfFoot}><Text style={st.mfMeta}>{featured_audio.meta}</Text><Text style={st.mfMeta}>{featured_audio.expire_label}</Text></View>
        </Appear>
      )}

      {made.length > 0 && (
        <View style={st.madeList}>
          {made.map((m, i) => (
            <Pressable key={m.id} style={[st.mi, i > 0 && st.miLine]} onPress={() => onOpenMade(m.id)} accessibilityRole="button">
              <View style={[st.mIcon, { backgroundColor: FEAT[m.kind].bg }]}><MobileIcon name={m.kind} size={18} color={FEAT[m.kind].fg} /></View>
              <View style={st.flex}>
                <Text style={st.miTitle} numberOfLines={1}>{m.title}</Text>
                <Text style={st.miSub} numberOfLines={1}>{m.sub}</Text>
              </View>
              <Text style={st.miRight}>{m.expire_label}</Text>
            </Pressable>
          ))}
        </View>
      )}
      <Text style={st.note}>스튜디오는 투자 권유나 주가 예측을 하지 않아요.</Text>
    </ScrollView>
  );
}

function FeatureCard({ title, desc, k, onPress }: { title: string; desc: string; k: StudioFeatureKey; onPress: () => void }) {
  const p = usePressScale(0.97);
  return (
    <Pressable onPress={onPress} onPressIn={p.onPressIn} onPressOut={p.onPressOut} accessibilityRole="button">
      <Animated.View style={[st.feat, { transform: [{ scale: p.scale }] }]}>
        <View style={[st.fi, { backgroundColor: FEAT[k].bg }]}>
          <MobileIcon name={k} size={23} color={FEAT[k].fg} strokeWidth={1.8} />
        </View>
        <View style={st.flex}>
          <Text style={st.featTitle}>{title}</Text>
          <Text style={st.featDesc} numberOfLines={2}>{desc}</Text>
        </View>
        <MobileIcon name="chevron_right" size={18} color={C.muted} />
      </Animated.View>
    </Pressable>
  );
}

/** 소리 막대: 재생 중이면 각자 다른 박자로 줄었다 늘었다 (체험판 .wave · eq) */
function WaveBar({ h, i, on, playing }: { h: number; i: number; on: boolean; playing: boolean }) {
  const v = useRef(new Animated.Value(1)).current;
  const still = useReduceMotion();
  useEffect(() => {
    if (!playing || still) { tween(v, 1, 200, EASE, ND).start(); return; }
    const d = 320 + ((i * 53) % 260);
    const loop = Animated.loop(Animated.sequence([tween(v, 0.45, d, EASE, ND), tween(v, 1, d, EASE, ND)]));
    loop.start();
    return () => loop.stop();
  }, [playing, still, v, i]);
  return <Animated.View style={[st.bar, { height: h, backgroundColor: on ? C.waveOn : C.wave, transform: [{ scaleY: v }] }]} />;
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.appBg },
  flex: { flex: 1, minWidth: 0 },
  body: { paddingHorizontal: PAD, paddingBottom: 40, gap: GAP },
  subRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 2 },
  sub: { flex: 1, fontSize: 13.5, color: C.sub },
  usage: { height: 28, borderRadius: 14, paddingHorizontal: 10, backgroundColor: C.accentSoft, justifyContent: 'center' },
  usageSpent: { backgroundColor: C.warnBg },
  usageText: { fontSize: 13, fontWeight: '800', color: C.accentDeep },
  usageTextSpent: { color: C.warnText },
  feat: { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: C.card, borderRadius: R.card, padding: 16, minHeight: 82 },
  fi: { width: 50, height: 50, borderRadius: R.icon, alignItems: 'center', justifyContent: 'center' },
  featTitle: { fontSize: 17, fontWeight: '800', color: C.text },
  featDesc: { fontSize: 13.5, color: C.sub, marginTop: 3 },
  madeHead: { flexDirection: 'row', alignItems: 'baseline', gap: 8, marginTop: 14 },
  madeTitle: { fontSize: 17, fontWeight: '800', color: C.text },
  madeSub: { fontSize: 12.5, color: C.muted },
  mfeat: { backgroundColor: C.card, borderRadius: R.card, padding: 18 },
  mfHead: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  mfTag: { fontSize: 13, fontWeight: '700', color: C.play },
  mfTitle: { fontSize: 19, fontWeight: '800', color: C.text, marginTop: 8 },
  mfSub: { fontSize: 13.5, color: C.sub, marginTop: 3 },
  player: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 16 },
  wave: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 3, height: 24, overflow: 'hidden' },
  bar: { width: 3, borderRadius: 2 },
  dur: { fontSize: 13, fontWeight: '700', color: C.sub },
  mfFoot: { flexDirection: 'row', justifyContent: 'space-between', borderTopWidth: 1, borderTopColor: C.line, marginTop: 16, paddingTop: 12 },
  mfMeta: { fontSize: 12.5, color: C.muted },
  madeList: { backgroundColor: C.card, borderRadius: R.card, paddingHorizontal: 16 },
  mi: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 66, paddingVertical: 10 },
  miLine: { borderTopWidth: 1, borderTopColor: C.line },
  mIcon: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  miTitle: { fontSize: 15, fontWeight: '800', color: C.text },
  miSub: { fontSize: 12.5, color: C.sub, marginTop: 2 },
  miRight: { fontSize: 12, color: C.muted },
  note: { textAlign: 'center', fontSize: 12, color: C.muted, marginTop: 8 },
});
