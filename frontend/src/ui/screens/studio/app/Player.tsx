import React, { useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View, type ScrollViewInstance } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { nf } from '@/ui/shared/app/nf';
import { Text } from '@/components/ui/AppText';
import { PressScale } from '@/ui/motion/PressScale';
import { chapterAt, fmt, lineAt } from '@/store/studioPlayer';
import { Head } from '../../my/app/parts';
import type { MadeItem } from '../Studio.types';
import { AUDIO_OFF_BG, audioOff } from '../appAudio';
import type { AudioEp } from '../audioEp';

/**
 * 앱 오디오 플레이어 = 원본 studio.html #pgPl (09)
 * 검정 카드(진행자 A·B · 제목 20 · 진행 막대(누르기·끌기) · 시간/지금 챕터 · 속도 · −10 · 재생 64 · +10) ·
 * 종목별 챕터 · 대본(줄 누르면 그 부분부터) · 관련 업데이트·출처 · 내 메모와 연결 · [조건 바꿔 새로 만들기]
 * 앱은 아직 소리를 내지 않음 (재생 모듈 없음 → store/studioPlayer 타이머). 서버 오디오면 그 편의 대본·챕터를 보여 준다
 */
type Ep = AudioEp;
const C = { a: '#8569E3', a2: '#6A42AB', ink: '#16171A', ink2: '#575B63', ink3: '#9A9EA7' };
export const SPEEDS = [1, 1.25, 1.5, 2];

