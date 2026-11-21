import React, { useMemo } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Text, TextInput } from '@/components/ui/AppText';
import { BackGlyph, CheckGlyph } from '@/ui/screens/auth/AuthGlyphs';
import { Sheet } from '@/ui/shared/Sheet';
import { StockLogo } from '@/ui/shared/StockLogo';
import { fpx, webTracking } from '@/ui/theme';
import type { OnboardingFlowProps, OnboardingStock, StockStatus } from '../Onboarding.types';

export function WebOnboardingFlow(p: OnboardingFlowProps) {
  const q = p.query.trim().toLowerCase();
  const list = useMemo(() => p.stocks.filter((s) => !q || s.name.toLowerCase().includes(q) || s.stock_code.includes(q)), [p.stocks, q]);
  const picked = Object.keys(p.selected);
  if (p.step === 'setup') return <Setup onBack={p.onBack} onChoose={p.onChooseHome} />;
  if (p.step === 'ready') return null;
  return (
    <View style={st.screen}>
      <View style={st.card}>
        <View style={st.top}><Pressable onPress={p.onBack} style={st.back}><BackGlyph /></Pressable><View style={st.progress}><View style={[st.dot, st.dotOn]} /><View style={st.dot} /><View style={st.dot} /></View><Pressable onPress={p.onSkip} style={st.skip}><Text style={st.skipT}>건너뛰기</Text></Pressable></View>
        <Text style={st.title}>관심 있는 종목을 골라 주세요</Text>
        <Text style={st.sub}>여러 개를 골라도 괜찮아요. 선택한 종목은 홈과 메모 보드에 표시돼요.</Text>
        <View style={st.search}><Text style={st.searchIcon}>⌕</Text><TextInput value={p.query} onChangeText={p.onQueryChange} placeholder="종목명 또는 종목코드 검색" placeholderTextColor="#9AA0AA" style={st.input} accessibilityLabel="종목 검색" />{p.query ? <Pressable onPress={() => p.onQueryChange('')}><Text style={st.clear}>×</Text></Pressable> : null}</View>
        <ScrollView style={st.list} contentContainerStyle={st.grid} showsVerticalScrollIndicator={false}>
          {list.length ? list.map((s) => <Card key={s.stock_code} stock={s} value={p.selected[s.stock_code]} onToggle={() => p.onToggle(s.stock_code)} onStatus={(v) => p.onStatusChange(s.stock_code, v)} />) : <View style={st.empty}><Text style={st.emptyB}>‘{p.query}’ 종목을 찾지 못했어요</Text><Text style={st.emptyS}>검색어를 다시 확인해 주세요.</Text></View>}
        </ScrollView>
        <View style={st.foot}><Text style={st.count}>{picked.length ? `${picked.length}개 선택됨` : '종목을 하나 이상 선택해 주세요'}</Text><Pressable disabled={!picked.length} onPress={p.onOpenHolding} style={[st.cta, !!picked.length && st.ctaOn]}><Text style={st.ctaT}>다음</Text></Pressable></View>
      </View>
      <HoldingDialog {...p} />
    </View>
  );
}

function Card({ stock, value, onToggle, onStatus }: { stock: OnboardingStock; value?: StockStatus; onToggle: () => void; onStatus: (v: StockStatus) => void }) {
  return <View style={[st.stock, value && st.stockOn]}><Pressable onPress={onToggle} style={st.stockMain} accessibilityRole="checkbox" accessibilityState={{ checked: !!value }}><View style={[st.check, value && st.checkOn]}>{value ? <CheckGlyph /> : null}</View><StockLogo logo={stock.logo} bg={stock.logo_bg} ink={stock.logo_ink} size={38} variant="web" /><View style={{ flex: 1 }}><Text style={st.stockB} numberOfLines={1}>{stock.name}</Text><Text style={st.stockS}>{stock.market} · {stock.stock_code}</Text></View></Pressable>{value ? <View style={st.seg}>{(['holding', 'watching'] as const).map((v) => <Pressable key={v} onPress={() => onStatus(v)} style={[st.segBtn, value === v && st.segOn]}><Text style={[st.segT, value === v && st.segTOn]}>{v === 'holding' ? '보유' : '관심'}</Text></Pressable>)}</View> : null}</View>;
}

