import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { TabFrame, TabScroll } from '@/ui/layout/app/TabFrame';
import { nf } from '@/ui/shared/app/nf';
import { Text } from '@/components/ui/AppText';
import { PressScale } from '@/ui/motion/PressScale';
import { Reveal } from '@/ui/motion/Reveal';
import { useCoachRef } from '@/ui/shared/Coach';
import { Sheet } from '@/ui/shared/Sheet';
import { SpentBox } from '@/ui/shared/SpentBox';
import type { MadeItem, StudioHomeProps, StudioKind } from '../Studio.types';
import { GEN_LATE, type AppGenJob } from '@/store/genJobs';
import { Spin } from './Spin';
import { AUDIO_OFF_BG, audioOff } from '../appAudio';
import { useRemoveMade } from '../studioItems';

/**
 * 앱 스튜디오 홈 = 원본 app/studio.html #vst (11.17 웹 통일 순서: 오디오 · 주간보고서 · 실험실 · 퀴즈)
 * 머리 아래 줄(12.5 ink3 · 오른쪽 AI 사용량 칩 28) · 기능 카드(라운드 20 · 16 · 아이콘 50/15) ·
 * '만든 항목' + 30일 보관 · 라디오 카드(mfeat) · 목록(라운드 20) · 아래 안내 12
 * 사용량 칩 → 시트(사용량 막대 · 크레딧 구매 · 플랜 변경)
 */
const C = { a: '#8569E3', a2: '#6A42AB', ink: '#16171A', ink2: '#575B63', ink3: '#9A9EA7', bg: '#F3F4F6' };
export const FEAT_COLOR: Record<StudioKind, { bg: string; c: string }> = {
  audio: { bg: '#DCE7FF', c: '#3D73F0' },
  report: { bg: '#FFE1E1', c: '#E5484D' },
  lab: { bg: '#FFEDB8', c: '#B07800' },
  quiz: { bg: '#D9F2E2', c: '#1F8A4C' },
};

