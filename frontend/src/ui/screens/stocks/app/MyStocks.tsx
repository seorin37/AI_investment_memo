import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Animated, BackHandler, PanResponder, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path, Rect } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { Odometer } from '@/ui/motion/Numbers';
import { Reveal } from '@/ui/motion/Reveal';
import { Skeleton } from '@/ui/motion/Skeleton';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { ConfirmDialog } from '@/ui/shared/ConfirmDialog';
import { AppSnackbar } from '@/ui/shared/Snackbar';
import { StockLogo } from '@/ui/shared/StockLogo';
import { appColor, curve, ft } from '@/ui/theme';
import type { AppMyStocksProps, Hold, MyStock } from '../MyStocks.types';
import { AddStockSheet } from './AddStockSheet';
import { Check13, Grip, HOLD_BG, HoldIcon, TrashIcon } from './stockGlyphs';

type Filter = 'all' | Hold;
type Snack = { msg: string; action?: { label: string; onPress: () => void }; undo?: () => void; key: number };
type Drag = { code: string; group: string[]; from: number; to: number };
let seq = 0;
const nextKey = () => ++seq;
const KO: Record<Hold, string> = { holding: '보유', watching: '관심' };
const josa = (w: string) => {
  const c = w.charCodeAt(w.length - 1);
  return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? '을' : '를';
};
const won = (n: number) => `${n.toLocaleString('ko-KR')}원`;

/**
 * 앱 내 종목 탭 (원본 stock.html · 11.11 · 11.17 웹 통일)
 * 전체·보유·관심 칩(보라 알약) · [+ 종목 추가] 시트 · 보유/관심 묶음 · 종목 줄(로고 · 이름 · 새 소식 · 메모·AI 연결 · 종가 · 등락)
 * 꾹 누르기 = 선택 모드: 위 '✕ N개 선택 · 전체 선택', 아래 탭바 자리 [보유로 옮기기 · 관심으로 옮기기 · 내 종목에서 빼기], 줄 오른쪽 ⋮⋮ 로 묶음 안 순서.
 * 원본에 줄 밀기는 없음 (꾹 누르기 선택 모드가 그 역할).
 */
