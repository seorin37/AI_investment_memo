import React, { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View, type ScrollViewInstance, type ViewStyle } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { FeatIcon } from '@/ui/layout/web/StudioColumnFrame';
import { chapterAt, fmt, lineAt, type GenJob } from '@/store/studioPlayer';
import type { MadeItem } from '../Studio.types';
import type { AudioEp } from '../audioEp';
import { GBtn } from './Credit';

type Hover = { hovered?: boolean; pressed?: boolean };
type Ep = AudioEp;
const TR = { letterSpacing: -0.2 };
const SVGP = { strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
const Ico = {
  check: (c = 'white') => <Svg width={12} height={12} viewBox="0 0 12 12" fill="none"><Path d="M2.5 6L4.75 8.25L9.5 3.5" stroke={c} strokeWidth={1.5} {...SVGP} /></Svg>,
  pause: (s = 22, c = 'white') => <Svg width={s} height={s} viewBox="0 0 22 22" fill={c}><Path d="M8.07 4.58H6.6C5.99 4.58 5.5 5.08 5.5 5.68V16.32C5.5 16.92 5.99 17.42 6.6 17.42H8.07C8.67 17.42 9.17 16.92 9.17 16.32V5.68C9.17 5.08 8.67 4.58 8.07 4.58Z" /><Path d="M15.4 4.58H13.93C13.33 4.58 12.83 5.08 12.83 5.68V16.32C12.83 16.92 13.33 17.42 13.93 17.42H15.4C16.01 17.42 16.5 16.92 16.5 16.32V5.68C16.5 5.08 16.01 4.58 15.4 4.58Z" /></Svg>,
  play: (s = 22, c = 'white') => <Svg width={s} height={s} viewBox="0 0 24 24" fill={c}><Path d="M8 5.5V18.5C8 19.27 8.83 19.75 9.5 19.4L19.5 12.9C20.1 12.5 20.1 11.6 19.5 11.2L9.5 4.7C8.83 4.3 8 4.78 8 5.5Z" /></Svg>,
  alert: () => <Svg width={36} height={36} viewBox="0 0 36 36" fill="none"><Path d="M18 31.5C25.4558 31.5 31.5 25.4558 31.5 18C31.5 10.5442 25.4558 4.5 18 4.5C10.5442 4.5 4.5 10.5442 4.5 18C4.5 25.4558 10.5442 31.5 18 31.5Z" stroke="#D93033" strokeWidth={2.7} /><Path d="M18 11.25V19.5" stroke="#D93033" strokeWidth={3} strokeLinecap="round" /><Path d="M18 24.75H18.015" stroke="#D93033" strokeWidth={3.9} strokeLinecap="round" /></Svg>,
  back: () => <Svg width={18} height={18} viewBox="0 0 18 18" fill="none"><Path d="M11.25 4.5L6.75 9L11.25 13.5" stroke="#404752" strokeWidth={1.5} {...SVGP} /></Svg>,
};

/** 웹 만드는 중 = 원본 studio.tsx Gen (위 120 · 아이콘 72/22 · 제목 22 · 막대 200 · 단계 22 동그라미) */
export function WebGen({ job, steps }: { job: GenJob; steps: string[] }) {
  const cur = job.steps.findIndex((s) => s !== 'done');
  return (
    <GenView
      kind={job.kind}
      title={job.kind === 'report' ? '주간보고서를 만드는 중이에요' : '오디오를 만드는 중이에요'}
      sub={'다른 화면으로 가도 계속 만들어요.\n끝나면 알려 드릴게요.'}
      pct={job.pct}
      at={cur < 0 ? steps.length : cur}
      steps={steps}
    />
  );
}

/** 웹 실험 중 = 원본 studio.tsx Gen 의 lab (GEN_T 48줄 · STEPS 53줄). at: 지금 단계 번호 (앞 단계는 완료) */
export function WebLabGen({ pct, at }: { pct: number; at: number }) {
  return <GenView kind="lab" title="실험을 하는 중이에요" sub="잠시만 기다려 주세요." pct={pct} at={at} steps={['조건 읽기', '영향 경로 찾기', '결과 정리하기']} />;
}

function GenView({ kind, title, sub, pct, at, steps }: { kind: 'audio' | 'report' | 'lab'; title: string; sub: string; pct: number; at: number; steps: string[] }) {
  return (
    <ScrollView contentContainerStyle={st.center}>
      <View style={st.big}><FeatIcon f={kind} size={36} /></View>
      <View style={{ alignItems: 'center', gap: 6, alignSelf: 'stretch' }}>
        <Text style={st.h}>{title}</Text>
        <Text style={st.sub}>{sub}</Text>
      </View>
      <View style={st.bar}><View style={[st.barI, { width: `${pct}%` }]} /></View>
      <View style={{ gap: 10, alignItems: 'flex-start' }}>
        {steps.map((t, i) => (
          <View key={t} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <View style={[st.dot, { backgroundColor: i < at ? '#15171A' : i === at ? '#E5E3E8' : '#F5F6F8' }]}>{i < at ? Ico.check() : i === at ? Ico.check('#15171A') : null}</View>
            <Text style={[st.stT, i <= at && { color: '#15171A' }, i === at && { fontWeight: '700' }]}>{t}</Text>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

/** 웹 만들기 실패 = 원본 studio.tsx Fail(FailLike) */
export function WebFail({ kind, onHome, onRetry }: { kind: 'audio' | 'report'; onHome: () => void; onRetry: () => void }) {
  return (
    <ScrollView contentContainerStyle={st.center}>
      <View style={st.big}>{Ico.alert()}</View>
      <View style={{ alignItems: 'center', gap: 6, alignSelf: 'stretch' }}>
        <Text style={st.h}>{kind === 'report' ? '주간보고서를 만들지 못했어요' : '오디오를 만들지 못했어요'}</Text>
        <Text style={st.sub}>잠시 후 다시 시도해 주세요.</Text>
      </View>
      <View style={{ flexDirection: 'row', gap: 8, alignSelf: 'stretch' }}>
        <GBtn flex onPress={onHome}>스튜디오로</GBtn>
        <GBtn flex dark onPress={onRetry}>다시 시도</GBtn>
      </View>
      <Text style={[st.note, { textAlign: 'center' }]}>크레딧 사용 내역은 설정 › 사용량에서 볼 수 있어요.</Text>
    </ScrollView>
  );
}

/** 진행자 얼굴 (원본 Face) */
function Face({ dark }: { dark?: boolean }) {
  const f = dark ? 'white' : '#15171A';
  return (
    <Svg width={36} height={36} viewBox="0 0 36 36" fill="none">
      <Path d="M12.6 18.18C13.69 18.18 14.58 17.29 14.58 16.2C14.58 15.11 13.69 14.22 12.6 14.22C11.51 14.22 10.62 15.11 10.62 16.2C10.62 17.29 11.51 18.18 12.6 18.18Z" fill={f} />
      <Path d="M23.4 18.18C24.49 18.18 25.38 17.29 25.38 16.2C25.38 15.11 24.49 14.22 23.4 14.22C22.31 14.22 21.42 15.11 21.42 16.2C21.42 17.29 22.31 18.18 23.4 18.18Z" fill={f} />
      {dark ? <Path d="M18 25.56C19.19 25.56 20.16 24.59 20.16 23.4C20.16 22.21 19.19 21.24 18 21.24C16.81 21.24 15.84 22.21 15.84 23.4C15.84 24.59 16.81 25.56 18 25.56Z" fill="white" /> : <Path d="M12.6 22.5C16.2 25.5 19.8 25.5 23.4 22.5" stroke="#15171A" strokeWidth={1.98} strokeLinecap="round" />}
    </Svg>
  );
}

/**
 * 웹 오디오 플레이어 = 원본 studio.tsx Player (스튜디오 열 안 · 안쪽 16 · 사이 12)
 * ‹ 스튜디오 · 회색 카드(진행자 56 · 제목 22 · 진행 막대 6(누르면 그 위치) · 시간 · −10 · 재생 56 · +10 · 속도) ·
 * 챕터 · 대본(지금 줄 앞뒤 4줄) · 들은 소식의 출처 · 연결된 메모 · [조건 바꿔 새로 만들기]
 */
export function WebPlayer({ item, ep, t, playing, speed, onBack, onToggle, onSeek, onSpeed, onRemake }: {
  item: MadeItem; ep: Ep; t: number; playing: boolean; speed: number;
  onBack: () => void; onToggle: () => void; onSeek: (t: number) => void; onSpeed: () => void; onRemake: () => void;
}) {
  const [w, setW] = useState(1);
  const [full, setFull] = useState(false);
  const fullRef = useRef<ScrollViewInstance>(null);
  const lineY = useRef<number[]>([]);
  const ci = chapterAt(t, ep);
  const cur = lineAt(t, ep);
  const talking = playing ? ep.script[cur][1] : null;
  /* 전체 보기로 듣는 중이면 지금 줄이 상자 위쪽에 오게 따라간다 (멈춰 있을 때는 사용자가 스크롤한 그대로) */
  useEffect(() => {
    if (!full || !playing) return;
    const y = lineY.current[cur];
    if (y !== undefined) fullRef.current?.scrollTo({ y: Math.max(0, y - 80), animated: true });
  }, [cur, full, playing]);
  return (
    <ScrollView contentContainerStyle={st.box} showsVerticalScrollIndicator={false}>
      <Pressable onPress={onBack} accessibilityRole="button" style={st.backL}>{Ico.back()}<Text style={st.backT}>스튜디오</Text></Pressable>
      <View style={st.card}>
        <View style={{ flexDirection: 'row', gap: 28 }}>
          {(['A', 'B'] as const).map((h, i) => (
            <View key={h} style={{ alignItems: 'center', gap: 6 }}>
              <View style={[st.face, h === 'A' ? { borderWidth: 2.5, borderColor: '#15171A', backgroundColor: '#FFFFFF' } : { borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#15171A' }, talking === h && { transform: [{ scale: 1.06 }] }]}><Face dark={h === 'B'} /></View>
              <Text style={st.host}>{ep.hosts[i]}</Text>
            </View>
          ))}
        </View>
        <View style={{ alignItems: 'center', gap: 2, alignSelf: 'stretch' }}>
          <Text style={st.h}>{item.title}</Text>
          <Text style={[st.note, { textAlign: 'center' }]}>{item.meta}</Text>
        </View>
        <Pressable onLayout={(e) => setW(e.nativeEvent.layout.width)} onPress={(e) => onSeek((e.nativeEvent.locationX / w) * ep.dur)} accessibilityRole="adjustable" accessibilityLabel="재생 위치" style={st.seek}>
          <View style={[st.seekI, { width: `${(t / ep.dur) * 100}%` }]} />
        </Pressable>
        <View style={st.times}>
          {[fmt(t), `지금 · ${ep.chapters[ci][1]}`, fmt(ep.dur)].map((x, i) => <Text key={i} style={st.time}>{x}</Text>)}
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 18 }}>
          <Pressable onPress={() => onSeek(t - 10)} accessibilityRole="button" accessibilityLabel="10초 뒤로"><Text style={st.jump}>-10</Text></Pressable>
          <Pressable onPress={onToggle} accessibilityRole="button" accessibilityLabel={playing ? '일시정지' : '재생'} style={st.play}>{playing ? Ico.pause() : Ico.play(22)}</Pressable>
          <Pressable onPress={() => onSeek(t + 10)} accessibilityRole="button" accessibilityLabel="10초 앞으로"><Text style={st.jump}>+10</Text></Pressable>
          <Pressable onPress={onSpeed} accessibilityRole="button" accessibilityLabel="재생 속도" style={st.spd}><Text style={st.spdT}>{speed.toFixed(1)}x</Text></Pressable>
        </View>
      </View>
      <Text style={st.lbl}>챕터</Text>
      <View style={{ gap: 2 }}>
        {ep.chapters.map(([c0, name], i) => (
          <Pressable key={`${i}-${name}`} onPress={() => onSeek(c0)} accessibilityRole="button" style={({ hovered }: Hover) => [st.ch, i === ci ? { backgroundColor: '#F5F6F8' } : hovered && { backgroundColor: '#F9F9F9' }]}>
            <Text style={st.chN}>{String(i + 1).padStart(2, '0')}</Text>
            <Text style={[st.chT, i === ci && { fontWeight: '700' }]}>{name}</Text>
            <Text style={st.chN}>{fmt(c0)}</Text>
          </Pressable>
        ))}
      </View>
      <View style={st.lblRow}>
        <Text style={st.lbl}>대본</Text>
        <Pressable onPress={() => setFull(!full)} accessibilityRole="button" accessibilityState={{ expanded: full }} style={({ hovered }: Hover) => [st.more, hovered && { backgroundColor: '#F5F6F8' }]}>
          <Text style={st.moreT}>{full ? '접기' : `전체 보기 · ${ep.script.length}줄`}</Text>
        </Pressable>
      </View>
      {full ? (
        /* 전체 대본 (2026-11-24): 상자 안에서 따로 스크롤 · 줄을 누르면 그 부분부터 · 재생 중에는 지금 줄을 따라간다 */
        <ScrollView ref={fullRef} style={st.full} contentContainerStyle={{ gap: 4, padding: 8 }} nestedScrollEnabled showsVerticalScrollIndicator>
          {ep.script.map(([s0, who, text], i) => (
            <Pressable key={i} onLayout={(e) => { lineY.current[i] = e.nativeEvent.layout.y; }} onPress={() => { onSeek(s0); if (!playing) onToggle(); }}
              accessibilityRole="button" accessibilityLabel={`${fmt(s0)}부터 듣기`}
              style={({ hovered }: Hover) => [st.fullLn, i === cur ? { backgroundColor: '#F5F6F8' } : hovered && { backgroundColor: '#F9F9F9' }]}>
              <View style={[st.who, who === 'A' ? { borderWidth: 1, borderColor: '#15171A', backgroundColor: '#FFFFFF' } : { backgroundColor: '#15171A' }]}><Text style={[st.whoT, who === 'B' && { color: '#FFFFFF' }]}>{who}</Text></View>
              <Text keepAll style={[st.line, i === cur ? { fontWeight: '500', color: '#15171A' } : { color: i < cur ? '#575B63' : '#8E8A97' }]}>{text}</Text>
              <Text style={st.fullT}>{fmt(s0)}</Text>
            </Pressable>
          ))}
        </ScrollView>
      ) : (
        <View style={{ gap: 12 }}>
          {ep.script.map(([, who, text], i) => (i >= cur - 1 && i <= cur + 2 ? (
            <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10 }}>
              <View style={[st.who, who === 'A' ? { borderWidth: 1, borderColor: '#15171A', backgroundColor: '#FFFFFF' } : { backgroundColor: '#15171A' }]}><Text style={[st.whoT, who === 'B' && { color: '#FFFFFF' }]}>{who}</Text></View>
              <Text keepAll style={[st.line, i === cur ? { fontWeight: '500', color: '#15171A' } : { color: '#8E8A97' }]}>{text}</Text>
            </View>
          ) : null))}
        </View>
      )}
      <View style={st.src}>
        <Text style={st.lbl}>들은 소식의 출처 · 연결된 메모</Text>
        {[...(ep.market_source ? [{ kind: '시장', text: ep.market_source, memo: '' }] : []), ...ep.sources].map((r, i) => (
          <View key={`${i}-${r.text}`} style={{ gap: 2 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <View style={st.chipS}><Text style={st.chipST}>{r.kind}</Text></View>
              <Text style={st.srcT}>{r.text}</Text>
            </View>
            {r.memo ? <Text style={st.srcM}>{r.memo}</Text> : null}
          </View>
        ))}
      </View>
      <GBtn onPress={onRemake}>조건 바꿔 새로 만들기</GBtn>
    </ScrollView>
  );
}

/** 웹 미니 플레이어 = 원본 studio.tsx Mini (스튜디오 열 카드 안 아래 12 · 검정 · 라운드 18) */
export function WebMini({ title, sub, progress, playing, onOpen, onToggle, onClose }: { title: string; sub: string; progress: number; playing: boolean; onOpen: () => void; onToggle: () => void; onClose: () => void }) {
  return (
    <View style={[st.mini, miniEnter]}>
      <Pressable onPress={onToggle} accessibilityRole="button" accessibilityLabel={playing ? '일시정지' : '재생'} style={st.miniP}>{playing ? Ico.pause(16, '#15171A') : Ico.play(16, '#15171A')}</Pressable>
      <Pressable onPress={onOpen} accessibilityRole="button" style={{ flex: 1, minWidth: 0, gap: 1 }}>
        <Text style={st.miniT} numberOfLines={1}>{title}</Text>
        <Text style={st.miniS} numberOfLines={1}>{sub}</Text>
      </Pressable>
      <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="닫기" style={{ width: 18, height: 18, flexShrink: 0 }}>
        <Svg width={18} height={18} viewBox="0 0 18 18" fill="none"><Path d="M4.5 4.5L13.5 13.5M13.5 4.5L4.5 13.5" stroke="white" strokeWidth={1.5} strokeLinecap="round" /></Svg>
      </Pressable>
      <View pointerEvents="none" style={[st.miniL, { width: `${Math.min(100, progress * 100)}%` }]} />
    </View>
  );
}

/* 원본 motion.css .st-mini: 아래에서 위로 등장 (--t-slow .45s · --spring · 동작 줄이기 설정이면 ×.01) */
const miniEnter = {
  animationKeyframes: { from: { transform: [{ translateY: '120%' }] } },
  animationDuration: globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? '4.5ms' : '450ms',
  animationTimingFunction: 'cubic-bezier(.34, 1.45, .64, 1)',
  animationFillMode: 'both',
} as unknown as ViewStyle;

const st = StyleSheet.create({
  center: { alignItems: 'center', gap: 18, paddingHorizontal: 16, paddingBottom: 18, paddingTop: 120 },
  big: { width: 72, height: 72, borderRadius: 22, backgroundColor: '#F5F6F8', alignItems: 'center', justifyContent: 'center' },
  h: { textAlign: 'center', fontSize: 22, lineHeight: 33, fontWeight: '700', letterSpacing: -0.4, color: '#15171A' },
  sub: { textAlign: 'center', fontSize: 15, lineHeight: 23, color: '#8E8A97', ...TR },
  bar: { width: 200, height: 6, borderRadius: 3, backgroundColor: '#F5F6F8', overflow: 'hidden' },
  barI: { height: 6, borderRadius: 3, backgroundColor: '#15171A' },
  dot: { width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  stT: { fontSize: 15, lineHeight: 18, color: '#8E8A97', ...TR },
  note: { fontSize: 14, lineHeight: 21, color: '#8E8A97', ...TR },
  box: { gap: 12, paddingHorizontal: 16, paddingBottom: 18, paddingTop: 6 },
  backL: { flexDirection: 'row', alignItems: 'center', gap: 2, alignSelf: 'flex-start', paddingRight: 8 },
  backT: { fontSize: 15, lineHeight: 18, fontWeight: '700', color: '#404752', ...TR },
  card: { alignItems: 'center', gap: 14, borderRadius: 20, backgroundColor: '#F5F6F8', padding: 18 },
  face: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center' },
  host: { fontSize: 14, lineHeight: 17, fontWeight: '700', color: '#404752', ...TR },
  seek: { alignSelf: 'stretch', height: 6, borderRadius: 3, backgroundColor: '#E5E3E8', overflow: 'hidden' },
  seekI: { height: 6, borderRadius: 3, backgroundColor: '#15171A' },
  times: { alignSelf: 'stretch', flexDirection: 'row', justifyContent: 'space-between' },
  time: { fontSize: 14, lineHeight: 21, fontWeight: '700', color: '#404752', ...TR },
  jump: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: '#404752', ...TR },
  play: { width: 56, height: 56, borderRadius: 28, backgroundColor: '#15171A', alignItems: 'center', justifyContent: 'center' },
  spd: { height: 28, borderRadius: 999, backgroundColor: '#FFFFFF', paddingHorizontal: 10, justifyContent: 'center' },
  spdT: { fontSize: 14, lineHeight: 17, fontWeight: '700', color: '#404752' },
  lbl: { fontSize: 14, lineHeight: 21, fontWeight: '700', color: '#8E8A97', ...TR },
  ch: { flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 12, padding: 12 },
  chN: { fontSize: 14, lineHeight: 17, color: '#8E8A97', ...TR },
  chT: { flex: 1, minWidth: 0, fontSize: 15, lineHeight: 18, color: '#15171A', ...TR },
  who: { width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  whoT: { fontSize: 13, lineHeight: 16, fontWeight: '700', color: '#15171A' },
  line: { flex: 1, minWidth: 0, fontSize: 15, lineHeight: 23, ...TR },
  src: { gap: 10, borderRadius: 18, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', padding: 16 },
  chip: { height: 24, borderRadius: 999, paddingHorizontal: 9, justifyContent: 'center', backgroundColor: '#F5F6F8' },
  chipT: { fontSize: 13, lineHeight: 16, fontWeight: '700', color: '#404752' },
  /* 출처·연결된 메모 (2026-11-24: 15 → 13, 메모 줄 14 → 12, 굵게 뺌 · 칩은 공시·뉴스·업데이트 모두 같은 회색) */
  srcT: { flex: 1, minWidth: 0, fontSize: 13, lineHeight: 19, fontWeight: '400', color: '#15171A', ...TR },
  srcM: { fontSize: 12, lineHeight: 17, color: '#8E8A97', ...TR },
  chipS: { height: 20, borderRadius: 999, paddingHorizontal: 7, justifyContent: 'center', backgroundColor: '#F5F6F8' },
  chipST: { fontSize: 11, lineHeight: 14, fontWeight: '700', color: '#404752' },
  lblRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  more: { height: 28, borderRadius: 999, paddingHorizontal: 10, justifyContent: 'center' },
  moreT: { fontSize: 13, lineHeight: 16, fontWeight: '700', color: '#404752', ...TR },
  full: { maxHeight: 380, borderRadius: 16, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF' },
  fullLn: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 8 },
  fullT: { fontSize: 12, lineHeight: 23, color: '#B8BFC8', ...TR },
  mini: { position: 'absolute', left: 12, right: 12, bottom: 12, zIndex: 20, flexDirection: 'row', alignItems: 'center', gap: 10, overflow: 'hidden', borderRadius: 18, backgroundColor: '#15171A', paddingVertical: 10, paddingLeft: 10, paddingRight: 8 },
  miniP: { width: 40, height: 40, flexShrink: 0, borderRadius: 20, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  miniT: { fontSize: 15, lineHeight: 19.5, fontWeight: '700', color: '#FFFFFF', ...TR },
  miniS: { fontSize: 14, lineHeight: 18.2, color: '#B8BFC8', ...TR },
  miniL: { position: 'absolute', left: 0, bottom: 0, height: 3, backgroundColor: '#8E8A97' },
});