export function FeatIcon({ k, size = 50 }: { k: StudioKind; size?: number }) {
  const { bg, c } = FEAT_COLOR[k];
  const s = size * 0.46;
  const p = { stroke: c, strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, fill: 'none' };
  return (
    <View style={{ width: size, height: size, borderRadius: size === 50 ? 15 : 12, backgroundColor: bg, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={s} height={s} viewBox="0 0 24 24" fill="none">
        {k === 'audio' ? <Path d="M4 10V14M8 7V17M12 4V20M16 8V16M20 11V13" {...p} />
          : k === 'report' ? <><Path d="M7 3H14L19 8V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" {...p} /><Path d="M14 3V8H19" {...p} /><Path d="M9.5 17V15M12.5 17V13M15.5 17V14" {...p} /></>
          : k === 'lab' ? <><Path d="M9 3H15M10 3V9L5 18.5A1.7 1.7 0 0 0 6.5 21H17.5A1.7 1.7 0 0 0 19 18.5L14 9V3" {...p} /><Path d="M7.5 15H16.5" {...p} /></>
          : <><Circle cx={12} cy={12} r={9} {...p} /><Path d="M9.6 9.3a2.4 2.4 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.6" {...p} /><Path d="M12 17.2h.01" {...p} strokeWidth={2.4} /></>}
      </Svg>
    </View>
  );
}

const Chev = ({ c = '#B7BBC3' }: { c?: string }) => <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"><Path d="M9 5l7 7-7 7" /></Svg>;
const Bolt = ({ c, s = 11 }: { c: string; s?: number }) => <Svg width={s} height={s * 13 / 11} viewBox="0 0 11 13"><Path d="M6.5 0 0 7.5h4.5L3.5 13 11 4.8H6.3z" fill={c} /></Svg>;
const WAVE = [8, 14, 10, 18, 12, 20, 9, 16, 22, 13, 17, 10, 19, 12, 8, 15, 11, 18, 9, 14, 12, 7];

export function AppStudioHome({ header, jobs, onJob, playingId, onQuickPlay, spent = false, ...p }: StudioHomeProps & {
  header: React.ReactNode;
  /** 만드는 중 · 실패 줄 (원본 madeRow prog / fail) */
  jobs: AppGenJob[];
  /** 지금 재생 중인 오디오 · 플레이어를 열지 않고 바로 재생 */
  playingId: string | null;
  onQuickPlay: (m: MadeItem) => void;
  onJob?: (id: string) => void;
  /** 미니 플레이어가 떠 있으면 스크롤 끝 빈 자리 (원본 .withmini) */
  bottomPad?: number;
  /** AI 사용량 정지 (usage_pct 100 이상과 같게) */
  spent?: boolean;
}) {
  const remove = useRemoveMade();
  const [sheet, setSheet] = useState(false);
  const featRef = useCoachRef('studio');
  const full = spent || p.usage_pct >= 100;
  const top = p.made.find((m) => m.kind === 'audio');
  const rest = p.made.filter((m) => m !== top);
  return (
    <TabFrame style={st.root}>
      {header}
      <TabScroll contentContainerStyle={{ paddingBottom: 24 }} showsVerticalScrollIndicator={false}>
        <View style={st.subr}>
          <Text style={[st.subrT, { flex: 1 }]}>내 종목 {p.stock_count} · AI 연결 메모 {p.ai_memo_count}</Text>
          <PressScale scaleTo={0.93} onPress={() => setSheet(true)} accessibilityRole="button" accessibilityLabel={`AI 사용량 ${p.usage_pct}%`} style={[st.cred, full && st.credZero]}>
            <Bolt c={full ? '#8A5A00' : '#5B3BD1'} />
            <Text style={[st.credT, full && { color: '#8A5A00' }]}>
              AI 사용량 {p.usage_pct}%
            </Text>
          </PressScale>
        </View>
        {full ? (
          <View style={st.spent}>
            <SpentBox variant="app" title="이번 달 AI 사용량을 다 썼어요" body={`${p.usage_refill}에 새로 채워져요.\n이미 만든 결과와 오늘의 퀴즈는 계속 쓸 수 있어요.`} onCredit={p.onBuyCredit} onPlan={p.onChangePlan} />
          </View>
        ) : null}
        {/* 사용법 안내 ④ 대상 (원본 #feat) */}
        <View ref={featRef} collapsable={false}>
        {p.features.map((f, i) => (
          <Reveal key={f.key} i={i}>
            <PressScale scaleTo={0.975} onPress={() => p.onFeature(f.key)} accessibilityRole="button" accessibilityLabel={f.title} style={st.fc}>
              <FeatIcon k={f.key} />
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={st.fcH}>{f.title}</Text>
                <Text style={st.fcP}>{f.desc}</Text>
              </View>
              <Chev />
            </PressScale>
          </Reveal>
        ))}
        </View>
        <View style={st.secr}><Text style={st.secrT}>만든 항목</Text><Text style={st.secrS}>30일 보관 · 다시 보기 무료</Text></View>
        {top ? <RadioCard m={top} playing={playingId === top.id} onPress={() => p.onOpenMade(top)} onPlay={() => onQuickPlay(top)} onRemove={() => remove(top)} /> : null}
        {rest.length || jobs.length ? (
          <View style={st.made}>
            {jobs.map((job, i) => {
              const title = p.features.find((f) => f.key === job.kind)?.title ?? '';
              return job.status === 'fail' ? (
                <Pressable key={job.id} onPress={() => onJob?.(job.id)} accessibilityRole="button" style={[st.mi, i > 0 && st.miLine]}>
                  <View style={[st.failIc]}><Svg width={17} height={17} viewBox="0 0 24 24" fill="none" stroke="#E5484D" strokeWidth={2} strokeLinecap="round"><Path d="M12 8v5M12 16.5h.01" /><Circle cx={12} cy={12} r={9} /></Svg></View>
                  <View style={{ flex: 1 }}><Text style={st.miB}>{title} · {job.late ? GEN_LATE.title : '만들지 못했어요'}</Text><Text style={st.miS}>{job.late ? GEN_LATE.body : job.sub}</Text></View>
                  <Text style={[st.miR, { color: C.a2, fontWeight: '700' }]}>다시 시도</Text>
                </Pressable>
              ) : (
                <Pressable key={job.id} onPress={() => onJob?.(job.id)} accessibilityRole="button" style={[st.mi, i > 0 && st.miLine]}>
                  <FeatIcon k={job.kind} size={38} />
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={st.miB} numberOfLines={1}>{title} 만드는 중</Text>
                    <Text style={st.miS} numberOfLines={1}>{job.sub}</Text>
                  </View>
                  <View style={st.spin}><Spin /></View>
                </Pressable>
              );
            })}
            {rest.map((m, i) => (
              <View key={m.id} style={[st.mrow, (i > 0 || jobs.length > 0) && st.miLine]}>
                <Pressable onPress={() => p.onOpenMade(m)} accessibilityRole="button" style={[st.mi, st.miMain]}>
                  <FeatIcon k={m.kind} size={38} />
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={st.miB} numberOfLines={1}>{m.title}</Text>
                    <Text style={st.miS} numberOfLines={1}>{m.sub}</Text>
                  </View>
                  <Text style={st.miR}>{m.left}</Text>
                </Pressable>
                <Pressable onPress={() => remove(m)} accessibilityRole="button" accessibilityLabel={`${m.title} 휴지통으로`} hitSlop={10} style={st.del}>
                  <Trash />
                </Pressable>
                {m.kind === 'audio' ? (
                  <Pressable onPress={() => onQuickPlay(m)} accessibilityRole="button" accessibilityLabel={playingId === m.id ? '일시정지' : '바로 재생'} hitSlop={6} accessibilityState={{ disabled: audioOff }} style={[st.qp, audioOff && { backgroundColor: AUDIO_OFF_BG }]}>{playingId === m.id ? <PauseGlyph s={14} /> : <PlayGlyph s={14} />}</Pressable>
                ) : null}
              </View>
            ))}
          </View>
        ) : null}
        {!p.made.length && !jobs.length ? <View style={st.made}><Text style={st.empty}>{'아직 만든 항목이 없어요\n위에서 오디오·보고서·실험을 만들어 보세요'}</Text></View> : null}
        <Text style={st.sdisc}>스튜디오는 투자 권유나 주가 예측을 하지 않아요.</Text>
      </TabScroll>
      <Sheet open={sheet} onClose={() => setSheet(false)} label="AI 사용량">
        <View style={{ paddingHorizontal: 18 }}>
          <Text style={st.shH}>{full ? '이번 달 AI 사용량을 다 썼어요' : 'AI 사용량'}</Text>
          <Text style={st.shD}>이번 달 {p.usage_pct}% 사용 · {p.usage_refill}에 새로 채워져요</Text>
          <View style={st.ubar}><View style={[st.ubarI, { width: `${Math.min(100, p.usage_pct)}%`, backgroundColor: full ? '#E89A0C' : C.a }]} /></View>
          <View style={{ gap: 8, marginTop: 4 }}>
            <Choice bg="#FFF1D6" icon={<Bolt c="#B07800" s={17} />} title="크레딧 구매" sub="이번 달에 필요한 만큼만 더 써요" onPress={() => { setSheet(false); p.onBuyCredit(); }} />
            <Choice bg="#EEE9FB" icon={<Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="#6A42AB" strokeWidth={2} strokeLinejoin="round"><Path d="M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4 6.7 19.4l1.2-6L3.4 9.3l6-.7z" /></Svg>} title="플랜 변경" sub="매달 받는 사용량을 늘려요 · MY › 플랜" onPress={() => { setSheet(false); p.onChangePlan(); }} />
          </View>
        </View>
      </Sheet>
    </TabFrame>
  );
}

function Choice({ bg, icon, title, sub, onPress }: { bg: string; icon: React.ReactNode; title: string; sub: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [st.ch, pressed && { backgroundColor: '#EEEEF1' }]}>
      <View style={[st.ci, { backgroundColor: bg }]}>{icon}</View>
      <View style={{ flex: 1 }}><Text style={st.chB}>{title}</Text><Text style={st.chS}>{sub}</Text></View>
      <Chev c={C.ink3} />
    </Pressable>
  );
}

/* .mfeat 라디오 카드: 라운드 20 · 16 · 머리 12.5 파랑 · 제목 17 · 재생 44 · 파형 · 아래 줄 */
function RadioCard({ m, playing, onPress, onPlay, onRemove }: { m: MadeItem; playing: boolean; onPress: () => void; onPlay: () => void; onRemove: () => void }) {
  return (
    <View style={st.mfeat}>
      <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={`${m.title} 열기`}>
        <View style={st.mh}>
          <Svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="#3D73F0" strokeWidth={1.8} strokeLinecap="round"><Path d="M4 10V14M8 7V17M12 4V20M16 8V16M20 11V13" /></Svg>
          <Text style={st.mhT}>AI 오디오 · 최신</Text>
        </View>
        <Text style={st.mfB}>{m.title}</Text>
        <Text style={st.mfS}>{m.sub}</Text>
      </Pressable>
      <View style={st.pl}>
        <Pressable onPress={onPlay} accessibilityRole="button" accessibilityLabel={playing ? '일시정지' : '바로 재생'} accessibilityState={{ disabled: audioOff }} style={[st.pb, audioOff && { backgroundColor: AUDIO_OFF_BG }]}>{playing ? <PauseGlyph /> : <PlayGlyph />}</Pressable>
        <Pressable onPress={onPress} accessible={false} style={st.wv}>{WAVE.map((h, i) => <View key={i} style={[st.wvI, { height: h, backgroundColor: i < 5 ? '#3D73F0' : '#C9D7FB' }]} />)}</Pressable>
        <Text style={st.du}>{m.dur}</Text>
      </View>
      <View style={st.mf}>
        <Text style={[st.mfT, { flex: 1 }]}>{m.foot}</Text>
        <Text style={st.mfT}>{m.left}</Text>
        <Pressable onPress={onRemove} accessibilityRole="button" accessibilityLabel={`${m.title} 휴지통으로`} hitSlop={12} style={{ marginLeft: 10, marginVertical: -1 }}><Trash /></Pressable>
      </View>
    </View>
  );
}

const Trash = () => <Svg width={16} height={16} viewBox="0 0 16 16" fill="none"><Path d="M2.5 4h11M6 4V2.75h4V4M4 4l.6 9.25h6.8L12 4" stroke="#B0B5BD" strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" /></Svg>;
const PlayGlyph = ({ s = 16 }: { s?: number }) => <Svg width={s} height={s} viewBox="0 0 24 24" fill="#fff"><Path d="M8 5v14l11-7z" /></Svg>;
const PauseGlyph = ({ s = 16 }: { s?: number }) => <Svg width={s} height={s} viewBox="0 0 24 24" fill="#fff"><Path d="M7 5h4v14H7zM13 5h4v14h-4z" /></Svg>;

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  subr: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingBottom: 10 },
  subrT: { ...nf(13.5), color: '#6B7079' },
  cred: { flexDirection: 'row', alignItems: 'center', gap: 4, height: 28, paddingHorizontal: 10, borderRadius: 14, backgroundColor: '#F0ECFF' },
  credZero: { backgroundColor: '#FFF1D6', borderWidth: 1, borderColor: '#F1D9A8' },
  credT: { ...nf(13.5), fontWeight: '800', color: '#5B3BD1', fontVariant: ['tabular-nums'] },
  fc: { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: '#FFFFFF', borderRadius: 20, marginHorizontal: 16, marginBottom: 10, padding: 16 },
  fcH: { ...nf(16), fontWeight: '800', color: C.ink, marginBottom: 3 },
  fcP: { ...nf(14), color: C.ink2 },
  secr: { flexDirection: 'row', alignItems: 'baseline', gap: 8, paddingTop: 12, paddingHorizontal: 18, paddingBottom: 8 },
  secrT: { ...nf(15.5), fontWeight: '800', color: C.ink },
  secrS: { ...nf(13), fontWeight: '500', color: '#6B7079' },
  made: { backgroundColor: '#FFFFFF', borderRadius: 20, marginHorizontal: 16, paddingVertical: 4, paddingHorizontal: 16 },
  mi: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 },
  mrow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  miMain: { flex: 1, minWidth: 0 },
  miLine: { borderTopWidth: 1, borderTopColor: '#F0F1F4' },
  miB: { ...nf(15.5), fontWeight: '700', color: C.ink },
  miS: { ...nf(13), color: '#6B7079' },
  miR: { ...nf(13), color: '#6B7079' },
  del: { width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  failIc: { width: 38, height: 38, borderRadius: 12, backgroundColor: '#FFE4E4', alignItems: 'center', justifyContent: 'center' },
  qp: { width: 32, height: 32, borderRadius: 16, marginRight: 14, backgroundColor: '#3D73F0', alignItems: 'center', justifyContent: 'center' },
  spin: { width: 20, height: 20 },
  empty: { fontSize: 14, lineHeight: 21.5, color: '#6B7079', textAlign: 'center', paddingVertical: 20 },
  mfeat: { backgroundColor: '#FFFFFF', borderRadius: 20, marginHorizontal: 16, marginBottom: 10, padding: 16 },
  mh: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  mhT: { ...nf(13.5), fontWeight: '700', color: '#3D73F0' },
  mfB: { ...nf(17), fontWeight: '700', color: C.ink, marginTop: 8 },
  mfS: { ...nf(14), color: C.ink2, marginTop: 2 },
  pl: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 14 },
  pb: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#3D73F0', alignItems: 'center', justifyContent: 'center' },
  wv: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 3, height: 28 },
  wvI: { width: 3, borderRadius: 2 },
  du: { ...nf(14), fontWeight: '700', color: C.ink2 },
  spent: { marginHorizontal: 16, marginBottom: 10 },
  mf: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, borderTopColor: '#F0F1F4', marginTop: 14, paddingTop: 10 },
  mfT: { ...nf(13), color: '#6B7079' },
  sdisc: { ...nf(13), color: '#6B7079', textAlign: 'center', marginTop: 14, marginHorizontal: 16, marginBottom: 24 },
  shH: { ...nf(19), fontWeight: '700', color: C.ink, marginBottom: 4 },
  shD: { ...nf(13.5), color: '#6B7079', marginBottom: 2 },
  ubar: { height: 8, borderRadius: 4, backgroundColor: '#ECEDF1', overflow: 'hidden', marginTop: 10, marginBottom: 16 },
  ubarI: { height: '100%', borderRadius: 4 },
  ch: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16, backgroundColor: '#F6F6F8' },
  ci: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  chB: { ...nf(16), fontWeight: '700', color: C.ink },
  chS: { ...nf(13.5), color: '#6B7079', marginTop: 1 },
});