function HoldingDialog(p: OnboardingFlowProps) {
  const picked = p.stocks.filter((s) => p.selected[s.stock_code]);
  return <Sheet open={p.holding_open} onClose={p.onCloseHolding} width={520} label="보유 관심 확인"><View style={st.dialog}><View style={st.dialogHead}><View><Text style={st.dialogTitle}>보유·관심을 확인해 주세요</Text><Text style={st.dialogSub}>이 설정은 나중에 내 종목에서 바꿀 수 있어요.</Text></View><Pressable onPress={p.onCloseHolding}><Text style={st.close}>닫기</Text></Pressable></View><View style={st.dialogRows}>{picked.map((s) => <View key={s.stock_code} style={st.row}><StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={40} variant="web" /><View style={{ flex: 1 }}><Text style={st.rowB}>{s.name}</Text><Text style={st.rowS}>{s.stock_code}</Text></View><View style={st.seg}>{(['holding', 'watching'] as const).map((v) => <Pressable key={v} onPress={() => p.onStatusChange(s.stock_code, v)} style={[st.segBtn, p.selected[s.stock_code] === v && st.segOn]}><Text style={[st.segT, p.selected[s.stock_code] === v && st.segTOn]}>{v === 'holding' ? '보유' : '관심'}</Text></Pressable>)}</View><Pressable onPress={() => p.onRemove(s.stock_code)}><Text style={st.remove}>×</Text></Pressable></View>)}</View><Pressable onPress={() => { p.onCloseHolding(); p.onContinue(); }} style={[st.cta, st.ctaOn, { width: '100%' }]}><Text style={st.ctaT}>이대로 계속</Text></Pressable></View></Sheet>;
}

function Setup({ onBack, onChoose }: { onBack: () => void; onChoose: OnboardingFlowProps['onChooseHome'] }) {
  return <View style={st.screen}><View style={[st.card, st.setupCard]}><View style={st.top}><Pressable onPress={onBack} style={st.back}><BackGlyph /></Pressable><View style={st.progress}><View style={st.dot} /><View style={[st.dot, st.dotOn]} /><View style={st.dot} /></View><View style={st.skip} /></View><Text style={st.title}>홈 구성을 선택해 주세요</Text><Text style={st.sub}>바로 시작할 수도 있고, 원하는 위젯으로 직접 구성할 수도 있어요.</Text><View style={st.choices}><Choice title="기본 템플릿 적용" sub="시장 · 업데이트 · 뉴스를 알맞게 배치해 드려요" sample="시장 한눈에 보기  ·  종목별 업데이트" onPress={() => onChoose('template')} primary /><Choice title="직접 사용자화" sub="빈 홈에 원하는 위젯을 하나씩 추가해요" sample="＋  원하는 위젯 추가" onPress={() => onChoose('custom')} /></View></View></View>;
}

function Choice({ title, sub, sample, onPress, primary }: { title: string; sub: string; sample: string; onPress: () => void; primary?: boolean }) {
  return <Pressable onPress={onPress} style={({ hovered }: { hovered?: boolean }) => [st.choice, primary && st.choicePrimary, hovered && { transform: [{ translateY: -2 }] }]}><View style={[st.choicePreview, primary && st.choicePreviewOn]}><View style={st.miniLine} /><View style={st.miniBox}><Text style={st.miniText}>{sample}</Text></View><View style={st.miniRow}><View style={st.miniHalf} /><View style={st.miniHalf} /></View></View><Text style={st.choiceB}>{title}</Text><Text style={st.choiceS}>{sub}</Text><View style={[st.choiceBtn, primary && st.choiceBtnOn]}><Text style={[st.choiceBtnT, primary && { color: '#FFFFFF' }]}>선택하기</Text></View></Pressable>;
}

