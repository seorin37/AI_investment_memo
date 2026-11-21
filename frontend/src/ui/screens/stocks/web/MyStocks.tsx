import React, { useEffect, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { FixedFrame } from '@/ui/layout/web/FixedFrame';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { ConfirmDialog } from '@/ui/shared/ConfirmDialog';
import { ContextMenu, type MenuItem } from '@/ui/shared/ContextMenu';
import { WebSelectBar } from '@/ui/shared/SelectBar';
import { WebSnackbar } from '@/ui/shared/Snackbar';
import { StockLogo } from '@/ui/shared/StockLogo';
import { curve, fpx } from '@/ui/theme';
import type { Hold, MyStock, WebMyStocksProps } from '../MyStocks.types';
import { WebAddStockDialog } from './AddStockDialog';
import { useContextMenuDom } from './stocksDom.web';

type Hover = { pressed: boolean; hovered?: boolean };
type Tab = 'all' | Hold;
type Snack = { msg: string; undo?: () => void; check?: boolean; key: number };
const KO: Record<Hold, string> = { holding: '보유', watching: '관심' };
const josa = (w: string) => {
  const c = w.charCodeAt(w.length - 1);
  return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? '을' : '를';
};
let seq = 0;
const nextKey = () => ++seq;

/**
 * 웹 내 종목 (원본 web/src/screens/mine.tsx · 11.16 앱 통일)
 * 860 틀 · 제목 줄 [선택] [+ 종목 추가] · 전체 n · 보유 n · 관심 n (검은 알약) · 보유/관심 카드 · 줄(로고 36 · 이름 17 · 새 소식 · 메모·AI 연결 · 종가 · 등락 · ⋯)
 * 줄 우클릭·⋯ = 종목 메뉴(옮기기 · 기업정보 · 여러 개 선택 · 빼기) · 선택 모드 = 아래 검정 막대(보유로 · 관심으로 · 휴지통)
 */
export function WebMyStocks(p: WebMyStocksProps) {
  const [tab, setTab] = useState<Tab>('all');
  const [sel, setSel] = useState<Set<string> | null>(null);
  const [menu, setMenu] = useState<{ s: MyStock; at: { x: number; y: number } } | null>(null);
  const [ask, setAsk] = useState<MyStock[] | null>(null);
  const [snack, setSnack] = useState<Snack | null>(null);
  const [add, setAdd] = useState(false);
  const k = useMotionK();
  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack(null), 4000 * k);
    return () => clearTimeout(t);
  }, [snack, k]);
  const L = p.stocks;
  const groups = (['holding', 'watching'] as const).filter((g) => tab === 'all' || tab === g).map((g) => [g, L.filter((s) => s.status === g)] as const);
  const shown = groups.flatMap(([, l]) => l);
  const list = L.filter((s) => sel?.has(s.stock_code));
  const tog = (s: MyStock) =>
    setSel((x) => {
      const n = new Set(x ?? []);
      if (n.has(s.stock_code)) n.delete(s.stock_code);
      else n.add(s.stock_code);
      return n;
    });
  const move = (ls: MyStock[], h: Hold) => {
    p.onMove(
      ls.map((s) => s.stock_code),
      h,
    );
    setSnack({ msg: ls.length > 1 ? `${ls.length}개를 ${KO[h]} 종목으로 옮겼어요` : `${ls[0].name}${josa(ls[0].name)} ${KO[h]} 종목으로 바꿨어요`, check: true, key: nextKey() });
  };
  const remove = (ls: MyStock[]) => {
    const before = L;
    p.onRemove(ls.map((s) => s.stock_code));
    setSnack({ msg: ls.length > 1 ? `${ls.length}개 종목을 내 종목에서 뺐어요` : `${ls[0].name}${josa(ls[0].name)} 내 종목에서 뺐어요`, undo: () => (p.onRestore(before), setSnack(null)), key: nextKey() });
  };
  const menuItems = (s: MyStock): MenuItem[] => [
    { label: s.status === 'holding' ? '관심 종목으로 바꾸기' : '보유 종목으로 바꾸기', icon: 'move', run: () => move([s], s.status === 'holding' ? 'watching' : 'holding') },
    { label: '기업정보 보기', icon: 'info', run: () => p.onOpenCompany(s.stock_code) },
    { label: '여러 개 선택', icon: 'select', run: () => setSel(new Set([s.stock_code])) },
    '-',
    { label: '내 종목에서 빼기', icon: 'trash', danger: true, run: () => setAsk([s]) },
  ];
  const box = useContextMenuDom((code, at) => {
    const s = L.find((x) => x.stock_code === code);
    if (s && !sel) setMenu({ s, at });
  });
  const askMemo = ask ? ask.reduce((a, s) => a + s.memo_count, 0) : 0;
  const askAi = ask ? ask.reduce((a, s) => a + s.ai_count, 0) : 0;
  return (
    <View style={st.root}>
      <ScrollView style={st.flex} showsVerticalScrollIndicator={false}>
        <FixedFrame>
          <View style={st.page} ref={box}>
            <View style={st.head}>
              <View style={st.headL}>
                <Text style={st.title}>내 종목</Text>
                <Text style={st.sub}>관심을 둔 이유까지, 메모와 함께 보관해요</Text>
              </View>
              <View style={st.headR}>
                <Pressable onPress={() => setSel(sel ? null : new Set())} style={({ hovered }: Hover) => [st.btnW, hovered && { backgroundColor: '#F9F9F9' }]}>
                  <Text style={st.btnWT}>{sel ? '선택 끝내기' : '선택'}</Text>
                </Pressable>
                <Pressable onPress={() => setAdd(true)} style={({ hovered }: Hover) => [st.btnB, hovered && { backgroundColor: '#2A2A2A' }]}>
                  <Text style={st.btnBT}>＋ 종목 추가</Text>
                </Pressable>
              </View>
            </View>
            <View style={st.body}>
              <Tabs
                value={tab}
                onChange={setTab}
                items={[
                  ['all', `전체 ${L.length}`],
                  ['holding', `보유 ${L.filter((s) => s.status === 'holding').length}`],
                  ['watching', `관심 ${L.filter((s) => s.status === 'watching').length}`],
                ]}
              />
              {L.length === 0 ? (
                <View style={st.empty}>
                  <Text style={st.emptyB}>관심 있는 종목을 추가해 보세요</Text>
                  <Text style={st.emptyP}>종목마다 생각을 메모로 남기면, AI가 관련 공시·뉴스를 이어 붙여 드려요.</Text>
                  <Pressable onPress={() => setAdd(true)} style={st.emptyBtn}>
                    <Text style={st.emptyBtnT}>종목 추가</Text>
                  </Pressable>
                </View>
              ) : null}
              {groups
                .filter(([, l]) => l.length)
                .map(([g, l], gi) => (
                  <Appear key={g} i={gi} style={st.card}>
                    <View style={st.cardH}>
                      <Text style={st.cardHT}>{KO[g]}</Text>
                      <Text style={st.cardHS}>{l.length}종목</Text>
                    </View>
                    {l.map((s) => {
                      const up = (s.change_pct ?? 0) >= 0;
                      const on = !!sel?.has(s.stock_code);
                      return (
                        <View key={s.stock_code} {...({ dataSet: { mine: s.stock_code } } as object)}>
                          <Pressable onPress={() => (sel ? tog(s) : p.onOpenStock(s.stock_code))} accessibilityRole="button" style={({ hovered }: Hover) => [st.row, on ? { backgroundColor: '#F7F7F7' } : hovered ? { backgroundColor: '#F9F9F9' } : null]}>
                            {sel ? <Pick on={on} /> : null}
                            <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={36} variant="webSide" radius={10} />
                            <View style={st.flexMin}>
                              <View style={st.nmRow}>
                                <Text style={st.nm} numberOfLines={1}>
                                  {s.name}
                                </Text>
                                {s.new_count > 0 ? (
                                  <View style={st.nb}>
                                    <Text style={st.nbT}>{s.new_count}</Text>
                                  </View>
                                ) : null}
                              </View>
                              <Text style={st.meta}>
                                메모 {s.memo_count} · AI 연결 {s.ai_count}
                              </Text>
                            </View>
                            <View style={st.pr}>
                              <Text style={st.prB}>{s.price == null ? '—' : `${s.price.toLocaleString('ko-KR')}원`}</Text>
                              {s.change_pct == null ? null : (
                                <Text style={[st.prS, { color: up ? '#E5484D' : '#2F6BDB' }]}>
                                  {up ? '+' : ''}
                                  {s.change_pct.toFixed(2)}%
                                </Text>
                              )}
                              {s.as_of ? <Text style={[st.prS, { color: '#8B95A1' }]}>{`${s.as_of.slice(5, 7)}.${s.as_of.slice(8, 10)}`}</Text> : null}
                            </View>
                            {!sel ? (
                              <Pressable
                                accessibilityLabel={`${s.name} 메뉴`}
                                onPress={(e) => {
                                  const ne = e.nativeEvent as unknown as { pageX: number; pageY: number };
                                  setMenu({ s, at: { x: ne.pageX - 220, y: ne.pageY + 12 } });
                                }}
                                style={({ hovered }: Hover) => [st.dots, hovered && { backgroundColor: '#F2F3F4' }]}
                              >
                                <Svg width={18} height={18} viewBox="0 0 18 18" fill="#8B95A1">
                                  <Circle cx={4} cy={9} r={1.5} />
                                  <Circle cx={9} cy={9} r={1.5} />
                                  <Circle cx={14} cy={9} r={1.5} />
                                </Svg>
                              </Pressable>
                            ) : null}
                          </Pressable>
                        </View>
                      );
                    })}
                  </Appear>
                ))}
              <Text style={st.foot}>
                {p.as_of_mixed ? '시세는 종목별 종가 기준' : p.as_of ? `시세는 ${p.as_of.slice(5, 7)}.${p.as_of.slice(8, 10)} 종가 기준` : '시세 데이터가 아직 연결되지 않았어요'} · 종목을 우클릭하면 바로 옮기거나 뺄 수 있어요
              </Text>
            </View>
          </View>
        </FixedFrame>
        <View style={{ height: 96 }} />
      </ScrollView>
      <ContextMenu at={menu?.at ?? null} items={menu ? menuItems(menu.s) : []} onClose={() => setMenu(null)} />
      {sel ? (
        <View style={st.selBar} pointerEvents="box-none">
          <WebSelectBar
            n={sel.size}
            total={shown.length}
            all={sel.size === shown.length && shown.length > 0}
            onAll={() => setSel(sel.size === shown.length ? new Set() : new Set(shown.map((s) => s.stock_code)))}
            onTrash={() => {
              setAsk(list);
              setSel(null);
            }}
            onEnd={() => setSel(null)}
            extra={[
              { label: '보유로 옮기기', onPress: () => (move(list, 'holding'), setSel(null)) },
              { label: '관심으로 옮기기', onPress: () => (move(list, 'watching'), setSel(null)) },
            ]}
          />
        </View>
      ) : null}
      <WebAddStockDialog
        open={add}
        mine={L}
        universe={p.universe}
        popular={p.popular}
        onClose={() => setAdd(false)}
        onAdd={(c, h) => {
          p.onAdd(c, h);
          const n = p.universe.find((u) => u.stock_code === c)?.name ?? '';
          setSnack({ msg: `${n}${josa(n)} ${KO[h]} 종목에 추가했어요`, check: true, key: nextKey() });
        }}
      />
      <WebSnackbar visible={!!snack} message={snack?.msg ?? ''} onUndo={snack?.undo} check={snack?.check} style={st.snack} />
      <ConfirmDialog
        variant="web"
        danger
        open={!!ask}
        title={ask && ask.length > 1 ? `${ask.length}개 종목을 뺄까요?` : '내 종목에서 뺄까요?'}
        body={askMemo ? `메모 ${askMemo}개는 휴지통으로 옮겨져요. 휴지통에서 복원할 수 있어요.${askAi ? ` AI 연결된 메모 ${askAi}개는 추적이 멈춰요.` : ''}` : '휴지통에서 다시 복원할 수 있어요.'}
        confirmLabel="빼기"
        onCancel={() => setAsk(null)}
        onConfirm={() => {
          if (ask) remove(ask);
          setAsk(null);
        }}
      />
    </View>
  );
}

