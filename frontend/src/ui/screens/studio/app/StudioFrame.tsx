import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { WebIcon } from '@/ui/icons/Icon';
import { webColor } from '@/ui/theme';
import { useCoachRef } from '@/ui/shared/Coach';
import { useShellSize } from '@/ui/layout/web/shellSize';

/** 앱 스튜디오 틀: 웹 StudioColumnFrame 펼침 머리와 같고, 폭 100% · 접기 대신 오른쪽에 알림 · MY */
export function StudioFrame({ stockCount, aiMemoCount, usagePct, onUsage, right, children }: {
  stockCount: number; aiMemoCount: number; usagePct: number; onUsage: () => void; right: React.ReactNode; children: React.ReactNode;
}) {
  /* 사용법 안내 ④ 대상 */
  const coachRef = useCoachRef('studio');
  const z = useShellSize();
  const out = usagePct >= 100;
  return (
    <View style={st.col} accessibilityLabel="스튜디오">
      <View ref={coachRef} collapsable={false} style={st.card}>
        <View style={[st.head, z.studioHead, st.mobileHead]}>
          <View style={st.star}>
            <WebIcon name="sparkleNudge" size={19} color="#FFFFFF" />
          </View>
          <View style={st.headText}>
            <Text style={[st.title, z.studioTitle]} numberOfLines={1}>
              스튜디오
            </Text>
            <Text style={[st.sub, z.studioSub]} numberOfLines={1}>
              {z.compact ? `종목 ${stockCount} · AI 메모 ${aiMemoCount}` : `내 종목 ${stockCount} · AI 연결 메모 ${aiMemoCount}`}
            </Text>
          </View>
          <Pressable onPress={onUsage} accessibilityRole="button" accessibilityLabel={`AI 사용량 ${usagePct}%`} style={[st.usage, { backgroundColor: out ? webColor.usageOutBg : webColor.chip }]}>
            <View style={st.bar}>
              <View style={[st.barFill, { width: `${Math.min(100, usagePct)}%`, backgroundColor: out ? webColor.usageOutBar : webColor.ink }]} />
            </View>
            <Text style={[st.usageT, { color: out ? webColor.usageOutInk : webColor.ink }]}>AI 사용량 {usagePct}%</Text>
          </Pressable>
          {right}
        </View>
        <View style={st.body}>{children}</View>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  col: { width: '100%', height: '100%' },
  card: { flex: 1, overflow: 'hidden', backgroundColor: webColor.surface },
  /* 앱 탭 상단 바와 같은 높이 60 · 오른쪽 12 (TopBar SPEC) */
  mobileHead: { height: 60, paddingTop: 0, paddingBottom: 0, paddingRight: 12, gap: 8 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  star: { width: 32, height: 32, borderRadius: 10, backgroundColor: webColor.ink, alignItems: 'center', justifyContent: 'center' },
  headText: { flex: 1, minWidth: 0 },
  /* 원본 text-[22px] leading-[1.3] tracking-[-0.4px] */
  title: { letterSpacing: -0.4, fontWeight: '700', color: webColor.ink },
  sub: { color: webColor.studioSub },
  usage: { height: 32, flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 999, paddingHorizontal: 12 },
  bar: { width: 24, height: 6, borderRadius: 999, overflow: 'hidden', backgroundColor: 'rgba(0,0,0,0.1)' },
  barFill: { position: 'absolute', left: 0, top: 0, bottom: 0, borderRadius: 999 },
  usageT: { fontSize: 13, lineHeight: 20, fontWeight: '700' },
  body: { flex: 1, minHeight: 0 },
});
