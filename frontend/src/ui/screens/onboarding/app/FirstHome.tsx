import React from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { Sheet } from '@/ui/shared/Sheet';
import { StockLogo } from '@/ui/shared/StockLogo';
import { appColor, ft } from '@/ui/theme';
import type { FirstHomeProps } from '../FirstHome.types';

export function AppFirstHome(p: FirstHomeProps) {
  return (
    <>
      <View style={st.card}>
        <View style={st.paper}><View style={st.paperLine} /><View style={[st.paperLine, { width: '62%' }]} /><Text style={st.pencil}>✎</Text></View>
        <View style={st.copy}><Text style={st.eyebrow}>{p.saved ? '첫 메모를 저장했어요' : '첫 메모, 가볍게 시작해 볼까요?'}</Text><Text style={st.title}>{p.saved ? '이제 AI가 관련 소식을 확인해요' : '지금 떠오른 생각을 한 줄 적어 보세요'}</Text><Text style={st.sub}>{p.saved ? '메모 보드에서 생각과 연결된 소식을 이어서 볼 수 있어요.' : '완벽한 분석보다 지금의 생각을 남기는 게 먼저예요.'}</Text></View>
        <Pressable onPress={p.onOpenPicker} style={st.cta}><Text style={st.ctaT}>{p.saved ? '메모 보드 보기' : '첫 메모 작성하기'}</Text></Pressable>
        {!p.saved ? <Pressable onPress={p.onSkip} style={st.skip}><Text style={st.skipT}>나중에 할게요</Text></Pressable> : null}
      </View>
      <Sheet open={p.picker_open} onClose={p.onClosePicker} title="어느 종목에 메모할까요?" label="첫 메모 종목 선택">
        <ScrollView style={{ maxHeight: 390 }} contentContainerStyle={st.list}>
          {p.stocks.map((s) => <Pressable key={s.stock_code} onPress={() => p.onPickStock(s)} style={st.row}><StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={42} variant="app" /><View style={{ flex: 1 }}><Text style={st.rowB}>{s.name}</Text><Text style={st.rowS}>{s.market} · {s.stock_code}</Text></View><Text style={st.arrow}>›</Text></Pressable>)}
        </ScrollView>
      </Sheet>
    </>
  );
}

const st = StyleSheet.create({
  card: { borderRadius: 22, padding: 18, backgroundColor: '#17181C' }, paper: { height: 80, borderRadius: 15, backgroundColor: '#FCEAAA', padding: 16, marginBottom: 16 }, paperLine: { width: '82%', height: 7, marginBottom: 9, borderRadius: 4, backgroundColor: 'rgba(161,117,0,.24)' }, pencil: { position: 'absolute', right: 14, bottom: 8, fontSize: 28, color: '#A47B12' },
  copy: { gap: 4 }, eyebrow: { ...ft(12), color: '#B9A7F4', fontWeight: '800' }, title: { ...ft(20, 1.35), color: '#FFFFFF', fontWeight: '800' }, sub: { ...ft(13, 1.5), color: '#B8BBC2' }, cta: { minHeight: 50, marginTop: 16, borderRadius: 14, backgroundColor: appColor.accent, alignItems: 'center', justifyContent: 'center' }, ctaT: { ...ft(15), color: '#FFFFFF', fontWeight: '800' }, skip: { minHeight: 38, alignItems: 'center', justifyContent: 'center' }, skipT: { ...ft(13), color: '#A4A8B3' },
  list: { paddingHorizontal: 22, paddingBottom: 8 }, row: { minHeight: 66, flexDirection: 'row', alignItems: 'center', gap: 11, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#E6E8EC' }, rowB: { ...ft(15), color: '#18181C', fontWeight: '700' }, rowS: { ...ft(11), marginTop: 3, color: '#9A9EA7' }, arrow: { fontSize: 26, color: '#9A9EA7' },
});
