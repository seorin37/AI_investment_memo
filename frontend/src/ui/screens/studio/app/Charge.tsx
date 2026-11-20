import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { PressScale } from '@/ui/motion/PressScale';
import { Page } from '../../my/app/parts';
import type { ChargeProps } from '../Studio.types';

/**
 * 앱 크레딧 충전 = 원본 app/studio.html #pgCg (21)
 * '충전할 크레딧' · 상품 줄 58(라운드 16 · 고르면 테두리 2 #16171A · 동그라미 22) · 아래 [N 크레딧 결제하기] + 안내 11.5
 * 원본의 '상품 구성·가격은 … 임시예요' 문구는 미정 안내라 뺌. 결제는 연결 안 됨 → onPay 에서 안내만
 */
export function AppCharge({ packs, default_credits, onBack, onPay }: ChargeProps) {
  const [n, setN] = useState(default_credits);
  const cur = packs.find((x) => x.credits === n);
  return (
    <Page
      title="크레딧 충전"
      onBack={onBack}
      bottom={
        <View>
          <PressScale onPress={() => onPay(n)} accessibilityRole="button" style={st.cta}><Text style={st.ctaT}>{cur?.label ?? ''} 결제하기</Text></PressScale>
          <Text style={st.cap}>스토어 결제 창이 열려요 · 결제 수단은 그 창에서 골라요</Text>
        </View>
      }
    >
      <Text style={st.secr}>충전할 크레딧</Text>
      {packs.map((p) => {
        const on = p.credits === n;
        return (
          <PressScale key={p.credits} scaleTo={0.98} onPress={() => setN(p.credits)} accessibilityRole="radio" accessibilityState={{ selected: on }} style={[st.pk, on && st.pkOn]}>
            <View style={[st.rd, on && { borderColor: '#16171A' }]}>{on ? <View style={st.rdI} /> : null}</View>
            <Text style={st.pkT}>{p.label}</Text>
            {p.tag ? <View style={st.tag}><Text style={st.tagT}>{p.tag}</Text></View> : null}
            <Text style={st.pr}>{p.price}</Text>
          </PressScale>
        );
      })}
    </Page>
  );
}

const st = StyleSheet.create({
  secr: { fontSize: 15, lineHeight: 21, fontWeight: '800', color: '#16171A', paddingTop: 4, paddingHorizontal: 2, paddingBottom: 8 },
  pk: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 10, backgroundColor: '#FFFFFF', borderRadius: 16, height: 58, paddingHorizontal: 16, borderWidth: 2, borderColor: 'transparent' },
  pkOn: { borderColor: '#16171A' },
  rd: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: '#C9CDD4', alignItems: 'center', justifyContent: 'center' },
  rdI: { width: 12, height: 12, borderRadius: 6, backgroundColor: '#16171A' },
  pkT: { fontSize: 15, lineHeight: 21, fontWeight: '800', color: '#16171A' },
  tag: { backgroundColor: '#16171A', borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 },
  tagT: { fontSize: 11, lineHeight: 15, fontWeight: '700', color: '#FFFFFF' },
  pr: { marginLeft: 'auto', fontSize: 15, lineHeight: 21, fontWeight: '600', color: '#575B63' },
  cta: { height: 54, borderRadius: 15, backgroundColor: '#16171A', alignItems: 'center', justifyContent: 'center' },
  ctaT: { fontSize: 16, lineHeight: 22, fontWeight: '800', color: '#FFFFFF' },
  cap: { textAlign: 'center', fontSize: 11.5, lineHeight: 16, color: '#9A9EA7', marginTop: 6 },
});
