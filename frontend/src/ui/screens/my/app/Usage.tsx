import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { useMotionK } from '@/ui/motion/useMotion';
import type { UsageProps } from '../My.types';
import type { TrackedStock } from '../My.mock';
import { Chev, Foot, Grp, Item, Lb, MC, Odometer, Page, Rv, UsageBar } from './parts';

/**
 * 앱 사용량 = 원본 app/my.html usageHTML()
 * (90% 이상 주의 · 100% 중단 안내) · 무료 플랜 카드(가정 · 예시 데이터 배지 · 큰 % · 막대 · 남은 사용량 · 다음 갱신)
 * 종목별 추적 현황(펼치기 · 첫 종목 열림 · 메모 + 칩) · 안내 · [플랜 살펴보기] · 안내
 */
export function AppUsage(p: UsageProps) {
  const pct = p.usage_pct;
  const st2 = pct >= 100 ? 'er' : pct >= 90 ? 'wn' : '';
  const total = p.tracked.reduce((a, t) => a + t.memos.length, 0);
  return (
    <Page title="사용량" lead="AI 업데이트에 쓰인 사용량을 확인해요." onBack={p.onBack}>
      {st2 ? (
        <Rv i={0}>
          <View style={[st.ban, st2 === 'er' ? st.banEr : st.banWn]}>
            <View style={[st.banDot, { backgroundColor: st2 === 'er' ? MC.red : '#E89A0C' }]} />
            <View style={{ flex: 1 }}>
              <Text style={[st.banB, { color: st2 === 'er' ? '#9A1C1C' : '#7A5300' }]}>{st2 === 'er' ? 'AI 업데이트가 일시 중단되었어요' : 'AI 사용량이 거의 다 찼어요'}</Text>
              <Text keepAll style={[st.banT, { color: st2 === 'er' ? '#9A1C1C' : '#7A5300' }]}>
                {st2 === 'er' ? 'AI 사용량을 모두 소진했어요. 메모 작성과 기존 기록 확인은 계속 이용할 수 있어요.' : `이번 기간 사용량의 ${pct}%를 썼어요. ${p.usage_renew}에 다시 채워져요.`}
              </Text>
            </View>
          </View>
        </Rv>
      ) : null}
      <Rv i={1}>
        <Grp style={st.plan}>
          <View style={st.planH}>
            <Text style={st.planHT}>{p.plan_name}</Text>
            <View style={st.ex}><Text style={st.exT}>가정</Text></View>
            <View style={[st.ex, { marginLeft: 'auto' }]}><Text style={st.exT}>예시 데이터</Text></View>
          </View>
          <View style={st.big}>
            <Odometer value={pct} size={30} lineHeight={38} />
            <Text style={st.bigT}>% 사용</Text>
          </View>
          <UsageBar pct={pct} delay={250} />
          <View style={st.m}>
            <Text style={[st.mT, { color: st2 === 'er' ? MC.red : MC.ink2 }]}>남은 사용량 {Math.max(0, 100 - pct)}%</Text>
            <Text style={[st.mT, { color: MC.ink3 }]}>다음 갱신 {p.usage_renew}</Text>
          </View>
        </Grp>
      </Rv>
      <Rv i={2}>
        <View style={st.lbRow}>
          <Lb style={{ flex: 1 }}>종목별 추적 현황</Lb>
          <Lb>{st2 === 'er' ? '추적 일시 중단' : `추적 항목 ${total}개`}</Lb>
        </View>
      </Rv>
      <Rv i={3}>
        <Grp>
          {p.tracked.filter((t) => t.memos.length).map((t, i, all) => <Acc key={t.stock_code} stock={t} first={i === 0} last={i === all.length - 1} onOpenMemo={p.onOpenMemo} />)}
        </Grp>
      </Rv>
      <Rv i={4}><Foot>AI 연결을 켠 메모만 분석하고, 연결하지 않은 메모는 분석하지 않아요. 항목을 누르면 그 메모가 열려요.</Foot></Rv>
      <Rv i={5}><Grp style={{ marginTop: 10 }}><Item two last title="플랜 살펴보기" sub="무료 · PLUS · PRO 비교" onPress={p.onPlans} /></Grp></Rv>
      <Rv i={6}><Foot>메모 작성과 기존 기록 확인은 사용량과 관계없이 이용할 수 있어요.</Foot></Rv>
    </Page>
  );
}

