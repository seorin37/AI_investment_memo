import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { fpx } from '@/ui/theme';
import { useCoachRef } from '@/ui/shared/Coach';
import { INK, Toggle45 } from '../web/parts';

/** 앱 새 메모 시트의 AI 연결 칸: 웹 memo/web/parts.tsx AiFooter 와 같고, 폭이 좁아 설명을 두 줄까지 */
export function AiFooter({ on, set, sub }: { on: boolean; set: (v: boolean) => void; sub: string }) {
  const coachRef = useCoachRef('ai');
  return (
    <View style={st.foot}>
      <View ref={coachRef} collapsable={false} style={st.footBox}>
        <View style={st.footRow}>
          <View style={st.flex}>
            <Text style={st.footT}>AI 연결</Text>
            <Text style={[st.footS, { color: on ? '#57535F' : '#4E5968' }]} numberOfLines={2}>
              {sub}
            </Text>
          </View>
          <Toggle45 on={on} set={set} />
        </View>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  foot: { paddingHorizontal: 24, paddingVertical: 12 },
  footBox: { minHeight: 84, borderRadius: 12, backgroundColor: '#F2F3F4', paddingHorizontal: 16, paddingVertical: 8, justifyContent: 'center' },
  footRow: { minHeight: 40, flexDirection: 'row', alignItems: 'center', gap: 12 },
  footT: { ...fpx(17, 26), fontWeight: '500', color: INK },
  footS: { ...fpx(14, 21), fontWeight: '500' },
});
