import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import type { HelpProps } from '../My.types';
import { Chev, MC, Page, Rv } from './parts';

/**
 * 앱 도움말 = 원본 app/my.html openHelp() (사용법 다시 보기 카드)
 * 원본 머리 글 '서비스 이용 안내는 준비 중이에요.'는 개발 상태 문구라 뺌.
 * 웹 자주 묻는 질문은 '사이드바' 등 웹 기준 문구라 앱에는 넣지 않음.
 */
export function AppHelp({ onBack, onReplayGuide }: HelpProps) {
  return (
    <Page title="도움말" onBack={onBack}>
      <Rv i={0}>
        <Pressable onPress={onReplayGuide} style={({ pressed }) => [st.hre, pressed && { backgroundColor: '#F7F7F9' }]} accessibilityRole="button">
          <View style={st.hic}>
            <Svg width={20} height={20} viewBox="0 0 20 20" fill="none"><Circle cx={10} cy={10} r={7.2} stroke="#FFFFFF" strokeWidth={1.6} /><Path d="M12.9 7.1L11.3 11.3L7.1 12.9L8.7 8.7L12.9 7.1Z" fill="#FFFFFF" /></Svg>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={st.hreB}>사용법 다시 보기</Text>
            <Text style={st.hreS}>메모 쓰기부터 스튜디오까지 30초 안내</Text>
          </View>
          <Chev />
        </Pressable>
      </Rv>
    </Page>
  );
}

const st = StyleSheet.create({
  hre: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 18, paddingHorizontal: 16, backgroundColor: '#FFFFFF', borderRadius: 18 },
  hic: { width: 44, height: 44, borderRadius: 14, backgroundColor: MC.a, alignItems: 'center', justifyContent: 'center' },
  hreB: { fontSize: 16, lineHeight: 23, fontWeight: '700', color: MC.ink },
  hreS: { fontSize: 13, lineHeight: 19, color: MC.ink2, marginTop: 2 },
});
