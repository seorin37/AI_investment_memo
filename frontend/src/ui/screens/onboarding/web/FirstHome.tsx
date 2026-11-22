import React from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { Sheet } from '@/ui/shared/Sheet';
import { StockLogo } from '@/ui/shared/StockLogo';
import { fpx } from '@/ui/theme';
import { useCoach } from '@/store/coach';
import type { FirstHomeProps } from '../FirstHome.types';

export function WebFirstHome(p: FirstHomeProps) {
  /* [둘러보기] = 앱과 같은 사용법 안내 ①부터 (2026-11-22). 안내 창만 닫고 공용 튜토리얼(store/coach · ui/shared/Coach)로.
     호스트의 onNextGuide(종목 고르기 창)는 여기서 부르지 않음 — 첫 메모 종목 고르기는 카드의 [첫 메모 작성하기](onOpenPicker) 그대로 */
  const startTour = () => {
    p.onCloseGuide();
    useCoach.getState().go(0);
  };
  return (
    <>
      <View style={st.card}>
        <View style={st.paper}><View style={st.paperLine} /><View style={[st.paperLine, { width: 92 }]} /><Text style={st.pencil}>✎</Text></View>
        <View style={st.copy}><Text style={st.eyebrow}>{p.saved ? '첫 메모 저장 완료' : '첫 메모를 남겨 보세요'}</Text><Text style={st.title}>{p.saved ? 'AI가 이 생각과 관련된 소식을 확인해요' : '지금 떠오른 생각 한 줄이면 충분해요'}</Text><Text style={st.sub}>{p.saved ? '종목 메모 보드에서 생각의 흐름을 계속 이어갈 수 있어요.' : '종목을 고르고 첫 메모를 작성하면 홈이 내 생각으로 채워져요.'}</Text></View>
        <Pressable onPress={p.onOpenPicker} style={st.cta}><Text style={st.ctaT}>{p.saved ? '메모 보드 보기' : '첫 메모 작성하기'}</Text></Pressable>
        {!p.saved ? <Pressable onPress={p.onSkip} style={st.later}><Text style={st.laterT}>나중에</Text></Pressable> : null}
      </View>
      <Sheet open={p.guide_open} onClose={p.onCloseGuide} width={430} label="첫 홈 안내" scrim="rgba(14,15,20,.52)">
        <View style={st.guide}><View style={st.guideIcon}><Text style={st.guideIconT}>✦</Text></View><Text style={st.guideTitle}>30초만 둘러볼까요?</Text><Text style={st.guideSub}>홈에서 내 종목 소식을 확인하고,{String.fromCharCode(10)}떠오른 생각을 바로 메모할 수 있어요.</Text><Pressable onPress={startTour} style={st.guideCta}><Text style={st.guideCtaT}>둘러보기</Text></Pressable><Pressable onPress={p.onSkip} style={st.guideSkip}><Text style={st.guideSkipT}>건너뛰기</Text></Pressable></View>
      </Sheet>
      <Sheet open={p.picker_open} onClose={p.onClosePicker} width={440} label="첫 메모 종목 선택">
        <View style={st.picker}><View style={st.pickerHead}><Text style={st.pickerTitle}>어느 종목에 메모할까요?</Text><Pressable onPress={p.onClosePicker}><Text style={st.close}>닫기</Text></Pressable></View><ScrollView style={{ maxHeight: 390 }}>{p.stocks.map((s) => <Pressable key={s.stock_code} onPress={() => p.onPickStock(s)} style={({ hovered }: { hovered?: boolean }) => [st.row, hovered && { backgroundColor: '#F7F7F8' }]}><StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={40} variant="web" /><View style={{ flex: 1 }}><Text style={st.rowB}>{s.name}</Text><Text style={st.rowS}>{s.market} · {s.stock_code}</Text></View><Text style={st.arrow}>›</Text></Pressable>)}</ScrollView></View>
      </Sheet>
    </>
  );
}

const st = StyleSheet.create({
  card: { minHeight: 170, borderRadius: 20, backgroundColor: '#17181C', padding: 22, flexDirection: 'row', alignItems: 'center', gap: 20 }, paper: { width: 150, height: 118, borderRadius: 16, backgroundColor: '#FCEAAA', padding: 18 }, paperLine: { width: 112, height: 8, marginBottom: 11, borderRadius: 4, backgroundColor: 'rgba(161,117,0,.24)' }, pencil: { position: 'absolute', right: 14, bottom: 10, fontSize: 31, color: '#A47B12' }, copy: { flex: 1 }, eyebrow: { ...fpx(12, 18), color: '#B9A7F4', fontWeight: '700' }, title: { ...fpx(20, 29), marginTop: 4, color: '#FFFFFF', fontWeight: '700' }, sub: { ...fpx(13, 20), marginTop: 5, color: '#B8BBC2' }, cta: { minWidth: 152, minHeight: 46, borderRadius: 13, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18 }, ctaT: { ...fpx(14, 21), color: '#15171A', fontWeight: '700' }, later: { position: 'absolute', right: 27, bottom: 15 }, laterT: { ...fpx(12, 18), color: '#8D929C' },
  guide: { borderRadius: 22, backgroundColor: '#FFFFFF', padding: 30, alignItems: 'center' }, guideIcon: { width: 62, height: 62, borderRadius: 20, backgroundColor: '#EEE9FB', alignItems: 'center', justifyContent: 'center' }, guideIconT: { fontSize: 28, color: '#6A42AB' }, guideTitle: { ...fpx(23, 32), marginTop: 18, color: '#191F28', fontWeight: '700' }, guideSub: { ...fpx(14, 22), marginTop: 8, color: '#6B7078', textAlign: 'center' }, guideCta: { width: '100%', height: 50, marginTop: 24, borderRadius: 14, backgroundColor: '#111111', alignItems: 'center', justifyContent: 'center' }, guideCtaT: { ...fpx(15, 23), color: '#FFFFFF', fontWeight: '700' }, guideSkip: { minHeight: 38, justifyContent: 'center' }, guideSkipT: { ...fpx(13, 20), color: '#8B95A1' },
  picker: { borderRadius: 22, backgroundColor: '#FFFFFF', padding: 24 }, pickerHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }, pickerTitle: { ...fpx(20, 29), color: '#191F28', fontWeight: '700' }, close: { ...fpx(13, 20), color: '#6B7078' }, row: { minHeight: 64, borderRadius: 12, paddingHorizontal: 8, flexDirection: 'row', alignItems: 'center', gap: 11 }, rowB: { ...fpx(14, 21), color: '#191F28', fontWeight: '700' }, rowS: { ...fpx(11, 16), marginTop: 2, color: '#9AA0AA' }, arrow: { fontSize: 25, color: '#9AA0AA' },
});
