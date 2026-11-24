import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import type { DataProps } from '../My.types';
import { ConfirmSheet, Grp, Item, Lb, MC, Page, Rv } from './parts';

/**
 * 앱 데이터 = 원본 app/my.html openData() — 개수 3칸 · 위험 구역(모든 데이터 삭제 [전체 삭제]) → 확인 시트
 * 앱 원본에는 내보내기가 없음 (웹만). 전체 삭제는 확인까지만 — mock 데이터도 지우지 않음.
 */
export function AppData({ counts, onBack, onWipe }: DataProps) {
  const [ask, setAsk] = useState(false);
  const closeAsk = useCallback(() => {
    if (!ask) return false;
    setAsk(false);
    return true;
  }, [ask]);
  const stats: [string, number][] = [['메모', counts.memo], ['투자 기록', counts.journal], ['종목', counts.stock]];
  return (
    <Page title="데이터" onBack={onBack} onHardwareBack={closeAsk}>
      <Rv i={0}>
        <View style={st.sm3}>{stats.map(([l, n]) => <View key={l} style={st.sm}><Text style={st.smL}>{l}</Text><Text style={st.smB}>{n}개</Text></View>)}</View>
      </Rv>
      <Rv i={1}><Lb><Text style={{ color: MC.red }}>위험 구역</Text></Lb></Rv>
      <Rv i={5}>
        <Grp>
          <Item
            two
            last
            title="모든 데이터 삭제"
            sub="모든 메모, 기록, 종목이 영구 삭제돼요. 되돌릴 수 없어요."
            right={
              <Pressable onPress={() => setAsk(true)} style={({ pressed }) => [st.del, pressed && { backgroundColor: '#FFF5F5' }]} accessibilityRole="button" accessibilityLabel="전체 삭제">
                <Text style={st.delT}>전체 삭제</Text>
              </Pressable>
            }
          />
        </Grp>
      </Rv>
      <ConfirmSheet
        open={ask}
        red
        title="모든 데이터를 삭제할까요?"
        body={`메모 ${counts.memo}개, 투자 기록 ${counts.journal}개, 종목 ${counts.stock}개가 영구 삭제돼요. 되돌릴 수 없어요.`}
        ok="전체 삭제"
        onCancel={() => setAsk(false)}
        onOk={() => { setAsk(false); onWipe(); }}
      />
    </Page>
  );
}

const st = StyleSheet.create({
  sm3: { flexDirection: 'row', gap: 6, marginBottom: 4 },
  sm: { flex: 1, backgroundColor: '#FFFFFF', borderRadius: 14, paddingVertical: 11, paddingHorizontal: 12 },
  smL: { fontSize: 11.5, lineHeight: 14, color: MC.ink3 },
  smB: { fontSize: 19, lineHeight: 22, fontWeight: '700', color: MC.ink, marginTop: 2 },
  del: { borderWidth: 1, borderColor: '#F3B9B9', borderRadius: 10, paddingVertical: 6, paddingHorizontal: 12, minHeight: 32, justifyContent: 'center' },
  delT: { fontSize: 12.5, lineHeight: 18, fontWeight: '700', color: MC.red },
});
