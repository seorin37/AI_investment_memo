import React from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { useShellSize } from '@/ui/layout/web/shellSize';
import { FeatIcon } from '@/ui/layout/web/StudioColumnFrame';
import { SpentBox } from '@/ui/shared/SpentBox';
import { studioFeature } from '@/ui/theme';
import type { MadeItem, StudioFeatureItem, StudioKind } from '../Studio.types';
import { AUDIO_OFF_BG } from '../appAudio';
import { useRemoveMade } from '../studioItems';

type Hover = { hovered?: boolean; pressed?: boolean };

/**
 * 앱 스튜디오 홈: 웹 studio/web/StudioHome.tsx 와 같음 + 재생을 막는 동안 못 누르는 색(playOff).
 * 원본 web studio.tsx Home (스튜디오 열 카드 안 · 안쪽 16 · 사이 10)
 * (다 썼으면 SpentBox) · 설명 14 · 기능 줄(아이콘 44/13 · 제목 17 · 설명 15 · ›) · '만든 항목' 17 + 30일 보관 ·
 * 목록(라운드 18 · 줄 72 · 오디오는 바로 재생 36) · 아래 안내 13
 */
export function AppStudioHome({ features, made, spent, refill, bottomPad = 0, playOff, onFeature, onOpenMade, onQuickPlay, onBuyCredit, onChangePlan }: {
  /** 미니 플레이어가 떠 있으면 아래 빈 자리 (원본 pb-[84px]) */
  bottomPad?: number;
  /** 앱: 재생 모듈이 없는 동안 바로 재생을 못 누르는 색으로 */
  playOff?: boolean;
  features: StudioFeatureItem[];
  made: MadeItem[];
  spent: boolean;
  refill: string;
  onFeature: (k: StudioKind) => void;
  onOpenMade: (m: MadeItem) => void;
  onQuickPlay: (m: MadeItem) => void;
  onBuyCredit: () => void;
  onChangePlan: () => void;
}) {
  const remove = useRemoveMade();
  const z = useShellSize();
  return (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={[st.page, { paddingHorizontal: z.homePadX, paddingBottom: 24 + bottomPad }]} showsVerticalScrollIndicator={false}>
      {spent ? <SpentBox variant="web" title="이번 달 AI 사용량을 다 썼어요" body={`${refill}에 새로 채워져요.\n이미 만든 결과와 오늘의 퀴즈는 계속 쓸 수 있어요.`} onCredit={onBuyCredit} onPlan={onChangePlan} /> : null}
      <Text style={st.lead}>쌓인 소식을 듣고, 읽고, 실험해 보세요</Text>
      {features.map((f) => (
        <Pressable key={f.key} onPress={() => onFeature(f.key)} accessibilityRole="button" style={({ hovered }: Hover) => [st.feat, z.feat, hovered && { backgroundColor: '#F9F9F9' }]}>
          <View style={[st.fi, z.featBox, { backgroundColor: studioFeature[f.key].box }]}><FeatIcon f={f.key} size={z.featIcon} /></View>
          <View style={{ flex: 1, minWidth: 0, gap: 3 }}>
            <Text style={[st.fT, z.featTitle]}>{f.title}</Text>
            <Text style={[st.fD, z.featDesc]}>{f.desc}</Text>
          </View>
          <Svg width={18} height={18} viewBox="0 0 18 18" fill="none"><Path d="M6.75 4.5L11.25 9L6.75 13.5" stroke="#9AA0AA" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" /></Svg>
        </Pressable>
      ))}
      <View style={st.secr}><Text style={st.secrT}>만든 항목</Text><Text style={st.secrS}>30일 보관 · 다시 보기 무료</Text></View>
      <View style={st.made}>
        {!made.length ? <Text style={st.empty}>{'아직 만든 항목이 없어요\n위에서 오디오·보고서·실험을 만들어 보세요'}</Text> : null}
        {made.map((m, i) => (
          <View key={m.id} style={[st.row, i < made.length - 1 && st.rowLine]}>
            <Pressable onPress={() => onOpenMade(m)} accessibilityRole="button" style={st.rowMain}>
              <View style={[st.mi, { backgroundColor: studioFeature[m.kind].box }]}><FeatIcon f={m.kind} size={20} /></View>
              <View style={{ flex: 1, minWidth: 0, gap: 4 }}>
                <Text style={st.mT} numberOfLines={1}>{m.title}</Text>
                <Text style={st.mS} numberOfLines={1}>{m.meta}</Text>
              </View>
              {m.kind !== 'audio' ? <Text style={st.mS}>{m.left}</Text> : null}
            </Pressable>
            <Pressable onPress={() => remove(m)} accessibilityRole="button" accessibilityLabel={`${m.title} 휴지통으로`} hitSlop={6} style={({ hovered }: Hover) => [st.del, hovered && { backgroundColor: '#FBEFEF' }]}>
              {({ hovered }: Hover) => <TrashGlyph color={hovered ? '#E45D6A' : '#B0B5BD'} />}
            </Pressable>
            {m.kind === 'audio' ? (
              <Pressable onPress={() => onQuickPlay(m)} accessibilityRole="button" accessibilityLabel="바로 재생" style={({ hovered }: Hover) => [st.qp, hovered && { backgroundColor: '#2A2A2A' }, playOff && { backgroundColor: AUDIO_OFF_BG }]}>
                <Svg width={14} height={14} viewBox="0 0 14 14" fill="#FFFFFF"><Path d="M4 2.5v9l7.5-4.5z" /></Svg>
              </Pressable>
            ) : null}
          </View>
        ))}
      </View>
      <Text style={st.disc}>스튜디오는 투자 권유나 주가 예측을 하지 않아요.</Text>
    </ScrollView>
  );
}