/* .acc: 머리(.sk2 로고 26 · 이름 15 700 · 'N개 추적 중 ⌄') · 펼치면 메모(.ti #F6F7F9 라운드 14 · 플러그 · 제목 14 · ›) + 칩 · .35s */
function Acc({ stock, first, last, onOpenMemo }: { stock: TrackedStock; first: boolean; last: boolean; onOpenMemo: UsageProps['onOpenMemo'] }) {
  const k = useMotionK();
  const [open, setOpen] = useState(first);
  const [h, setH] = useState(0);
  const [v] = useState(() => new Animated.Value(first ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: open ? 1 : 0, duration: 350 * k, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [open, k, v]);
  return (
    <View>
      <Pressable onPress={() => setOpen((o) => !o)} style={[st.sk2, (!last || open) && st.sk2Line]} accessibilityRole="button" accessibilityState={{ expanded: open }}>
        <View style={[st.lg0, { backgroundColor: stock.logo_bg }]}><Text style={st.lg0T}>{stock.logo}</Text></View>
        <Text style={st.sk2T}>{stock.name}</Text>
        <View style={st.sk2V}>
          <Text style={st.sk2VT}>{stock.memos.length}개 추적 중</Text>
          <Animated.View style={{ transform: [{ rotate: v.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '180deg'] }) }] }}>
            <Svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke={MC.ink3} strokeWidth={2.2} strokeLinecap="round"><Path d="M6 9l6 6 6-6" /></Svg>
          </Animated.View>
        </View>
      </Pressable>
      <Animated.View style={{ height: h ? v.interpolate({ inputRange: [0, 1], outputRange: [0, h] }) : open ? undefined : 0, overflow: 'hidden' }}>
        <View onLayout={(e) => setH(e.nativeEvent.layout.height)} style={{ position: h ? 'absolute' : 'relative', left: 0, right: 0 }}>
          {stock.memos.map((m) => (
            <Pressable key={m.title} onPress={() => onOpenMemo(stock.stock_code, m.title)} style={({ pressed }) => [st.ti, pressed && { opacity: 0.85 }]} accessibilityRole="button" accessibilityLabel={`${m.title} 메모 열기`}>
              <View style={st.tiB}>
                <Svg width={13} height={13} viewBox="0 0 24 24" fill="none"><Path d="M9 3V7M15 3V7" stroke="#6A42AB" strokeWidth={2.4} strokeLinecap="round" /><Path d="M6.5 7H17.5V11C17.5 12.46 16.92 13.86 15.89 14.89C14.86 15.92 13.46 16.5 12 16.5C10.54 16.5 9.14 15.92 8.11 14.89C7.08 13.86 6.5 12.46 6.5 11V7Z" fill="#6A42AB" /><Path d="M12 16.5V21" stroke="#6A42AB" strokeWidth={2.4} strokeLinecap="round" /></Svg>
                <Text style={st.tiT} numberOfLines={1}>{m.title}</Text>
                <Chev />
              </View>
              <View style={st.chips}>{m.chips.map((c) => <View key={c} style={st.chip}><Text style={st.chipT}>{c}</Text></View>)}</View>
            </Pressable>
          ))}
          <View style={{ height: 4 }} />
        </View>
      </Animated.View>
    </View>
  );
}

const st = StyleSheet.create({
  ban: { borderRadius: 16, paddingVertical: 12, paddingHorizontal: 14, marginBottom: 10, flexDirection: 'row', gap: 8, borderWidth: 1 },
  banWn: { backgroundColor: '#FFF6E0', borderColor: '#F5DFA6' },
  banEr: { backgroundColor: '#FFEEEE', borderColor: '#F7C7C7' },
  banDot: { width: 7, height: 7, borderRadius: 4, marginTop: 6 },
  banB: { fontSize: 13.5, lineHeight: 21, fontWeight: '700' },
  banT: { fontSize: 12.5, lineHeight: 19.4 },
  plan: { padding: 16 },
  planH: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  planHT: { fontSize: 14, lineHeight: 20, fontWeight: '700', color: MC.ink },
  ex: { backgroundColor: '#F1F2F4', borderRadius: 5, paddingVertical: 1, paddingHorizontal: 5 },
  exT: { fontSize: 11, lineHeight: 16, fontWeight: '700', color: MC.ink2 },
  big: { flexDirection: 'row', alignItems: 'flex-end', marginTop: 10, marginBottom: 2 },
  bigT: { fontSize: 30, lineHeight: 38, fontWeight: '800', color: MC.ink },
  m: { flexDirection: 'row', justifyContent: 'space-between' },
  mT: { fontSize: 12, lineHeight: 17 },
  lbRow: { flexDirection: 'row' },
  sk2: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 14, paddingHorizontal: 16 },
  sk2Line: { borderBottomWidth: 1, borderBottomColor: '#F1F2F4' },
  lg0: { width: 26, height: 26, borderRadius: 7, alignItems: 'center', justifyContent: 'center' },
  lg0T: { fontSize: 12, lineHeight: 16, fontWeight: '800', color: '#FFFFFF' },
  sk2T: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: MC.ink },
  sk2V: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 4 },
  sk2VT: { fontSize: 12.5, lineHeight: 18, fontWeight: '500', color: MC.ink3 },
  ti: { marginVertical: 8, marginHorizontal: 12, backgroundColor: '#F6F7F9', borderRadius: 14, paddingVertical: 12, paddingHorizontal: 14 },
  tiB: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  tiT: { flex: 1, fontSize: 14, lineHeight: 20, fontWeight: '700', color: MC.ink },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginTop: 8 },
  chip: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E6E8EC', borderRadius: 7, paddingVertical: 3, paddingHorizontal: 7 },
  chipT: { fontSize: 11.5, lineHeight: 16, color: MC.ink2 },
});
