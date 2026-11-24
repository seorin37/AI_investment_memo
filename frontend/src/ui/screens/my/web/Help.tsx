import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { FixedFrame } from '@/ui/layout/web/FixedFrame';
import { fpx } from '@/ui/theme';
import { Chev, type Hover } from './parts';

/**
 * 웹 도움말 = 원본 overlays.tsx HelpPage (FixedFrame 860 · 위아래 32 · 사이 32)
 * PageTitle('도움말' · '자주 묻는 질문과 사용법이에요.') · 사용법 다시 보기 카드 420 · FAQ 아코디언(첫 항목 열림 · 줄 60)
 */
export function WebHelp({ faq, onReplayGuide }: { faq: [string, string][]; onReplayGuide: () => void }) {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false}>
      <FixedFrame>
        <View style={st.page}>
          <View style={st.head}>
            <Text style={st.title}>도움말</Text>
            <Text style={st.sub}>자주 묻는 질문과 사용법이에요.</Text>
          </View>
          <Pressable onPress={onReplayGuide} accessibilityRole="button" style={({ hovered }: Hover) => [st.replay, hovered && { backgroundColor: '#F9F9F9' }]}>
            <View style={st.hic}>
              <Svg width={20} height={20} viewBox="0 0 20 20" fill="none"><Circle cx={10} cy={10} r={7.2} stroke="white" strokeWidth={1.6} /><Path d="M12.9 7.1L11.3 11.3L7.1 12.9L8.7 8.7L12.9 7.1Z" fill="white" /></Svg>
            </View>
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text style={st.rT}>사용법 다시 보기</Text>
              <Text style={st.rS}>메모 쓰기부터 스튜디오까지 30초 안내</Text>
            </View>
            <Svg width={18} height={18} viewBox="0 0 18 18" fill="none"><Path d="M6.75 4.5L11.25 9L6.75 13.5" stroke="#9AA0AA" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" /></Svg>
          </Pressable>
          <View style={st.faq}>
            {faq.map(([q, a], i) => (
              <View key={q} style={i < faq.length - 1 && st.sep}>
                <Pressable onPress={() => setOpen(open === i ? null : i)} accessibilityRole="button" accessibilityState={{ expanded: open === i }} style={st.q}>
                  <Text style={st.qT}>{q}</Text>
                  <Chev dir={open === i ? 'up' : 'down'} />
                </Pressable>
                {open === i ? <Text keepAll style={st.a}>{a}</Text> : null}
              </View>
            ))}
          </View>
        </View>
      </FixedFrame>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  page: { width: 860, gap: 32, paddingTop: 32, paddingBottom: 32, alignItems: 'flex-start' },
  head: { width: '100%', paddingTop: 24, gap: 4 },
  title: { ...fpx(26, 35), fontWeight: '700', letterSpacing: -0.26, color: '#16171A' },
  sub: { ...fpx(14, 21), color: '#575B63' },
  replay: { width: 420, maxWidth: '100%', flexDirection: 'row', alignItems: 'center', gap: 16, borderRadius: 16, borderWidth: 1, borderColor: '#E5E8EB', backgroundColor: '#FFFFFF', padding: 20 },
  hic: { width: 44, height: 44, borderRadius: 14, backgroundColor: '#111111', alignItems: 'center', justifyContent: 'center' },
  rT: { ...fpx(17, 26), fontWeight: '700', color: '#191F28' },
  rS: { ...fpx(14, 21), color: '#6B7684' },
  faq: { width: 860, borderRadius: 16, borderWidth: 1, borderColor: '#E5E8EB', backgroundColor: '#FFFFFF', paddingHorizontal: 24, paddingVertical: 8 },
  sep: { borderBottomWidth: 1, borderBottomColor: '#EFEFF2' },
  q: { height: 60, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  qT: { ...fpx(17, 26), fontWeight: '700', color: '#191F28' },
  a: { ...fpx(15, 24), color: '#4E5968', paddingBottom: 20 },
});