/** 휴지통 아이콘 (만든 항목 삭제 = 휴지통, 2026-11-24) */
function TrashGlyph({ color }: { color: string }) {
  return (
    <Svg width={16} height={16} viewBox="0 0 16 16" fill="none">
      <Path d="M2.5 4h11M6 4V2.75h4V4M4 4l.6 9.25h6.8L12 4" stroke={color} strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

const st = StyleSheet.create({
  page: { gap: 10, paddingTop: 8 },
  lead: { fontSize: 14, lineHeight: 21, color: '#9A9EA7' },
  feat: { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 16, backgroundColor: '#FFFFFF' },
  fi: { alignItems: 'center', justifyContent: 'center' },
  fT: { fontWeight: '700', color: '#16171A' },
  fD: { color: '#575B63' },
  secr: { flexDirection: 'row', alignItems: 'flex-end', gap: 6, paddingTop: 28 },   // 위 기능 목록과 띄움 (2026-11-23, 8 → 28)
  secrT: { fontSize: 17, lineHeight: 26, fontWeight: '700', color: '#16171A' },
  secrS: { fontSize: 14, lineHeight: 21, color: '#9A9EA7' },
  made: { borderRadius: 18, backgroundColor: '#FFFFFF', paddingHorizontal: 16 },
  empty: { paddingVertical: 24, textAlign: 'center', fontSize: 14, lineHeight: 21, color: '#9A9EA7' },
  row: { height: 72, flexDirection: 'row', alignItems: 'center', gap: 12 },
  rowMain: { flex: 1, minWidth: 0, height: 72, flexDirection: 'row', alignItems: 'center', gap: 12 },
  rowLine: { borderBottomWidth: 1, borderBottomColor: '#F0F1F3' },
  mi: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  mT: { fontSize: 17, lineHeight: 26, fontWeight: '500', color: '#16171A' },
  mS: { fontSize: 14, lineHeight: 21, color: '#9A9EA7' },
  del: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  qp: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#15171A', alignItems: 'center', justifyContent: 'center' },
  disc: { paddingTop: 4, textAlign: 'center', fontSize: 13, lineHeight: 20, color: '#9A9EA7' },
});