export function AppPlayer({ item, ep, t, playing, speed, onBack, onToggle, onSeek, onSpeed, onOpenMemo, onRemake }: {
  item: MadeItem; ep: Ep; t: number; playing: boolean; speed: number;
  onBack: () => void; onToggle: () => void; onSeek: (t: number) => void; onSpeed: () => void; onOpenMemo: () => void; onRemake: () => void;
}) {
  const insets = useSafeAreaInsets();
  const sc = useRef<ScrollViewInstance>(null);
  const ci = chapterAt(t, ep);
  const li = lineAt(t, ep);
  const ml = ep.memo_link;
  const talk = playing ? ep.script[li][1] : null;
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Head title="AI 오디오" onBack={onBack} />
      <ScrollView ref={sc} contentContainerStyle={{ paddingBottom: 24 + insets.bottom }} showsVerticalScrollIndicator={false}>
        <View style={st.pc}>
          <View style={st.hosts}>
            <View style={[st.av2, talk === 'A' && st.talk]}><Text style={st.av2T}>A</Text></View>
            <Text style={st.hostT}>{ep.hosts[0]}</Text>
            <View style={[st.av2, { backgroundColor: C.a, marginLeft: 8 }, talk === 'B' && st.talk]}><Text style={[st.av2T, { color: '#FFFFFF' }]}>B</Text></View>
            <Text style={st.hostT}>{ep.hosts[1]}</Text>
          </View>
          <Text style={st.pcH}>{item.title}</Text>
          <Text style={st.ps}>{item.foot ?? item.sub}</Text>
          <Track k={t / ep.dur} onSeek={(r) => onSeek(r * ep.dur)} />
          <View style={st.tm}>
            <Text style={st.tmT}>{fmt(t)}</Text>
            <View style={st.now}><Text style={st.nowT}>지금 · {ep.chapters[ci][1].split(' ·')[0]}</Text></View>
            <Text style={st.tmT}>{fmt(ep.dur)}</Text>
          </View>
          <View style={st.ctl}>
            <PressScale scaleTo={0.88} onPress={onSpeed} accessibilityRole="button" accessibilityLabel={`재생 속도 ${speed}배`} style={st.sm}><Text style={st.ctlT}>{speed % 1 ? speed : speed.toFixed(1)}x</Text></PressScale>
            <PressScale scaleTo={0.88} onPress={() => onSeek(t - 10)} accessibilityRole="button" accessibilityLabel="10초 뒤로" style={st.rw}><Text style={st.ctlT}>−10</Text></PressScale>
            <PressScale scaleTo={0.88} onPress={onToggle} accessibilityRole="button" accessibilityLabel={playing ? '일시정지' : '재생'} accessibilityState={{ disabled: audioOff }} style={[st.big, audioOff && { backgroundColor: AUDIO_OFF_BG }]}>
              <Svg width={26} height={26} viewBox="0 0 26 26"><Path d={playing ? 'M6 4 L6 22 L11 22 L11 4 Z M15 4 L15 22 L20 22 L20 4 Z' : 'M7 4 L7 22 L13 18.5 L13 7.5 Z M13 7.5 L13 18.5 L22 13 L22 13 Z'} fill={audioOff ? '#FFFFFF' : C.ink} /></Svg>
            </PressScale>
            <PressScale scaleTo={0.88} onPress={() => onSeek(t + 10)} accessibilityRole="button" accessibilityLabel="10초 앞으로" style={st.rw}><Text style={st.ctlT}>+10</Text></PressScale>
            <View style={{ width: 46 }} />
          </View>
        </View>
        <Sec t="종목별 챕터" s="누르면 그 위치로" />
        <View style={st.card}>
          {ep.chapters.map(([c0, name], i) => (
            <Pressable key={`${i}-${name}`} onPress={() => onSeek(c0)} accessibilityRole="button" style={[st.cr, i > 0 && st.line]}>
              <Text style={st.crT}>{fmt(c0)}</Text>
              <Text style={[st.crN, i === ci && { color: C.a2, fontWeight: '800' }]}>{name}</Text>
              {i === ci ? <Svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke={C.a2} strokeWidth={2} strokeLinecap="round" style={{ marginLeft: 'auto' }}><Path d="M4 10v4h4l5 4V6L8 10z" /><Path d="M16 9a4 4 0 0 1 0 6" /></Svg> : null}
            </Pressable>
          ))}
        </View>
        <Sec t="대본" s="줄을 누르면 그 부분부터 들어요" />
        <View style={[st.card, { padding: 8 }]}>
          {ep.script.map(([s0, who, text], i) => {
            const on = i === li;
            const past = i < li;
            return (
              <Pressable key={i} onPress={() => { onSeek(s0); if (!playing) onToggle(); }} accessibilityRole="button" style={({ pressed }) => [st.ln, on && { backgroundColor: '#F1ECFF' }, pressed && !on && { backgroundColor: '#F6F4FF' }]}>
                <View style={st.tl}>
                  <View style={[st.rail, i === 0 && { top: 18 }, i === ep.script.length - 1 && { height: 18, bottom: undefined }]} />
                  <View style={[st.tc, on && { backgroundColor: C.a2, borderColor: C.a2 }]}><Text style={[st.tcT, on && { color: '#FFFFFF' }]}>{fmt(s0)}</Text></View>
                  <View style={[st.dot, past && { backgroundColor: C.ink3 }, on && { backgroundColor: C.a, transform: [{ scale: 1.3 }] }]} />
                </View>
                <View style={{ flex: 1, paddingVertical: 10 }}>
                  <Text style={[st.lnB, { color: on ? C.ink : past ? C.ink2 : C.ink3 }]}>{who} · {who === 'A' ? '메인' : '해설'}</Text>
                  <Text keepAll style={[st.lnT, { color: on ? C.ink : past ? C.ink2 : C.ink3 }]}>{text}</Text>
                </View>
              </Pressable>
            );
          })}
        </View>
        <Sec t="관련 업데이트 · 출처" />
        <View style={st.card}>
          {[...(ep.market_source ? [{ kind: '시장', text: ep.market_source, memo: '' }] : []), ...ep.sources].map((r, i) => (
            <View key={`${i}-${r.text}`} style={[st.rr, i > 0 && st.line]}>
              <View style={[st.tg, r.kind === '뉴스' && { backgroundColor: '#E8F0FF' }]}><Text style={[st.tgT, r.kind === '뉴스' && { color: '#2F6BDB' }]}>{r.kind}</Text></View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={st.rrT} numberOfLines={1}>{r.text}</Text>
                {r.memo ? <Text style={st.rrM} numberOfLines={1}>{r.memo}</Text> : null}
              </View>
            </View>
          ))}
        </View>
        {ml ? (
          <>
            <Sec t="내 메모와 연결" s="이 오디오에서 다룬 메모 1개" />
            <View style={st.mlink}>
              <View style={st.ymemo}><Text style={st.ymH}>{ml.head}</Text><Text style={st.ymB}>{ml.title}</Text></View>
              <Text keepAll style={st.mlP}>{ml.body}</Text>
              <View style={{ flexDirection: 'row', gap: 6 }}>
                <Pressable onPress={() => { onSeek(ml.seek); if (!playing) onToggle(); sc.current?.scrollTo({ y: 0, animated: true }); }} accessibilityRole="button" style={st.chip}><Text style={st.chipT}>▶ {fmt(ml.seek)} 부분 듣기</Text></Pressable>
                <View style={[st.chip, { backgroundColor: '#F2F2F5' }]}><Text style={[st.chipT, { color: C.ink2 }]}>{ml.count}</Text></View>
              </View>
              <Pressable onPress={onOpenMemo} accessibilityRole="link" style={{ marginTop: 8 }}><Text style={st.lk}>원본 메모 보기 ›</Text></Pressable>
            </View>
          </>
        ) : null}
        <View style={{ paddingTop: 6, paddingHorizontal: 16 }}>
          <PressScale onPress={onRemake} accessibilityRole="button" style={st.cta}><Text style={st.ctaT}>조건 바꿔 새로 만들기</Text></PressScale>
        </View>
      </ScrollView>
    </View>
  );
}