export function AppMyStocks(p: AppMyStocksProps) {
  const k = useMotionK();
  const insets = useSafeAreaInsets();
  const [filt, setFilt] = useState<Filter>('all');
  const [ready, setReady] = useState(false);
  const [sel, setSel] = useState<Set<string> | null>(null);
  const [add, setAdd] = useState(false);
  const [ask, setAsk] = useState<string[] | null>(null);
  const [snack, setSnack] = useState<Snack | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [dragY] = useState(() => new Animated.Value(0));
  const [fresh, setFresh] = useState<string[]>([]);
  const L = p.stocks;
  const count = (h: Hold) => L.filter((s) => s.status === h).length;

  useEffect(() => {
    const t = setTimeout(() => setReady(true), 800 * k);
    return () => clearTimeout(t);
  }, [k]);
  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack(null), (snack.undo || snack.action ? 5000 : 2200) * k);
    return () => clearTimeout(t);
  }, [snack, k]);
  const { onSelectionChange } = p;
  useEffect(() => {
    onSelectionChange?.(sel ? sel.size || 1 : 0);
  }, [sel, onSelectionChange]);
  useEffect(() => {
    if (!sel) return;
    const s = BackHandler.addEventListener('hardwareBackPress', () => {
      setSel(null);
      return true;
    });
    return () => s.remove();
  }, [sel]);
  useEffect(() => {
    if (!fresh.length) return;
    const t = setTimeout(() => setFresh([]), 2200 * k);
    return () => clearTimeout(t);
  }, [fresh, k]);

  /* ⋮⋮ 순서 (원본 #317: 4px 넘게 움직이면 끌기 · 지나간 줄은 .6s 비켜 줌 · 놓으면 그 자리로 날아가 앉음) */
  const commit = useRef<(code: string, group: string[], to: number) => void>(() => {});
  useEffect(() => {
    commit.current = (code, group, to) => {
      const next = group.filter((c) => c !== code);
      next.splice(to, 0, code);
      const inG = new Set(group);
      let i = 0;
      p.onReorder(L.map((s) => (inG.has(s.stock_code) ? next[i++] : s.stock_code)));
    };
  });
  const api = useMemo(() => {
    const s = { code: '', group: [] as string[], from: -1, to: -1, step: 76, started: false };
    return {
      setStep: (h: number) => {
        s.step = h + 8;
      },
      start: (code: string, group: string[]) => {
        s.code = code;
        s.group = group;
        s.from = group.indexOf(code);
        s.to = s.from;
        s.started = false;
        dragY.setValue(0);
      },
      move: (dy: number) => {
        if (!s.started) {
          if (Math.abs(dy) < 4) return;
          s.started = true;
          setDrag({ code: s.code, group: s.group, from: s.from, to: s.from });
        }
        dragY.setValue(dy);
        const to = Math.max(0, Math.min(s.group.length - 1, Math.round((s.from * s.step + dy) / s.step)));
        if (to !== s.to) {
          s.to = to;
          setDrag((d) => (d ? { ...d, to } : d));
        }
      },
      end: () => {
        if (!s.started) return;
        const { code, group, from, to } = s;
        Animated.timing(dragY, { toValue: (to - from) * s.step, duration: 600 * k, easing: curve.fly, useNativeDriver: NATIVE }).start(() => {
          setDrag(null);
          if (from !== to) commit.current(code, group, to);
          else dragY.setValue(0);
        });
      },
    };
  }, [dragY, k]);
  const orderKey = L.map((s) => s.stock_code).join(',');
  useLayoutEffect(() => {
    dragY.setValue(0);
  }, [orderKey, dragY]);

  const show = (s: Omit<Snack, 'key'>) => setSnack({ ...s, key: nextKey() });
  const toggle = (c: string) =>
    setSel((x) => {
      const n = new Set(x ?? []);
      if (n.has(c)) n.delete(c);
      else n.add(c);
      return n.size ? n : null;
    });
  const move = (to: Hold) => {
    if (!sel) return;
    const snap = L;
    const moved = [...sel].filter((c) => L.find((s) => s.stock_code === c)?.status !== to);
    setSel(null);
    if (filt !== 'all') setFilt('all');
    if (!moved.length) return;
    p.onMove(moved, to);
    setFresh(moved);
    const one = L.find((s) => s.stock_code === moved[0]);
    show({ msg: `${moved.length === 1 && one ? one.name + josa(one.name) : moved.length + '개를'} ${KO[to]} 종목으로 옮겼어요`, undo: () => (p.onRestore(snap), setSnack(null)) });
  };
  const remove = (cs: string[]) => {
    const snap = L;
    const one = L.find((s) => s.stock_code === cs[0]);
    p.onRemove(cs);
    show({ msg: `${cs.length === 1 && one ? one.name + josa(one.name) : cs.length + '개 종목을'} 내 종목에서 뺐어요`, undo: () => (p.onRestore(snap), setSnack(null)) });
  };
  const askList = ask ? L.filter((s) => ask.includes(s.stock_code)) : [];
  const memoN = askList.reduce((a, s) => a + s.memo_count, 0);
  const aiN = askList.reduce((a, s) => a + s.ai_count, 0);
  const types = sel ? [...sel].map((c) => L.find((s) => s.stock_code === c)?.status) : [];

  return (
    <View style={st.root}>
      {p.header({ onSearch: () => setAdd(true) })}
      {/* 선택 머리 (원본 .selh: 위 바 자리로 내려옴) */}
      {sel ? (
        <Reveal rise={-8} style={[st.selh, { top: insets.top }]}>
          <Pressable onPress={() => setSel(null)} accessibilityRole="button" accessibilityLabel="선택 끝내기" style={st.ib}>
            <Svg width={22} height={22} viewBox="0 0 24 24" stroke="#16171A" strokeWidth={2.2} strokeLinecap="round">
              <Path d="M6 6l12 12M18 6 6 18" />
            </Svg>
          </Pressable>
          <Text style={st.selhT}>{sel.size}개 선택</Text>
          <Pressable onPress={() => setSel(sel.size === L.length ? null : new Set(L.map((s) => s.stock_code)))} accessibilityRole="button" style={st.all}>
            <Text style={st.allT}>{sel.size === L.length ? '전체 해제' : '전체 선택'}</Text>
          </Pressable>
        </Reveal>
      ) : null}
      <ScrollView style={st.flex} contentContainerStyle={{ paddingBottom: 30 + (sel ? 80 + insets.bottom : 0) }} stickyHeaderIndices={L.length ? [1] : undefined} scrollEnabled={!drag} showsVerticalScrollIndicator={false}>
        <Text style={st.sub}>관심을 둔 이유까지, 메모와 함께 보관해요</Text>
        {L.length ? (
          <View>
            {/* 끈적이 머리는 자기 style 을 바깥 틀로 옮겨서, 줄 배치는 안쪽 View 에 */}
            <View style={st.chips}>
            <FilterChips value={filt} onChange={setFilt} holding={count('holding')} watching={count('watching')} />
            <Pressable onPress={() => setAdd(true)} accessibilityRole="button" style={({ pressed }) => [st.addc, pressed && { transform: [{ scale: 0.94 }] }]}>
              <Svg width={15} height={15} viewBox="0 0 24 24" stroke="#16171A" strokeWidth={2.2} strokeLinecap="round">
                <Path d="M12 5v14M5 12h14" />
              </Svg>
              <Text style={st.addcT}>종목 추가</Text>
            </Pressable>
            </View>
          </View>
        ) : (
          <View />
        )}
        {!L.length ? (
          <Reveal style={st.empty}>
            <View style={st.ill}>
              <Svg width={30} height={30} viewBox="0 0 24 24" fill="none" stroke="#7356D6" strokeWidth={1.8}>
                <Rect x={3} y={7} width={18} height={13} rx={2.5} />
                <Path d="M9 7V5h6v2M8 16v-3M12 16v-5M16 16v-2" />
              </Svg>
            </View>
            <Text style={st.emptyB}>관심 있는 종목을 추가해 보세요</Text>
            <Text style={st.emptyP}>{'종목마다 생각을 메모로 남기면,\nAI가 관련 공시·뉴스를 이어 붙여 드려요'}</Text>
            <Pressable onPress={() => setAdd(true)} accessibilityRole="button" style={({ pressed }) => [st.btn, pressed && { transform: [{ scale: 0.95 }] }]}>
              <Svg width={16} height={16} viewBox="0 0 24 24" stroke="#FFFFFF" strokeWidth={2.4} strokeLinecap="round">
                <Path d="M12 5v14M5 12h14" />
              </Svg>
              <Text style={st.btnT}>종목 추가</Text>
            </Pressable>
            <Text style={st.emptyS}>코스피 종목을 이름이나 코드로 찾을 수 있어요</Text>
          </Reveal>
        ) : !ready ? (
          [1, 2].map((n) => (
            <View key={n} style={st.grp}>
              <View style={st.gh}>
                <Skeleton style={{ width: 30, height: 30 }} radius={9} />
                <Skeleton style={{ width: 44, height: 16 }} />
              </View>
              {Array.from({ length: n }, (_, i) => (
                <View key={i} style={[st.sr, { gap: 12 }]}>
                  <Skeleton style={{ width: 36, height: 36 }} radius={10} />
                  <View style={{ flex: 1, gap: 6 }}>
                    <Skeleton style={{ width: '46%', height: 14 }} />
                    <Skeleton style={{ width: '30%', height: 11 }} />
                  </View>
                  <Skeleton style={{ width: 64, height: 14 }} />
                </View>
              ))}
            </View>
          ))
        ) : (
          <>
            {(['holding', 'watching'] as const).map((g, gi) => {
              if (filt !== 'all' && filt !== g) return null;
              const rows = L.filter((s) => s.status === g);
              const codes = rows.map((s) => s.stock_code);
              return (
                <Reveal key={g} i={gi} style={st.grp}>
                  <View style={st.gh}>
                    <View style={[st.gi, { backgroundColor: HOLD_BG[g] }]}>
                      <HoldIcon h={g} />
                    </View>
                    <Text style={st.ghT}>{KO[g]}</Text>
                    <Text style={st.ghS}>{rows.length}종목</Text>
                  </View>
                  {rows.length ? (
                    rows.map((s, i) => {
                      const d = drag && drag.group.includes(s.stock_code) ? drag : null;
                      const me = d?.code === s.stock_code;
                      const off = d && !me ? (d.from < d.to && i > d.from && i <= d.to ? -1 : d.from > d.to && i >= d.to && i < d.from ? 1 : 0) : 0;
                      return (
                        <StockRow
                          key={s.stock_code}
                          s={s}
                          sel={sel}
                          on={!!sel?.has(s.stock_code)}
                          fresh={fresh.includes(s.stock_code)}
                          lifted={me}
                          dragY={dragY}
                          shift={off}
                          group={codes}
                          api={api}
                          onPress={() => (sel ? toggle(s.stock_code) : p.onOpenStock(s.stock_code))}
                          onLongPress={() => !sel && setSel(new Set([s.stock_code]))}
                        />
                      );
                    })
                  ) : (
                    <Text style={st.none}>아직 {KO[g]} 종목이 없어요</Text>
                  )}
                </Reveal>
              );
            })}
            <Text style={st.foot2}>{p.as_of_mixed ? '시세는 종목별 종가 기준' : p.as_of ? `시세는 ${p.as_of.slice(5, 7)}.${p.as_of.slice(8, 10)} 종가 기준` : '시세 데이터가 아직 연결되지 않았어요'}</Text>
            <Text style={st.hint2}>종목을 꾹 누르면 여러 개를 옮기거나 빼고, ⋮⋮를 끌어 순서를 바꿀 수 있어요</Text>
          </>
        )}
      </ScrollView>

      {/* 선택 동작 막대 (원본 .abar: 탭바 자리 80) */}
      {sel ? (
        <View style={[st.abar, { height: 80 + insets.bottom, paddingBottom: 14 + insets.bottom }]}>
          <Pressable disabled={!types.includes('watching')} onPress={() => move('holding')} accessibilityRole="button" style={[st.ab, !types.includes('watching') && st.abDis]}>
            <HoldIcon h="holding" size={22} />
            <Text style={st.abT}>보유로 옮기기</Text>
          </Pressable>
          <Pressable disabled={!types.includes('holding')} onPress={() => move('watching')} accessibilityRole="button" style={[st.ab, !types.includes('holding') && st.abDis]}>
            <HoldIcon h="watching" size={22} />
            <Text style={st.abT}>관심으로 옮기기</Text>
          </Pressable>
          <Pressable onPress={() => setAsk([...sel])} accessibilityRole="button" style={st.ab}>
            <TrashIcon />
            <Text style={[st.abT, { color: appColor.red }]}>내 종목에서 빼기</Text>
          </Pressable>
        </View>
      ) : null}
      <AppSnackbar visible={!!snack} message={snack?.msg ?? ''} onUndo={snack?.undo} action={snack?.action} style={[st.snack, { bottom: sel ? 96 + insets.bottom : 16 }]} />
      <ConfirmDialog
        variant="app"
        danger
        open={!!ask}
        title={`${askList.length === 1 ? askList[0].name + josa(askList[0].name) : '종목 ' + askList.length + '개를'} 내 종목에서 뺄까요?`}
        body={`메모 ${memoN}개는 휴지통으로 옮겨져요. 휴지통에서 복원할 수 있어요.${aiN ? `\nAI 연결된 메모 ${aiN}개는 추적이 멈춰요.` : ''}`}
        confirmLabel="빼기"
        onCancel={() => setAsk(null)}
        onConfirm={() => {
          const cs = ask ?? [];
          setAsk(null);
          setSel(null);
          remove(cs);
        }}
      />
      <AddStockSheet
        open={add}
        mine={L}
        universe={p.universe}
        popular={p.popular}
        onClose={() => setAdd(false)}
        onAdd={(c, h) => {
          if (filt !== 'all' && filt !== h) setFilt('all');
          p.onAdd(c, h);
          setFresh([c]);
          const n = p.universe.find((u) => u.stock_code === c)?.name ?? '';
          show({ msg: `${n}${josa(n)} ${KO[h]} 종목에 추가했어요`, action: { label: '메모 쓰기', onPress: () => (setSnack(null), p.onWriteMemo(c)) } });
        }}
      />
    </View>
  );
}

