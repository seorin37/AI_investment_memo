import React, { useEffect, useMemo } from 'react';
import { BackHandler, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text, TextInput } from '@/components/ui/AppText';
import { BackGlyph, CheckGlyph } from '@/ui/screens/auth/AuthGlyphs';
import { Sheet } from '@/ui/shared/Sheet';
import { StockLogo } from '@/ui/shared/StockLogo';
import { appColor, ft } from '@/ui/theme';
import type { OnboardingFlowProps, OnboardingStock, StockStatus } from '../Onboarding.types';

export function AppOnboardingFlow(p: OnboardingFlowProps) {
  const insets = useSafeAreaInsets();
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (p.holding_open) p.onCloseHolding();
      else p.onBack();
      return true;
    });
    return () => sub.remove();
  }, [p]);
  if (p.step === 'setup') return <Setup top={insets.top} onBack={p.onBack} onChoose={p.onChooseHome} />;
  if (p.step === 'ready') return <Ready top={insets.top} bottom={insets.bottom} onFinish={p.onFinish} />;
  return <Pick {...p} top={insets.top} bottom={insets.bottom} />;
}

function Pick(p: OnboardingFlowProps & { top: number; bottom: number }) {
  const picked = Object.keys(p.selected);
  const q = p.query.trim().toLowerCase();
  const filtered = useMemo(() => p.stocks.filter((s) => !q || s.name.toLowerCase().includes(q) || s.stock_code.includes(q)), [p.stocks, q]);
  /* 3열 고정: 좌우 16 + 간격 9×2를 뺀 폭 (% 폭은 360에서 반올림으로 2열로 줄어듦) */
  const { width } = useWindowDimensions();
  const cardW = Math.floor((width - 32 - 18) / 3);
  return (
    <View style={[st.screen, { paddingTop: p.top }]}>
      <View style={st.top}>
        <Pressable onPress={p.onBack} style={st.back} accessibilityLabel="뒤로"><BackGlyph /></Pressable>
        <View style={st.progress}><View style={[st.dot, st.dotOn]} /><View style={st.dot} /><View style={st.dot} /></View>
        <Pressable onPress={p.onSkip} style={st.skip}><Text style={st.skipT}>건너뛰기</Text></Pressable>
      </View>
      <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 164 + p.bottom }}>
        <Text style={st.title}>관심 있는 종목을{String.fromCharCode(10)}골라 주세요</Text>
        <Text style={st.sub}>여러 개를 골라도 괜찮아요. 나중에도 바꿀 수 있어요.</Text>
        <View style={st.search}>
          <Text style={st.searchIcon}>⌕</Text>
          <TextInput value={p.query} onChangeText={p.onQueryChange} placeholder="종목명 또는 종목코드 검색" placeholderTextColor="#A4A8B3" style={st.input} returnKeyType="search" accessibilityLabel="종목 검색" />
          {p.query ? <Pressable onPress={() => p.onQueryChange('')} accessibilityLabel="검색어 지우기"><Text style={st.clear}>×</Text></Pressable> : null}
        </View>
        {filtered.length ? (
          <View style={st.grid}>{filtered.map((s) => <StockCard key={s.stock_code} stock={s} width={cardW} on={!!p.selected[s.stock_code]} onPress={() => p.onToggle(s.stock_code)} />)}</View>
        ) : (
          <View style={st.empty}><Text style={st.emptyB}>‘{p.query}’ 종목을 찾지 못했어요</Text><Text style={st.emptyS}>체험판에는 준비된 종목만 검색할 수 있어요.</Text></View>
        )}
      </ScrollView>
      <View style={[st.bottom, { paddingBottom: Math.max(14, p.bottom) }]}>
        {picked.length ? (
          <Pressable onPress={p.onOpenHolding} style={st.selectedBar}>
            <View style={st.stack}>{picked.slice(0, 4).map((code, i) => { const s = p.stocks.find((x) => x.stock_code === code)!; return <View key={code} style={{ marginLeft: i ? -8 : 0, zIndex: 4 - i }}><StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={30} variant="app" /></View>; })}</View>
            <Text style={st.selectedText}>{picked.length}개 선택 · 보유/관심 정하기</Text><Text style={st.chev}>›</Text>
          </Pressable>
        ) : null}
        <Pressable disabled={!picked.length} onPress={p.onContinue} style={[st.cta, !!picked.length && st.ctaOn]}><Text style={st.ctaT}>{picked.length ? `${picked.length}개 종목으로 계속` : '종목을 선택해 주세요'}</Text></Pressable>
      </View>
      <HoldingSheet {...p} />
    </View>
  );
}