function Sec({ t, s }: { t: string; s?: string }) {
  return <View style={st.secr}><Text style={st.secrT}>{t}</Text>{s ? <Text style={st.secrS}>{s}</Text> : null}</View>;
}

/* .trk: 22 높이 · 막대 4 · 손잡이 14 (끄는 동안 1.4배) */
function Track({ k, onSeek }: { k: number; onSeek: (r: number) => void }) {
  const [drag, setDrag] = useState(false);
  const [w, setW] = useState(1);
  const at = (x: number) => onSeek(Math.max(0, Math.min(1, x / w)));
  const p = `${Math.min(100, k * 100)}%` as const;
  return (
    <View
      style={st.trk}
      onLayout={(e) => setW(e.nativeEvent.layout.width)}
      onStartShouldSetResponder={() => true}
      onMoveShouldSetResponder={() => true}
      onResponderTerminationRequest={() => false}
      onResponderGrant={(e) => { setDrag(true); at(e.nativeEvent.locationX); }}
      onResponderMove={(e) => at(e.nativeEvent.locationX)}
      onResponderRelease={() => setDrag(false)}
      onResponderTerminate={() => setDrag(false)}
      accessibilityRole="adjustable"
      accessibilityLabel="재생 위치"
    >
      <View pointerEvents="none" style={st.trkBg} />
      <View pointerEvents="none" style={[st.trkFg, { width: p }]} />
      <View pointerEvents="none" style={[st.kn, { left: p }, drag && { transform: [{ scale: 1.4 }] }]} />
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F3F4F6' },
  pc: { backgroundColor: C.ink, borderRadius: 22, marginHorizontal: 16, padding: 16 },
  hosts: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  av2: { width: 26, height: 26, borderRadius: 13, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center', marginRight: -2 },
  talk: { transform: [{ scale: 1.12 }] },
  av2T: { ...nf(12), fontWeight: '800', color: C.ink },
  hostT: { ...nf(12), color: '#C9CCD2' },
  pcH: { ...nf(20), fontWeight: '700', color: '#FFFFFF', marginTop: 10, marginBottom: 2 },
  ps: { ...nf(12), color: '#9EA2AA' },
  trk: { height: 22, marginTop: 12, justifyContent: 'center' },
  trkBg: { position: 'absolute', left: 0, right: 0, top: 9, height: 4, borderRadius: 2, backgroundColor: '#3A3C42' },
  trkFg: { position: 'absolute', left: 0, top: 9, height: 4, borderRadius: 2, backgroundColor: '#FFFFFF' },
  kn: { position: 'absolute', top: 4, width: 14, height: 14, marginLeft: -7, borderRadius: 7, backgroundColor: '#FFFFFF' },
  tm: { flexDirection: 'row', alignItems: 'center' },
  tmT: { ...nf(11.5), color: '#9EA2AA' },
  now: { marginHorizontal: 'auto', backgroundColor: '#2B2D33', borderRadius: 10, paddingHorizontal: 9, paddingVertical: 2 },
  nowT: { ...nf(11.5), fontWeight: '600', color: '#FFFFFF' },
  ctl: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12 },
  sm: { width: 46, height: 34, borderRadius: 17, backgroundColor: '#2B2D33', alignItems: 'center', justifyContent: 'center' },
  rw: { width: 46, height: 46, borderRadius: 23, backgroundColor: '#2B2D33', alignItems: 'center', justifyContent: 'center' },
  ctlT: { ...nf(13), fontWeight: '800', color: '#FFFFFF' },
  big: { width: 64, height: 64, borderRadius: 32, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  secr: { flexDirection: 'row', alignItems: 'baseline', gap: 8, paddingTop: 12, paddingHorizontal: 18, paddingBottom: 8 },
  secrT: { ...nf(15), fontWeight: '800', color: C.ink },
  secrS: { ...nf(12), fontWeight: '500', color: C.ink3 },
  card: { backgroundColor: '#FFFFFF', borderRadius: 20, marginHorizontal: 16, paddingVertical: 6, paddingHorizontal: 16 },
  line: { borderTopWidth: 1, borderTopColor: '#F0F1F4' },
  cr: { flexDirection: 'row', alignItems: 'center', gap: 12, height: 48 },
  crT: { width: 34, ...nf(12), color: C.ink3 },
  crN: { ...nf(14.5), color: C.ink },
  ln: { flexDirection: 'row', gap: 8, paddingRight: 10, paddingLeft: 4, borderRadius: 14 },
  tl: { width: 46, alignItems: 'center', paddingTop: 10 },
  rail: { position: 'absolute', top: 0, bottom: 0, left: 22, width: 2, backgroundColor: '#ECEDF1' },
  tc: { backgroundColor: '#FFFFFF', borderRadius: 8, paddingHorizontal: 6, paddingVertical: 1, borderWidth: 1, borderColor: '#E2E4E8' },
  tcT: { fontSize: 11, lineHeight: 18.15, fontWeight: '700', color: C.ink3 },
  dot: { width: 9, height: 9, borderRadius: 5, backgroundColor: '#D5D8DD', marginTop: 6 },
  lnB: { fontSize: 12, lineHeight: 19.8, fontWeight: '700' },
  lnT: { fontSize: 13.5, lineHeight: 22 },
  rr: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 46, paddingVertical: 8 },
  tg: { borderRadius: 7, paddingHorizontal: 7, paddingVertical: 3, backgroundColor: '#F0ECFF' },
  tgT: { fontSize: 11.5, lineHeight: 15, fontWeight: '700', color: '#5B3BD1' },
  rrM: { ...nf(12), color: C.ink3 },
  rrT: { ...nf(13.5), color: C.ink },
  mlink: { backgroundColor: '#FFFFFF', borderRadius: 20, marginHorizontal: 16, marginBottom: 10, paddingVertical: 14, paddingHorizontal: 16 },
  ymemo: { backgroundColor: '#FFF1BF', borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12 },
  ymH: { ...nf(12), color: '#8A6A00' },
  ymB: { ...nf(15), fontWeight: '700', color: '#3D2F00', marginTop: 2 },
  mlP: { fontSize: 13, lineHeight: 21, color: C.ink2, marginTop: 10, marginBottom: 8 },
  chip: { height: 26, paddingHorizontal: 10, borderRadius: 13, backgroundColor: '#F0ECFF', justifyContent: 'center' },
  chipT: { ...nf(12), fontWeight: '700', color: '#5B3BD1' },
  lk: { ...nf(13), fontWeight: '700', color: C.a2 },
  cta: { height: 54, borderRadius: 15, backgroundColor: '#ECEDF1', alignItems: 'center', justifyContent: 'center' },
  ctaT: { ...nf(16), fontWeight: '800', color: C.ink },
});
