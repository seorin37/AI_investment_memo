import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import type { PlansProps } from '../My.types';
import { Foot, Grp, Lb, MC, OkIcon, Page, Rv } from './parts';

/**
 * 앱 플랜 살펴보기 = 원본 app/my.html plansHTML() · openPlans()
 * 플랜 카드 3장(고른 카드 검정 테두리 2 · 라디오) · 한눈에 비교 · 안내 · 아래 고정 [PLUS 시작하기]
 * 가격·한도는 GET /plans (configs/credits.yaml, 2026-11-25). 월간만 (연간 결제 미정이라 토글 숨김). 결제는 연결 안 됨 → onStart 에서 안내만.
 */
export function AppPlans(p: PlansProps) {
  const [pick, setPick] = useState(p.default_key);
  /* 고른 카드가 지금 쓰는 플랜이면 시작하기 대신 안내 (예전: 첫 카드 = 현재 플랜 가정) */
  const free = pick === p.current_key;
  return (
    <Page
      title="플랜 살펴보기"
      lead="필요한 만큼 AI 업데이트와 스튜디오를 쓸 수 있게 골라요. 가격은 부가세 포함이고, 앱과 웹이 같아요."
      onBack={p.onBack}
      bottom={
        <>
          <Pressable disabled={free} onPress={() => p.onStart(pick)} style={({ pressed }) => [st.cta, free && st.ctaDis, pressed && { opacity: 0.9 }]} accessibilityRole="button">
            <Text style={[st.ctaT, free && { color: MC.ink3 }]}>{free ? '지금 쓰는 플랜이에요' : `${pick} 시작하기`}</Text>
          </Pressable>
          <Text style={st.cap}>결제는 스토어 결제 창에서 진행돼요</Text>
        </>
      }
    >
      {p.plans.map((pl, i) => {
        const on = pl.key === pick;
        return (
          <Rv key={pl.key} i={i + 1}>
            <Pressable onPress={() => setPick(pl.key)} style={({ pressed }) => [st.pc, on && st.pcOn, pressed && { transform: [{ scale: 0.985 }] }]} accessibilityRole="radio" accessibilityState={{ checked: on }}>
              <View style={st.pcH}>
                <Text style={st.nm}>{pl.key}</Text>
                {pl.tag === '현재 플랜' ? <View style={[st.bd2, { backgroundColor: '#F1F2F4' }]}><Text style={[st.bd2T, { color: MC.ink2 }]}>현재 플랜</Text></View> : null}
                {pl.tag === '추천' ? <View style={[st.bd2, { backgroundColor: MC.aSoft }]}><Text style={[st.bd2T, { color: MC.a2 }]}>추천</Text></View> : null}
                <View style={[st.rd, on && st.rdOn]} />
              </View>
              <Text style={st.pr}>{pl.price} <Text style={st.prS}>{pl.price === '0원' ? '' : '/ 월'}</Text></Text>
              {pl.first ? <Text style={st.first}>{pl.first}</Text> : null}
              <View style={st.ul}>{pl.features.map((f) => <View key={f} style={st.li}><OkIcon /><Text keepAll style={st.liT}>{f}</Text></View>)}</View>
            </Pressable>
          </Rv>
        );
      })}
      <Rv i={4}><Lb>한눈에 비교</Lb></Rv>
      <Rv i={5}>
        <Grp style={st.cmp}>
          <View style={st.cr}>
            <Text style={[st.c0, st.crT]} />
            {p.plans.map((pl) => <Text key={pl.key} style={[st.c, st.crT, st.hd]}>{pl.key}</Text>)}
          </View>
          {p.compare.map(([l, vals], i) => (
            <View key={l} style={[st.cr, i === p.compare.length - 1 && { borderBottomWidth: 0 }]}>
              <Text keepAll style={[st.c0, st.crT, { color: MC.ink2 }]}>{l}</Text>
              {vals.map((v, j) => <View key={j} style={st.c}>{v === true ? <OkIcon /> : <Text style={[st.crT, { textAlign: 'center' }]}>{v}</Text>}</View>)}
            </View>
          ))}
        </Grp>
      </Rv>
      <Rv i={6}><Foot>{p.notes.map((n) => `· ${n}`).join('\n')}</Foot></Rv>
    </Page>
  );
}

const st = StyleSheet.create({
  pc: { borderWidth: 1.5, borderColor: '#E2E4E8', backgroundColor: '#FFFFFF', borderRadius: 20, padding: 16, marginBottom: 10 },
  pcOn: { borderWidth: 2, borderColor: MC.ink, padding: 15.5, shadowColor: '#000000', shadowOpacity: 0.25, shadowRadius: 10, shadowOffset: { width: 0, height: 6 }, elevation: 4 },
  pcH: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  nm: { fontSize: 18, lineHeight: 25, fontWeight: '800', letterSpacing: 0.36, color: MC.ink },
  bd2: { borderRadius: 6, paddingVertical: 2, paddingHorizontal: 7 },
  bd2T: { fontSize: 11, lineHeight: 15, fontWeight: '800' },
  rd: { marginLeft: 'auto', width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: '#C9CCD2' },
  rdOn: { borderWidth: 7, borderColor: MC.ink },
  pr: { fontSize: 22, lineHeight: 30, fontWeight: '800', color: MC.ink, marginTop: 10, marginBottom: 2 },
  prS: { fontSize: 13, fontWeight: '500', color: MC.ink3 },
  first: { fontSize: 13, lineHeight: 18, fontWeight: '700', color: MC.a2 },
  ul: { marginTop: 10, gap: 7 },
  li: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  liT: { flex: 1, fontSize: 13.5, lineHeight: 19.6, color: '#33343A' },
  cmp: { paddingVertical: 4, paddingHorizontal: 14 },
  cr: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F1F2F4' },
  c0: { flex: 1.3 },
  c: { flex: 1, alignItems: 'center', textAlign: 'center' },
  crT: { fontSize: 12.5, lineHeight: 18, color: MC.ink },
  hd: { fontWeight: '800' },
  cta: { borderRadius: 16, paddingVertical: 16, minHeight: 56, alignItems: 'center', justifyContent: 'center', backgroundColor: MC.ink },
  ctaDis: { backgroundColor: '#E3E5E9' },
  ctaT: { fontSize: 16, lineHeight: 23, fontWeight: '800', color: '#FFFFFF' },
  cap: { textAlign: 'center', fontSize: 11, lineHeight: 15.4, color: MC.ink3, marginTop: 6 },
});
