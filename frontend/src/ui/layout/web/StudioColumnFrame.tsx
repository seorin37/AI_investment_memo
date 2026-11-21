import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { AppIcon, WebIcon } from '@/ui/icons/Icon';
import { fpx, size, studioFeature, webColor } from '@/ui/theme';
import { useCoachRef } from '@/ui/shared/Coach';
import type { StudioColumnFrameProps, StudioFeature } from './WebShell.types';

type HoverState = { pressed: boolean; hovered?: boolean };

/* 접힌 열 기능 점 (원본 .st-dot: 1.6s ease-in-out 무한 · 50% 에서 바깥 5px 링 rgba(229,72,77,.18)) */
function RailDot({ label }: { label: string }) {
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.loop(Animated.sequence([
      Animated.timing(v, { toValue: 1, duration: 800, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
      Animated.timing(v, { toValue: 0, duration: 800, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
    ]));
    a.start();
    return () => a.stop();
  }, [v]);
  return (
    <View style={st.dotWrap} pointerEvents="none">
      <Animated.View style={[st.dotRing, { opacity: v }]} />
      <View style={st.dot}>
        <Text style={st.dotT}>{label}</Text>
      </View>
    </View>
  );
}

const FEAT: { key: StudioFeature; label: string }[] = [
  { key: 'audio', label: 'AI 오디오' },
  { key: 'report', label: 'AI 주간보고서' },
  { key: 'quiz', label: '오늘의 퀴즈' },
  { key: 'lab', label: 'AI 투자 실험실' },
];

/** 스튜디오 기능 아이콘 (접힘 열 · 스튜디오 홈 같이 씀) */
export function FeatIcon({ f, size = 20 }: { f: StudioFeature; size?: number }) {
  const c = studioFeature[f].ink;
  if (f === 'audio') return <AppIcon name="waveBlue" size={size} color={c} />;
  if (f === 'report') return <AppIcon name="reportFile" size={size} color={c} />;
  if (f === 'quiz') return <WebIcon name="helpRing" size={size} color={c} />;
  return <WebIcon name="flask" size={size} color={c} />;
}

/**
 * 웹 오른쪽 스튜디오 열의 틀 (원본 studio.tsx StudioColumn 바깥)
 * 펼침: 바깥 436 (위·오른쪽·아래 24) · 카드 412 · 라운드 22 · 테두리 #E4E4E7 · 머리 72
 * 접힘: 바깥 96 · 카드 72 · 높이 800(최대 100%) · 기능 버튼 4개
 * 카드 안 내용은 ⑧ 스튜디오 묶음에서 children 으로.
 */
export function StudioColumnFrame({ open, onToggle, stockCount, aiMemoCount, usagePct, onUsage, onFeature, badges, children }: StudioColumnFrameProps) {
  /* 사용법 안내 ④ 대상 (원본 studio.tsx data-coach="studio") */
  const coachRef = useCoachRef('studio');
  if (!open)
    return (
      <View style={st.colClosed} accessibilityLabel="스튜디오 (접힘)">
        <View style={st.rail}>
          <Pressable onPress={onToggle} accessibilityRole="button" accessibilityLabel="스튜디오 펼치기" style={({ hovered }: HoverState) => [st.railBtn, hovered && { backgroundColor: webColor.hover }]}>
            <WebIcon name="studioUnfold" size={20} />
          </Pressable>
          <View style={st.spacer} />
          <View style={st.railLine} />
          {FEAT.map((f) => (
            <Pressable key={f.key} onPress={() => onFeature(f.key)} accessibilityRole="button" accessibilityLabel={f.label} style={[st.railBtn, { backgroundColor: studioFeature[f.key].box }]}>
              <FeatIcon f={f.key} />
              {badges?.[f.key] ? <RailDot label={badges[f.key]!} /> : null}
            </Pressable>
          ))}
        </View>
      </View>
    );
  const out = usagePct >= 100;
  return (
    <View style={st.col} accessibilityLabel="스튜디오">
      <View ref={coachRef} collapsable={false} style={st.card}>
        <View style={st.head}>
          <View style={st.star}>
            <WebIcon name="sparkleNudge" size={19} color="#FFFFFF" />
          </View>
          <View style={st.headText}>
            <Text style={st.title} numberOfLines={1}>
              스튜디오
            </Text>
            <Text style={st.sub} numberOfLines={1}>
              내 종목 {stockCount} · AI 연결 메모 {aiMemoCount}
            </Text>
          </View>
          <Pressable onPress={onUsage} accessibilityRole="button" accessibilityLabel={`AI 사용량 ${usagePct}%`} style={({ hovered }: HoverState) => [st.usage, { backgroundColor: out ? webColor.usageOutBg : hovered ? webColor.chipHover : webColor.chip }]}>
            <View style={st.bar}>
              <View style={[st.barFill, { width: `${Math.min(100, usagePct)}%`, backgroundColor: out ? webColor.usageOutBar : webColor.ink }]} />
            </View>
            <Text style={[st.usageT, { color: out ? webColor.usageOutInk : webColor.ink }]}>AI 사용량 {usagePct}%</Text>
          </Pressable>
          <Pressable onPress={onToggle} accessibilityRole="button" accessibilityLabel="스튜디오 접기" style={({ hovered }: HoverState) => [st.fold, hovered && { backgroundColor: webColor.hover }]}>
            <WebIcon name="studioFold" size={18} />
          </Pressable>
        </View>
        <View style={st.body}>{children}</View>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  col: { width: size.studioCol, height: '100%', paddingTop: 24, paddingRight: 24, paddingBottom: 24 },
  card: { width: size.studioCard, flex: 1, overflow: 'hidden', borderRadius: 22, borderWidth: 1, borderColor: webColor.studioLine, backgroundColor: webColor.surface },
  head: { height: 72, flexDirection: 'row', alignItems: 'center', gap: 10, paddingBottom: 10, paddingLeft: 20, paddingRight: 12, paddingTop: 20 },
  star: { width: 32, height: 32, borderRadius: 10, backgroundColor: webColor.ink, alignItems: 'center', justifyContent: 'center' },
  headText: { flex: 1, minWidth: 0 },
  /* 원본 text-[22px] leading-[1.3] tracking-[-0.4px] */
  title: { fontSize: 22, lineHeight: 28.6, letterSpacing: -0.4, fontWeight: '700', color: webColor.ink },
  sub: { ...fpx(14, 21), color: webColor.studioSub },
  usage: { height: 32, flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 999, paddingHorizontal: 12 },
  bar: { width: 24, height: 6, borderRadius: 999, overflow: 'hidden', backgroundColor: 'rgba(0,0,0,0.1)' },
  barFill: { position: 'absolute', left: 0, top: 0, bottom: 0, borderRadius: 999 },
  usageT: { fontSize: 13, lineHeight: 20, fontWeight: '700' },
  fold: { width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  body: { flex: 1, minHeight: 0 },
  colClosed: { width: size.studioColClosed, height: '100%', paddingVertical: 24, paddingRight: 24 },
  rail: { height: 800, maxHeight: '100%', width: size.studioRail, alignItems: 'center', gap: 10, borderRadius: 20, borderWidth: 1, borderColor: webColor.line, backgroundColor: webColor.surface, paddingVertical: 18 },
  railBtn: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  spacer: { height: 16 },
  railLine: { height: 1, width: 32, backgroundColor: webColor.line3 },
  dotWrap: { position: 'absolute', right: -12, top: -4 },
  dotRing: { position: 'absolute', left: -5, top: -5, right: -5, bottom: -5, borderRadius: 999, backgroundColor: 'rgba(229,72,77,0.18)' },
  dot: { height: 16, minWidth: 16, borderRadius: 999, borderWidth: 2, borderColor: '#FFFFFF', backgroundColor: webColor.badge, paddingHorizontal: 3, alignItems: 'center', justifyContent: 'center' },
  dotT: { fontSize: 11, lineHeight: 11, fontWeight: '500', color: '#FFFFFF' },
});