const st = StyleSheet.create({
  screen: { flex: 1, minHeight: 650, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FDFDFD', padding: 20 },
  card: { width: 760, maxWidth: '100%', height: 760, maxHeight: '94vh', borderRadius: 24, borderWidth: 1, borderColor: '#E5E8EB', backgroundColor: '#FFFFFF', paddingHorizontal: 56, paddingTop: 24, paddingBottom: 28 },
  top: { height: 42, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, back: { width: 42, height: 42, marginLeft: -10, alignItems: 'center', justifyContent: 'center' }, progress: { flexDirection: 'row', gap: 6 }, dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D5D8DD' }, dotOn: { width: 18, backgroundColor: '#111111' }, skip: { minWidth: 64, minHeight: 42, alignItems: 'flex-end', justifyContent: 'center' }, skipT: { ...fpx(14, 21), color: '#8B95A1', fontWeight: '600' },
  title: { ...fpx(28, 38), marginTop: 20, color: '#18181C', fontWeight: '700', letterSpacing: webTracking(28) }, sub: { ...fpx(14, 21), marginTop: 5, color: '#8B95A1' },
  search: { height: 46, marginTop: 20, borderRadius: 13, backgroundColor: '#F2F3F4', paddingHorizontal: 13, flexDirection: 'row', alignItems: 'center' }, searchIcon: { fontSize: 23, color: '#6B7078', transform: [{ rotate: '-20deg' }] }, input: { flex: 1, height: 46, marginLeft: 8, fontSize: 14, color: '#191F28' }, clear: { width: 28, fontSize: 23, textAlign: 'center', color: '#9AA0AA' },
  list: { flex: 1, marginTop: 16 }, grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, paddingBottom: 12 }, stock: { width: '32.2%', minHeight: 106, borderWidth: 1, borderColor: '#E5E8EB', borderRadius: 15, padding: 12, backgroundColor: '#FFFFFF' }, stockOn: { borderColor: '#9B87E8', backgroundColor: '#FBF8FF' }, stockMain: { flexDirection: 'row', alignItems: 'center', gap: 9 }, check: { position: 'absolute', right: 0, top: 0, width: 20, height: 20, borderRadius: 10, backgroundColor: '#E2E4E8', alignItems: 'center', justifyContent: 'center', zIndex: 2 }, checkOn: { backgroundColor: '#111111' }, stockB: { ...fpx(14, 20), paddingRight: 18, color: '#191F28', fontWeight: '700' }, stockS: { ...fpx(11, 16), marginTop: 2, color: '#9AA0AA' },
  seg: { flexDirection: 'row', alignSelf: 'flex-end', marginTop: 9, padding: 2, borderRadius: 8, backgroundColor: '#EDEEF1' }, segBtn: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6 }, segOn: { backgroundColor: '#FFFFFF' }, segT: { ...fpx(11, 16), color: '#8B95A1', fontWeight: '700' }, segTOn: { color: '#6A42AB' },
  empty: { width: '100%', paddingTop: 78, alignItems: 'center' }, emptyB: { ...fpx(16, 24), color: '#333840', fontWeight: '700' }, emptyS: { ...fpx(13, 20), marginTop: 5, color: '#9AA0AA' },
  foot: { height: 58, paddingTop: 10, borderTopWidth: 1, borderTopColor: '#ECEEF1', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, count: { ...fpx(13, 20), color: '#6B7078' }, cta: { width: 150, minHeight: 48, borderRadius: 14, backgroundColor: '#D0D3D9', alignItems: 'center', justifyContent: 'center' }, ctaOn: { backgroundColor: '#111111' }, ctaT: { ...fpx(15, 23), color: '#FFFFFF', fontWeight: '700' },
  dialog: { borderRadius: 22, backgroundColor: '#FFFFFF', padding: 26 }, dialogHead: { flexDirection: 'row', justifyContent: 'space-between' }, dialogTitle: { ...fpx(21, 30), color: '#191F28', fontWeight: '700' }, dialogSub: { ...fpx(13, 20), marginTop: 4, color: '#8B95A1' }, close: { ...fpx(13, 20), color: '#6B7078' }, dialogRows: { marginVertical: 18 }, row: { minHeight: 65, flexDirection: 'row', alignItems: 'center', gap: 10, borderBottomWidth: 1, borderBottomColor: '#F0F1F3' }, rowB: { ...fpx(14, 20), color: '#191F28', fontWeight: '700' }, rowS: { ...fpx(11, 16), color: '#9AA0AA' }, remove: { width: 24, fontSize: 22, color: '#9AA0AA', textAlign: 'center' },
  setupCard: { width: 860, height: 650 }, choices: { flexDirection: 'row', gap: 18, marginTop: 28 }, choice: { flex: 1, borderWidth: 1.5, borderColor: '#E5E8EB', borderRadius: 20, padding: 18 }, choicePrimary: { borderColor: '#B8A6EF', backgroundColor: '#FDFBFF' }, choicePreview: { height: 160, borderRadius: 14, backgroundColor: '#F5F6F8', padding: 16 }, choicePreviewOn: { backgroundColor: '#F1EDFC' }, miniLine: { width: 82, height: 8, borderRadius: 4, backgroundColor: '#C9CCD2' }, miniBox: { height: 54, marginTop: 12, borderRadius: 10, backgroundColor: '#FFFFFF', justifyContent: 'center', paddingHorizontal: 12 }, miniText: { ...fpx(11, 16), color: '#6B7078' }, miniRow: { flex: 1, flexDirection: 'row', gap: 8, marginTop: 8 }, miniHalf: { flex: 1, borderRadius: 8, backgroundColor: '#FFFFFF' }, choiceB: { ...fpx(18, 27), marginTop: 17, color: '#191F28', fontWeight: '700' }, choiceS: { ...fpx(13, 20), marginTop: 5, color: '#8B95A1' }, choiceBtn: { height: 44, marginTop: 18, borderRadius: 12, backgroundColor: '#EEF0F3', alignItems: 'center', justifyContent: 'center' }, choiceBtnOn: { backgroundColor: '#111111' }, choiceBtnT: { ...fpx(14, 21), color: '#333840', fontWeight: '700' },
});