function StockCard({ stock, width, on, onPress }: { stock: OnboardingStock; width: number; on: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="checkbox" accessibilityState={{ checked: on }} style={({ pressed }) => [st.stock, { width }, on && st.stockOn, pressed && { transform: [{ scale: 0.97 }] }]}>
      <View style={st.checkPos}><View style={[st.check, on && st.checkOn]}>{on ? <CheckGlyph /> : null}</View></View>
      <StockLogo logo={stock.logo} bg={stock.logo_bg} ink={stock.logo_ink} size={42} variant="app" />
      {/* 원본처럼 한 줄 + 말줄임 (글자 중간 줄바꿈 방지) */}
      <Text style={[st.stockName, { alignSelf: 'stretch', flexShrink: 1 }]} numberOfLines={1}>{stock.name}</Text>
      <Text style={st.stockMeta}>{stock.market}</Text>
    </Pressable>
  );
}

function HoldingSheet(p: OnboardingFlowProps) {
  const picked = p.stocks.filter((s) => p.selected[s.stock_code]);
  return (
    <Sheet open={p.holding_open} onClose={p.onCloseHolding} title="보유·관심 정하기" label="선택한 종목 보유 관심 설정">
      <ScrollView style={{ maxHeight: 420 }} contentContainerStyle={st.sheetBody}>
        <Text style={st.sheetSub}>선택한 종목이 내 종목에 어떻게 표시될지 정해 주세요.</Text>
        {picked.map((s) => <StatusRow key={s.stock_code} stock={s} value={p.selected[s.stock_code]} onChange={(v) => p.onStatusChange(s.stock_code, v)} onRemove={() => p.onRemove(s.stock_code)} />)}
      </ScrollView>
      <View style={st.sheetFoot}><Pressable onPress={p.onCloseHolding} style={[st.cta, st.ctaOn]}><Text style={st.ctaT}>확인</Text></Pressable></View>
    </Sheet>
  );
}

function StatusRow({ stock, value, onChange, onRemove }: { stock: OnboardingStock; value: StockStatus; onChange: (v: StockStatus) => void; onRemove: () => void }) {
  return (
    <View style={st.statusRow}>
      <StockLogo logo={stock.logo} bg={stock.logo_bg} ink={stock.logo_ink} size={40} variant="app" />
      <View style={st.statusName}><Text style={st.rowB}>{stock.name}</Text><Text style={st.rowS}>{stock.stock_code}</Text></View>
      <View style={st.seg}>{(['holding', 'watching'] as const).map((v) => <Pressable key={v} onPress={() => onChange(v)} style={[st.segBtn, value === v && st.segOn]}><Text style={[st.segT, value === v && st.segTOn]}>{v === 'holding' ? '보유' : '관심'}</Text></Pressable>)}</View>
      <Pressable onPress={onRemove} accessibilityLabel={`${stock.name} 선택 해제`}><Text style={st.remove}>×</Text></Pressable>
    </View>
  );
}