function Appear({ i, style, children }: { i: number; style?: object; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: 1, duration: 450 * k, delay: i * 70 * k, easing: curve.ease, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [v, i, k]);
  return <Animated.View style={[style, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) }] }]}>{children}</Animated.View>;
}

function Pick({ on }: { on: boolean }) {
  return on ? (
    <Svg width={22} height={22} viewBox="0 0 22 22" fill="none">
      <Circle cx={11} cy={11} r={11} fill="#111111" />
      <Path d="M6.8 11.2L9.6 14L15.2 8.2" stroke="white" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ) : (
    <Svg width={22} height={22} viewBox="0 0 22 22" fill="none">
      <Circle cx={11} cy={11} r={10} stroke="#C9CCD2" strokeWidth={1.6} />
    </Svg>
  );
}

/* 전체 · 보유 · 관심 (원본 x-pill 검은 알약) */
function Tabs({ value, onChange, items }: { value: Tab; onChange: (t: Tab) => void; items: [Tab, string][] }) {
  const k = useMotionK();
  const [lay, setLay] = useState<Partial<Record<Tab, { x: number; w: number }>>>({});
  const [x] = useState(() => new Animated.Value(0));
  const [w] = useState(() => new Animated.Value(0));
  const cur = lay[value];
  useEffect(() => {
    if (!cur) return;
    const a = Animated.parallel([Animated.timing(x, { toValue: cur.x, duration: 450 * k, easing: curve.spring, useNativeDriver: false }), Animated.timing(w, { toValue: cur.w, duration: 450 * k, easing: curve.spring, useNativeDriver: false })]);
    a.start();
    return () => a.stop();
  }, [cur, x, w, k]);
  return (
    <View style={st.tabs}>
      {cur ? <Animated.View style={[st.xpill, { left: x, width: w }]} /> : null}
      {items.map(([t, l]) => {
        const on = t === value;
        return (
          <Pressable
            key={t}
            onLayout={(e) => {
              const ly = e.nativeEvent.layout;
              setLay((o) => (o[t]?.x === ly.x && o[t]?.w === ly.width ? o : { ...o, [t]: { x: ly.x, w: ly.width } }));
            }}
            onPress={() => onChange(t)}
            style={[st.tab, !on && { backgroundColor: '#FFFFFF' }]}
          >
            {({ hovered }: Hover) => <Text style={[st.tabT, { color: on ? '#FFFFFF' : hovered ? '#191F28' : '#8F8F8F' }]}>{l}</Text>}
          </Pressable>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1 },
  flex: { flex: 1 },
  flexMin: { flex: 1, minWidth: 0 },
  page: { width: 860, gap: 32, paddingTop: 32, paddingBottom: 40 },
  head: { width: '100%', paddingTop: 24, flexDirection: 'row', gap: 16 },
  headL: { height: 52, flex: 1, minWidth: 0, gap: 4 },
  title: { ...fpx(26, 35), fontWeight: '700', letterSpacing: -0.26, color: '#16171A' },
  sub: { ...fpx(14, 21), color: '#575B63' },
  headR: { position: 'absolute', right: 0, top: 25, flexDirection: 'row', alignItems: 'center', gap: 8 },
  btnW: { borderRadius: 999, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFFFFF', paddingHorizontal: 12, paddingVertical: 6 },
  btnWT: { ...fpx(13, 20), fontWeight: '700', color: '#15171A' },
  btnB: { borderRadius: 999, backgroundColor: '#15171A', paddingHorizontal: 12, paddingVertical: 6 },
  btnBT: { ...fpx(13, 20), fontWeight: '700', color: '#FFFFFF' },
  body: { width: '100%', gap: 24 },
  tabs: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  xpill: { position: 'absolute', top: 0, bottom: 0, borderRadius: 999, backgroundColor: '#111111' },
  tab: { borderRadius: 20, paddingHorizontal: 16, paddingVertical: 8 },
  tabT: { ...fpx(13, 20), fontWeight: '500' },
  empty: { width: '100%', alignItems: 'center', gap: 12, borderRadius: 20, borderWidth: 1, borderStyle: 'dashed', borderColor: '#CFD3D9', backgroundColor: '#FFFFFF', paddingHorizontal: 32, paddingVertical: 48 },
  emptyB: { ...fpx(22, 31), fontWeight: '700', color: '#191F28', textAlign: 'center' },
  emptyP: { ...fpx(15, 23), color: '#6B7684', textAlign: 'center' },
  emptyBtn: { marginTop: 8, height: 48, borderRadius: 14, backgroundColor: '#111111', paddingHorizontal: 24, justifyContent: 'center' },
  emptyBtnT: { ...fpx(17, 24), fontWeight: '700', color: '#FFFFFF' },
  card: { width: '100%', overflow: 'hidden', borderRadius: 20, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFFFFF' },
  cardH: { height: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20 },
  cardHT: { ...fpx(15, 20), fontWeight: '700', color: '#15171A' },
  cardHS: { ...fpx(13, 20), color: '#8B95A1' },
  row: { height: 72, flexDirection: 'row', alignItems: 'center', gap: 16, borderTopWidth: 1, borderTopColor: '#F0F1F3', paddingHorizontal: 20 },
  nmRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  nm: { flexShrink: 1, ...fpx(17, 26), fontWeight: '700', color: '#15171A' },
  nb: { minWidth: 20, height: 20, borderRadius: 10, backgroundColor: '#E5484D', paddingHorizontal: 5, alignItems: 'center', justifyContent: 'center' },
  nbT: { fontSize: 12, lineHeight: 14, fontWeight: '700', color: '#FFFFFF' },
  meta: { ...fpx(13, 20), color: '#8B95A1' },
  pr: { alignItems: 'flex-end' },
  prB: { ...fpx(15, 23), fontWeight: '700', color: '#15171A' },
  prS: { ...fpx(13, 20), fontWeight: '700' },
  dots: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  foot: { textAlign: 'center', ...fpx(13, 20), color: '#8B95A1' },
  selBar: { position: 'absolute', left: 0, right: 0, bottom: 28, alignItems: 'center' },
  snack: { position: 'absolute', bottom: 30 },
});