/* 전체 · 보유 n · 관심 n (원본 .cw: 보라 알약 .32s 반동) */
function FilterChips({ value, onChange, holding, watching }: { value: Filter; onChange: (f: Filter) => void; holding: number; watching: number }) {
  const k = useMotionK();
  const [lay, setLay] = useState<Partial<Record<Filter, { x: number; w: number }>>>({});
  const [x] = useState(() => new Animated.Value(0));
  const [w] = useState(() => new Animated.Value(0));
  const cur = lay[value];
  useEffect(() => {
    if (!cur) return;
    const a = Animated.parallel([Animated.timing(x, { toValue: cur.x, duration: 320 * k, easing: curve.spring, useNativeDriver: false }), Animated.timing(w, { toValue: cur.w, duration: 320 * k, easing: curve.spring, useNativeDriver: false })]);
    a.start();
    return () => a.stop();
  }, [cur, x, w, k]);
  const items: [Filter, string, number | null][] = [
    ['all', '전체', null],
    ['holding', '보유', holding],
    ['watching', '관심', watching],
  ];
  return (
    <View style={st.cw}>
      {cur ? <Animated.View style={[st.cpl, { left: x, width: w }]} /> : null}
      {items.map(([f, l, n]) => {
        const on = f === value;
        return (
          <Pressable
            key={f}
            onLayout={(e) => {
              const { x: lx, width } = e.nativeEvent.layout;
              setLay((o) => (o[f]?.x === lx && o[f]?.w === width ? o : { ...o, [f]: { x: lx, w: width } }));
            }}
            onPress={() => onChange(f)}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            style={({ pressed }) => [st.chip, on && st.chipOn, pressed && { transform: [{ scale: 0.94 }] }]}
          >
            <Text style={[st.chipT, on && st.chipTOn]}>{l}</Text>
            {n !== null ? <Odometer value={n} style={on ? st.chipNOn : st.chipN} /> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

type DragApi = { setStep: (h: number) => void; start: (code: string, group: string[]) => void; move: (dy: number) => void; end: () => void };

function StockRow({ s, sel, on, fresh, lifted, dragY, shift, group, api, onPress, onLongPress }: { s: MyStock; sel: Set<string> | null; on: boolean; fresh: boolean; lifted: boolean; dragY: Animated.Value; shift: number; group: string[]; api: DragApi; onPress: () => void; onLongPress: () => void }) {
  const k = useMotionK();
  const [h, setH] = useState(68);
  const [sv] = useState(() => new Animated.Value(0));
  /* 선택 모드 들어가면 체크 동그라미·손잡이가 밀려 나옴 (.3s) */
  const [selV] = useState(() => new Animated.Value(sel ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(sv, { toValue: shift * (h + 8), duration: 600 * k, easing: curve.fly, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [shift, h, sv, k]);
  useEffect(() => {
    const a = Animated.timing(selV, { toValue: sel ? 1 : 0, duration: 300 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [sel, selV, k]);
  const groupKey = group.join(',');
  /* 손잡이: 터치 시작부터 잡음 (선택 모드에 막 들어온 뒤 첫 끌기도 바로) */
  const pan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onStartShouldSetPanResponderCapture: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: () => api.start(s.stock_code, groupKey.split(',')),
        onPanResponderMove: (_, g) => api.move(g.dy),
        onPanResponderRelease: () => api.end(),
        onPanResponderTerminate: () => api.end(),
        onPanResponderTerminationRequest: () => false,
      }),
    [api, s.stock_code, groupKey],
  );
  const up = (s.change_pct ?? 0) >= 0;
  return (
    <Animated.View
      onLayout={(e) => {
        setH(e.nativeEvent.layout.height);
        api.setStep(e.nativeEvent.layout.height);
      }}
      style={[{ zIndex: lifted ? 6 : 0, transform: [{ translateY: lifted ? dragY : sv }, { scale: lifted ? 1.03 : 1 }] }, lifted && st.lift]}
    >
      <Pressable onPress={onPress} onLongPress={onLongPress} delayLongPress={480} accessibilityRole="button" accessibilityState={{ selected: on }} style={({ pressed }) => [st.sr, on && st.srOn, fresh && st.srNew, lifted && { backgroundColor: '#FFFFFF' }, pressed && !sel && { transform: [{ scale: 0.975 }], backgroundColor: '#ECEDF1' }]}>
        <Animated.View style={[st.sck, on && st.sckOn, { width: selV.interpolate({ inputRange: [0, 1], outputRange: [0, 24] }), marginRight: selV.interpolate({ inputRange: [0, 1], outputRange: [-12, 0] }), borderWidth: selV.interpolate({ inputRange: [0, 1], outputRange: [0, 2] }) }]}>
          {on ? <Check13 /> : null}
        </Animated.View>
        <StockLogo logo={s.logo} bg={s.logo_bg} ink={s.logo_ink} size={36} variant="app" />
        <View style={st.nm}>
          <View style={st.nmRow}>
            <Text style={st.nmB} numberOfLines={1}>
              {s.name}
            </Text>
            {s.new_count ? (
              <View style={st.bdg}>
                <Text style={st.bdgT}>{s.new_count}</Text>
              </View>
            ) : null}
          </View>
          <Text style={st.nmS} numberOfLines={1}>
            메모 {s.memo_count} · {s.ai_ready ? `AI 연결 ${s.ai_count}` : 'AI 연결 준비 중'}
          </Text>
        </View>
        <View style={st.pr}>
          <Text style={st.prB}>{s.price == null ? '—' : won(s.price)}</Text>
          {s.change_pct == null ? null : (
            <Text style={[st.prS, { color: up ? appColor.up : appColor.down }]}>
              {up ? '+' : ''}
              {s.change_pct.toFixed(2)}%
            </Text>
          )}
          {s.as_of ? <Text style={[st.prS, { color: appColor.ink3 }]}>{`${s.as_of.slice(5, 7)}.${s.as_of.slice(8, 10)}`}</Text> : null}
        </View>
        {sel ? (
          <View {...pan.panHandlers} style={st.hdl} accessible accessibilityLabel={`${s.name} 끌어서 순서 바꾸기`}>
            <Grip />
          </View>
        ) : null}
      </Pressable>
    </Animated.View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: appColor.bg },
  flex: { flex: 1 },
  sub: { ...ft(12.5), color: appColor.ink3, paddingHorizontal: 18, paddingBottom: 10 },
  selh: { position: 'absolute', left: 0, right: 0, height: 60, zIndex: 7, flexDirection: 'row', alignItems: 'center', paddingLeft: 8, paddingRight: 14, backgroundColor: appColor.bg },
  ib: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  selhT: { ...ft(18), fontWeight: '700', color: appColor.ink, marginLeft: 4 },
  all: { marginLeft: 'auto', padding: 8 },
  allT: { ...ft(14.5), fontWeight: '700', color: appColor.tabPurple },
  chips: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingTop: 4, paddingHorizontal: 16, paddingBottom: 12, backgroundColor: appColor.bg },
  cw: { flexDirection: 'row', gap: 6 },
  cpl: { position: 'absolute', top: 0, bottom: 0, borderRadius: 17, backgroundColor: appColor.accent },
  chip: { minHeight: 34, paddingHorizontal: 13, borderRadius: 17, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E3E5EA', flexDirection: 'row', alignItems: 'center', gap: 3 },
  chipOn: { backgroundColor: 'transparent', borderColor: 'transparent' },
  chipT: { ...ft(13.5), color: appColor.ink },
  chipTOn: { color: '#FFFFFF', fontWeight: '700' },
  chipN: { fontSize: 13.5, color: appColor.ink },
  chipNOn: { fontSize: 13.5, color: '#FFFFFF', fontWeight: '700' },
  addc: { marginLeft: 'auto', minHeight: 34, paddingHorizontal: 12, borderRadius: 17, backgroundColor: '#FFFFFF', flexDirection: 'row', alignItems: 'center', gap: 4 },
  addcT: { ...ft(13), color: appColor.ink },
  grp: { backgroundColor: '#FFFFFF', borderRadius: 20, marginHorizontal: 16, marginBottom: 12, paddingTop: 14, paddingHorizontal: 14, paddingBottom: 6 },
  gh: { flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 2, marginBottom: 10 },
  gi: { width: 30, height: 30, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  ghT: { ...ft(16), fontWeight: '800', color: appColor.ink },
  ghS: { marginLeft: 'auto', ...ft(12), fontWeight: '500', color: appColor.ink3 },
  sr: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#F4F5F7', borderRadius: 14, padding: 12, marginBottom: 8, borderWidth: 1.5, borderColor: 'transparent' },
  srOn: { backgroundColor: '#F4F0FF', borderColor: appColor.accent },
  srNew: { borderColor: appColor.accent, backgroundColor: '#F7F4FF' },
  lift: { shadowColor: '#111111', shadowOpacity: 0.45, shadowRadius: 11, shadowOffset: { width: 0, height: 10 }, elevation: 8, borderRadius: 14, backgroundColor: '#FFFFFF' },
  sck: { height: 24, borderRadius: 12, borderColor: '#C5C8CF', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  sckOn: { backgroundColor: appColor.accent, borderColor: appColor.accent },
  nm: { flex: 1, minWidth: 0 },
  nmRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  nmB: { flexShrink: 1, ...ft(15), fontWeight: '700', color: appColor.ink },
  bdg: { minWidth: 19, height: 19, paddingHorizontal: 5, borderRadius: 10, backgroundColor: appColor.red, alignItems: 'center', justifyContent: 'center' },
  bdgT: { fontSize: 11, lineHeight: 13, fontWeight: '700', color: '#FFFFFF' },
  nmS: { ...ft(12), color: appColor.ink3, marginTop: 2 },
  pr: { alignItems: 'flex-end' },
  prB: { ...ft(15), fontWeight: '700', color: appColor.ink },
  prS: { ...ft(12.5), fontWeight: '600' },
  hdl: { width: 28, height: 40, marginLeft: -4, alignItems: 'center', justifyContent: 'center' },
  none: { ...ft(12.5), color: appColor.ink3, paddingTop: 4, paddingHorizontal: 4, paddingBottom: 12 },
  foot2: { textAlign: 'center', ...ft(11.5), color: appColor.ink3, marginTop: 6, marginBottom: 10 },
  hint2: { textAlign: 'center', ...ft(11.5), color: appColor.ink3, marginTop: -4, marginBottom: 12, paddingHorizontal: 16 },
  empty: { alignItems: 'center', paddingTop: 90, paddingHorizontal: 30 },
  ill: { width: 64, height: 64, borderRadius: 20, backgroundColor: '#EDE8FB', alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  emptyB: { ...ft(17), fontWeight: '700', color: appColor.ink, marginBottom: 6, textAlign: 'center' },
  emptyP: { ...ft(13, 1.6), color: appColor.ink2, textAlign: 'center', marginBottom: 18 },
  emptyS: { ...ft(11.5), color: appColor.ink3, marginTop: 12, textAlign: 'center' },
  btn: { minHeight: 46, paddingHorizontal: 22, borderRadius: 23, backgroundColor: appColor.accent, flexDirection: 'row', alignItems: 'center', gap: 6 },
  btnT: { ...ft(15), fontWeight: '700', color: '#FFFFFF' },
  abar: { position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: '#FFFFFF', borderTopWidth: 1, borderTopColor: appColor.line, flexDirection: 'row', zIndex: 46 },
  ab: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 4 },
  abDis: { opacity: 0.3 },
  abT: { ...ft(12), color: appColor.ink },
  snack: { position: 'absolute', left: 12, right: 12 },
});