function Setup({ top, onBack, onChoose }: { top: number; onBack: () => void; onChoose: OnboardingFlowProps['onChooseHome'] }) {
  return (
    <View style={[st.screen, { paddingTop: top }]}>
      <View style={st.top}><Pressable onPress={onBack} style={st.back}><BackGlyph /></Pressable><View style={st.progress}><View style={st.dot} /><View style={[st.dot, st.dotOn]} /><View style={st.dot} /></View><View style={st.skip} /></View>
      <View style={st.setupBody}><Text style={st.title}>홈은 어떻게{String.fromCharCode(10)}시작할까요?</Text><Text style={st.sub}>기본 구성으로 바로 시작하거나, 직접 꾸밀 수 있어요.</Text>
        <Choice icon="✦" title="기본 템플릿 적용" sub="시장 · 업데이트 · 뉴스를 알맞게 배치해 드려요" onPress={() => onChoose('template')} primary />
        <Choice icon="⌘" title="직접 사용자화" sub="원하는 위젯을 골라 나만의 홈을 만들어요" onPress={() => onChoose('custom')} />
      </View>
    </View>
  );
}

function Choice({ icon, title, sub, onPress, primary }: { icon: string; title: string; sub: string; onPress: () => void; primary?: boolean }) {
  return <Pressable onPress={onPress} style={({ pressed }) => [st.choice, primary && st.choicePrimary, pressed && { transform: [{ scale: 0.98 }] }]}><View style={[st.choiceIcon, primary && st.choiceIconOn]}><Text style={[st.choiceIconT, primary && { color: '#FFFFFF' }]}>{icon}</Text></View><View style={{ flex: 1 }}><Text style={st.choiceB}>{title}</Text><Text style={st.choiceS}>{sub}</Text></View><Text style={st.choiceArrow}>›</Text></Pressable>;
}

function Ready({ top, bottom, onFinish }: { top: number; bottom: number; onFinish: () => void }) {
  return <View style={[st.ready, { paddingTop: top, paddingBottom: Math.max(bottom, 18) }]}><View style={st.readyMain}><View style={st.readyCheck}><Text style={st.readyCheckT}>✓</Text></View><Text style={st.readyTitle}>준비가 끝났어요!</Text><Text style={st.readySub}>이제 떠오른 생각을 메모로 남겨 보세요.{String.fromCharCode(10)}관련 소식은 AI가 계속 확인해 드릴게요.</Text></View><Pressable onPress={onFinish} style={[st.cta, st.ctaOn]}><Text style={st.ctaT}>내 홈으로 가기</Text></Pressable></View>;
}

const st = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#FFFFFF' }, top: { height: 62, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  back: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center', marginLeft: -10 }, progress: { flexDirection: 'row', gap: 6 }, dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D5D8DD' }, dotOn: { width: 18, backgroundColor: appColor.accent },
  skip: { minWidth: 64, minHeight: 44, alignItems: 'flex-end', justifyContent: 'center' }, skipT: { ...ft(14), color: '#8A8F98', fontWeight: '600' },
  title: { ...ft(27, 1.43), marginTop: 9, color: '#18181C', fontWeight: '800' }, sub: { ...ft(14, 1.5), marginTop: 7, color: '#9297A2' },
  search: { height: 48, marginTop: 22, borderRadius: 14, backgroundColor: '#F2F2F5', paddingHorizontal: 13, flexDirection: 'row', alignItems: 'center' }, searchIcon: { fontSize: 24, color: '#6E737D', transform: [{ rotate: '-20deg' }] }, input: { flex: 1, height: 48, paddingHorizontal: 9, color: '#18181C', fontSize: 15 }, clear: { width: 28, textAlign: 'center', fontSize: 24, color: '#9A9EA7' },
  grid: { marginTop: 16, flexDirection: 'row', flexWrap: 'wrap', gap: 9 }, stock: { minHeight: 126, borderRadius: 17, borderWidth: 1.5, borderColor: '#EAEBEE', paddingHorizontal: 10, paddingTop: 16, alignItems: 'center', backgroundColor: '#FFFFFF' }, stockOn: { borderColor: appColor.accent, backgroundColor: '#FBF9FF' }, checkPos: { position: 'absolute', top: 9, right: 9 }, check: { width: 20, height: 20, borderRadius: 10, backgroundColor: '#E0E2E7', alignItems: 'center', justifyContent: 'center' }, checkOn: { backgroundColor: appColor.accent }, stockName: { ...ft(13, 1.25), minHeight: 33, marginTop: 9, color: '#1B1C20', fontWeight: '700', textAlign: 'center' }, stockMeta: { ...ft(10), marginTop: 2, color: '#A4A8B3' },
  empty: { marginTop: 56, alignItems: 'center' }, emptyB: { ...ft(16), color: '#3F434A', fontWeight: '700' }, emptyS: { ...ft(13), marginTop: 8, color: '#9A9EA7' },
  bottom: { position: 'absolute', left: 0, right: 0, bottom: 0, padding: 16, paddingTop: 10, gap: 9, backgroundColor: '#FFFFFF', borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#ECEEF1' }, selectedBar: { height: 46, borderRadius: 14, backgroundColor: '#F2F2F5', paddingHorizontal: 12, flexDirection: 'row', alignItems: 'center' }, stack: { flexDirection: 'row' }, selectedText: { ...ft(13), flex: 1, marginLeft: 10, color: '#575B63', fontWeight: '700' }, chev: { fontSize: 24, color: '#8A8F98' },
  cta: { minHeight: 56, borderRadius: 16, backgroundColor: '#D0D3D9', alignItems: 'center', justifyContent: 'center' }, ctaOn: { backgroundColor: appColor.accent }, ctaT: { ...ft(17), color: '#FFFFFF', fontWeight: '800' },
  sheetBody: { paddingHorizontal: 22, paddingBottom: 8 }, sheetSub: { ...ft(13, 1.5), color: '#8A8F98', marginBottom: 7 }, statusRow: { minHeight: 66, flexDirection: 'row', alignItems: 'center', gap: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#E6E8EC' }, statusName: { flex: 1 }, rowB: { ...ft(14), color: '#1B1C20', fontWeight: '700' }, rowS: { ...ft(11), marginTop: 2, color: '#A4A8B3' }, seg: { flexDirection: 'row', backgroundColor: '#F1F2F4', borderRadius: 10, padding: 3 }, segBtn: { paddingHorizontal: 10, paddingVertical: 7, borderRadius: 8 }, segOn: { backgroundColor: '#FFFFFF' }, segT: { ...ft(12), color: '#8A8F98', fontWeight: '700' }, segTOn: { color: appColor.deepPurple }, remove: { width: 24, textAlign: 'center', fontSize: 22, color: '#A4A8B3' }, sheetFoot: { paddingHorizontal: 16, paddingTop: 10 },
  setupBody: { flex: 1, paddingHorizontal: 20 }, choice: { minHeight: 116, marginTop: 18, borderRadius: 21, borderWidth: 1.5, borderColor: '#E6E8EC', padding: 18, flexDirection: 'row', alignItems: 'center', gap: 14 }, choicePrimary: { borderColor: '#CFC3F5', backgroundColor: '#FCFAFF' }, choiceIcon: { width: 50, height: 50, borderRadius: 16, backgroundColor: '#F0F1F3', alignItems: 'center', justifyContent: 'center' }, choiceIconOn: { backgroundColor: appColor.accent }, choiceIconT: { fontSize: 23, color: '#575B63' }, choiceB: { ...ft(17), color: '#18181C', fontWeight: '800' }, choiceS: { ...ft(13, 1.45), marginTop: 5, color: '#8A8F98' }, choiceArrow: { fontSize: 28, color: '#9A9EA7' },
  ready: { flex: 1, backgroundColor: '#FFFFFF', paddingHorizontal: 16 }, readyMain: { flex: 1, alignItems: 'center', justifyContent: 'center' }, readyCheck: { width: 76, height: 76, borderRadius: 38, backgroundColor: '#EEE9FB', alignItems: 'center', justifyContent: 'center' }, readyCheckT: { fontSize: 38, color: appColor.accent, fontWeight: '800' }, readyTitle: { ...ft(27), marginTop: 24, color: '#18181C', fontWeight: '800' }, readySub: { ...ft(15, 1.6), marginTop: 12, color: '#757A84', textAlign: 'center' },
});
