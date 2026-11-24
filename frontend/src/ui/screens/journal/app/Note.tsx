import React, { useEffect, useRef, useState } from 'react';
import { Animated, BackHandler, Keyboard, KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, View, type LayoutChangeEvent, type TextInputInstance, type TextStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text, TextInput } from '@/components/ui/AppText';
import { copyText, shareText } from '@/lib/copyText';
import { useMotionK } from '@/ui/motion/useMotion';
import { ON_DOM } from '@/ui/shared/onDom';
import { Sheet } from '@/ui/shared/Sheet';
import { appColor, curve, ft } from '@/ui/theme';
import type { JBlock, JBlockStyle, JList, JournalEntry } from '../Journal.types';
import { Pill, type Toast } from './Journal';
import { JBack, JCheck, JChecklist, JCompose, JMore, JShare, JUndo, JX } from './journalGlyphs';

const A2 = appColor.tabPurple;
const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';
type Item = JBlock & { k: string };
let kseq = 0;
const key = () => `b${++kseq}`;
const withKeys = (bs: JBlock[]): Item[] => (bs.length ? bs : [{ s: 'title' as const, text: '' }]).map((b) => ({ ...b, k: key() }));
const strip = (it: Item[]): JBlock[] =>
  it.map(({ k: _k, ...b }) => {
    void _k;
    return b;
  });

/** 웹의 여러 줄 입력칸은 기본 2줄 높이에 스스로 줄지 않음 → 같은 글의 안 보이는 Text 높이에 맞춤 (기기는 내용만큼 저절로) */
const FIT = ON_DOM;

export interface AppNoteProps {
  /** 연 기록 (없으면 새 기록) */
  entry: JournalEntry | null;
  /** 날짜 줄 (새 기록은 mock '지금') */
  full: string;
  pinned: boolean;
  /** 뒤로 (원본 back: 저장하고 목록으로 — 확인창 없음) */
  onBack: (blocks: JBlock[]) => void;
  /** 아래 [새 기록] (원본 act('new'): 지금 기록을 저장하고 같은 화면에서 새 기록) */
  onNew: (blocks: JBlock[]) => void;
  onPin: () => void;
  /** 휴지통으로 (목록에서 되돌리기 스낵바) */
  onTrash: () => void;
}

/**
 * 앱 투자 기록 보기·쓰기 (원본 journal.html 14.1 · 14.2 · 14.3)
 * 머리 56 흰 (‹ 투자 기록 16.5 · 보기: [공유] [⋯] 36 원 #F1F0F6 / 쓰기: [되돌리기] [공유] [완료])
 * 날짜 12.5 가운데 · 줄마다 글 모양 (제목 26/800 · 머리말 20/800 · 부제목 17.5/700 · 본문 16 줄 1.65)
 * 보기에서 줄을 누르면 그 줄부터 쓰기. 아래 도구(체크리스트 · 새 기록)는 보기에서만,
 * 쓰는 동안은 키보드 위 줄 [가가 서식] [체크리스트] + 서식 패널 (제목·머리말·부제목·본문 · B I U S · 목록 4종).
 * RN TextInput 은 글자 일부만 서식을 줄 수 없어 B·I·U·S 는 줄 전체에 적용.
 */
export function AppNote(p: AppNoteProps) {
  const k = useMotionK();
  const insets = useSafeAreaInsets();
  const [items, setItems] = useState<Item[]>(() => withKeys(p.entry?.blocks ?? []));
  const [editing, setEditing] = useState(!p.entry);
  const [cur, setCur] = useState(0);
  const [fmt, setFmt] = useState(false);
  const [kb, setKb] = useState(false);
  const [more, setMore] = useState(false);
  const [shadow, setShadow] = useState(false);
  const [toastV, setToastV] = useState<Toast | null>(null);
  const refs = useRef<Record<string, TextInputInstance | null>>({});
  const hist = useRef<{ list: Item[][]; at: string }>({ list: [], at: '' });
  const [canUndo, setCanUndo] = useState(false);

  const toast = (msg: string) => setToastV((s) => ({ id: (s?.id ?? 0) + 1, msg }));
  const text = () => items.map((b) => b.text).join('\n');
  const share = () => void shareText(text()).then((copied) => copied && toast('공유할 내용을 복사했어요'));
  useEffect(() => {
    if (!toastV) return;
    const t = setTimeout(() => setToastV((s) => (s && s.id === toastV.id ? null : s)), 2300 * k);
    return () => clearTimeout(t);
  }, [toastV, k]);

  /* 키보드 (⑨-3c 와 같게: 키보드가 있으면 아래 안전 영역 여백을 빼서 키보드 위 빈 칸이 생기지 않게) */
  useEffect(() => {
    const a = Keyboard.addListener('keyboardDidShow', () => {
      setKb(true);
      setFmt(false);
    });
    const b = Keyboard.addListener('keyboardDidHide', () => setKb(false));
    return () => {
      a.remove();
      b.remove();
    };
  }, []);

  /* 줄 고르기: 쓰기 상태가 화면에 반영된 뒤에 그 줄로 (잠긴 칸은 focus 가 안 됨) */
  const [want, setWant] = useState<{ k: string; n: number } | null>(null);
  const focusAt = (k2: string) => setWant((w) => ({ k: k2, n: (w?.n ?? 0) + 1 }));
  useEffect(() => {
    if (!want) return;
    const t = setTimeout(() => refs.current[want.k]?.focus(), 60);
    return () => clearTimeout(t);
  }, [want, editing]);
  /* 새 기록은 바로 제목부터 쓰기 (원본 openNew → startEdit) */
  useEffect(() => {
    if (p.entry) return;
    const t = setTimeout(() => refs.current[items[0].k]?.focus(), 350 * k);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** 바꾸기 전 모습을 되돌리기 목록에 (글자 입력은 한 줄 단위로 묶음 · 줄 나누기·서식은 한 번씩) */
  const change = (next: Item[], structural = false, at = '') => {
    const h = hist.current;
    if (structural || !at || at !== h.at) {
      h.list.push(items);
      if (h.list.length > 50) h.list.shift();
      setCanUndo(true);
    }
    h.at = structural ? '' : at;
    setItems(next);
  };
  const undo = () => {
    const prev = hist.current.list.pop();
    if (prev) setItems(prev);
    setCanUndo(hist.current.list.length > 0);
  };

  const startEdit = (i: number) => {
    setEditing(true);
    setCur(i);
    focusAt(items[i].k);
  };
  const exitEdit = () => {
    Keyboard.dismiss();
    setFmt(false);
    setEditing(false);
  };
  const back = () => {
    Keyboard.dismiss();
    p.onBack(strip(items));
  };

  /* 안드로이드 뒤로: 시트(모달) → 서식 패널 → 저장하고 목록 (원본 back) */
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (fmt) return setFmt(false), true;
      back();
      return true;
    });
    return () => sub.remove();
  });

  /* 글 바꾸기 · 줄 바꿈 (제목·머리말·부제목 다음 줄은 본문 · 목록·체크리스트는 이어짐 · 빈 목록 줄에서 줄 바꿈은 목록 끝) */
  const onText = (i: number, t: string) => {
    const it = items[i];
    /* 새로 들어온 줄바꿈만 줄 나누기로 (원래 글 안에 있던 줄바꿈은 그대로 둠) */
    const nlCount = (s: string) => s.split('\n').length - 1;
    if (nlCount(t) <= nlCount(it.text)) return change(items.map((x, j) => (j === i ? { ...x, text: t } : x)), false, it.k);
    let d = 0;
    while (d < it.text.length && t[d] === it.text[d]) d++;
    const nl = t.indexOf('\n', d);
    const a = t.slice(0, nl);
    const rest = t.slice(nl + 1);
    if (!a && !rest && (it.l || it.check !== undefined) && i > 0) {
      const { l: _l, check: _c, ...plain } = it;
      void _l;
      void _c;
      return change(items.map((x, j) => (j === i ? { ...plain, s: 'body' as const, text: '' } : x)), true);
    }
    const nb: Item = it.check !== undefined ? { s: 'body', text: rest, check: false, k: key() } : it.l && it.l !== 'quote' ? { s: 'body', l: it.l, text: rest, k: key() } : { s: ['title', 'head', 'sub'].includes(it.s) ? 'body' : it.s, text: rest, k: key() };
    const next = [...items.slice(0, i), { ...it, text: a }, nb, ...items.slice(i + 1)];
    change(next, true);
    setCur(i + 1);
    focusAt(nb.k);
  };
  /* 빈 줄에서 지우기: 목록·체크리스트 표시 먼저 빼고, 그다음 줄을 지움 */
  const onKey = (i: number, keyName: string) => {
    if (keyName !== 'Backspace' || items[i].text || i === 0) return;
    const it = items[i];
    if (it.l || it.check !== undefined) {
      const { l: _l, check: _c, ...plain } = it;
      void _l;
      void _c;
      return change(items.map((x, j) => (j === i ? { ...plain, s: 'body' as const } : x)), true);
    }
    change(items.filter((_, j) => j !== i), true);
    setCur(i - 1);
    focusAt(items[i - 1].k);
  };
  const toggleCheck = (i: number) => change(items.map((x, j) => (j === i ? { ...x, check: !x.check } : x)), true);
  /* 체크리스트 넣기 (원본 insertCk: 지금 줄 다음에) */
  const insertCk = () => {
    const at = editing ? cur : items.length - 1;
    const nb: Item = { s: 'body', text: '', check: false, k: key() };
    change([...items.slice(0, at + 1), nb, ...items.slice(at + 1)], true);
    setEditing(true);
    setCur(at + 1);
    focusAt(nb.k);
  };
  /* 서식 (원본 #sty · #bius · #lst — 지금 줄에) */
  const setStyle = (s: JBlockStyle) => change(items.map((x, j) => (j === cur ? { ...x, s } : x)), true);
  const toggleMark = (m: 'b' | 'i' | 'u' | 'x') => change(items.map((x, j) => (j === cur ? { ...x, [m]: !x[m] } : x)), true);
  const toggleList = (l: JList) => {
    if (items[cur]?.check !== undefined) return;
    change(items.map((x, j) => (j === cur ? { ...x, l: x.l === l ? undefined : l } : x)), true);
  };
  const openFmt = () => {
    if (fmt) {
      setFmt(false);
      focusAt(items[cur].k);
      return;
    }
    Keyboard.dismiss();
    setFmt(true);
  };

  const empty = items.length === 1 && !items[0].text;
  const nums = items.map((b, i) => items.slice(0, i + 1).filter((x) => x.l === 'num').length);
  const bottomPad = kb ? 0 : insets.bottom;

  return (
    <KeyboardAvoidingView style={[st.root, { paddingTop: insets.top }]} behavior="padding">
      {/* 머리 */}
      <View style={[st.nh, shadow && st.nhSh]}>
        <Pressable onPress={back} accessibilityRole="button" accessibilityLabel="투자 기록으로 돌아가기" style={st.bk}>
          <JBack color={A2} />
          <Text style={st.bkT}>투자 기록</Text>
        </Pressable>
        <View style={st.rt}>
          {editing ? (
            <>
              <Pressable onPress={undo} disabled={!canUndo} accessibilityRole="button" accessibilityLabel="실행 취소" style={[st.undo, !canUndo && { opacity: 0.4 }]}>
                <JUndo color={A2} />
              </Pressable>
              <Rb label="공유" onPress={share}>
                <JShare color={A2} />
              </Rb>
              <Pressable onPress={exitEdit} accessibilityRole="button" style={st.done}>
                <Text style={st.doneT}>완료</Text>
              </Pressable>
            </>
          ) : (
            <>
              <Rb label="공유" onPress={share}>
                <JShare color={A2} />
              </Rb>
              <Rb label="더 보기" onPress={() => setMore(true)}>
                <JMore color={A2} />
              </Rb>
            </>
          )}
        </View>
      </View>

      <ScrollView style={st.flex} contentContainerStyle={st.scr} keyboardShouldPersistTaps="handled" onScroll={(e) => setShadow(e.nativeEvent.contentOffset.y > 8)} scrollEventThrottle={32}>
        <Text style={st.ndt}>{p.entry?.full ?? p.full}</Text>
        {items.map((b, i) => {
          const ts = textStyle(b);
          const field = (
            <TextInput
              ref={(r: TextInputInstance | null) => {
                refs.current[b.k] = r;
              }}
              value={b.text}
              multiline
              scrollEnabled={false}
              {...(FIT ? { numberOfLines: 1 } : null)}
              editable={editing}
              pointerEvents={editing ? 'auto' : 'none'}
              placeholder={i === 0 && empty ? '제목' : undefined}
              placeholderTextColor="#C2C5CC"
              onFocus={() => setCur(i)}
              onChangeText={(t) => onText(i, t)}
              onKeyPress={(e) => onKey(i, e.nativeEvent.key)}
              style={[st.in, ts, b.check ? { color: appColor.ink3 } : null, FIT && st.inFit]}
              accessibilityLabel={i === 0 ? '제목' : '기록 내용'}
            />
          );
          const input = FIT ? (
            <View>
              <Text style={[ts, st.ghost]} accessibilityElementsHidden aria-hidden>
                {`${b.text}\u200B`}
              </Text>
              {field}
            </View>
          ) : (
            field
          );
          return (
            <Pressable key={b.k} disabled={editing} onPress={() => startEdit(i)} style={[st.b, b.s === 'title' && st.bTitle, b.s === 'head' && st.bHead, b.check !== undefined && st.bCk, (b.l === 'dot' || b.l === 'dash' || b.l === 'num') && st.bList, b.l === 'quote' && st.bQuote]}>
              {b.check !== undefined ? (
                <View style={st.ckl}>
                  <Pressable onPress={() => toggleCheck(i)} accessibilityRole="checkbox" accessibilityState={{ checked: !!b.check }} accessibilityLabel={b.text || '할 일'} hitSlop={8} style={[st.cbx, b.check && st.cbxOn]}>
                    {b.check ? <JCheck /> : null}
                  </Pressable>
                  <View style={st.flex}>{input}</View>
                </View>
              ) : (
                <>
                  {b.l === 'dot' || b.l === 'dash' || b.l === 'num' ? <Text style={[ts, st.mk, { left: b.l === 'dot' ? 6 : b.l === 'dash' ? 4 : 2 }]}>{b.l === 'dot' ? '•' : b.l === 'dash' ? '–' : `${nums[i]}.`}</Text> : null}
                  {input}
                </>
              )}
            </Pressable>
          );
        })}
        {/* 아래 빈 곳을 누르면 마지막 줄부터 쓰기 */}
        <Pressable disabled={editing} onPress={() => startEdit(items.length - 1)} style={{ minHeight: 160 }} accessibilityElementsHidden />
      </ScrollView>

      {editing ? (
        <View style={{ paddingBottom: fmt ? 0 : bottomPad }}>
          {/* 키보드 위 줄 (원본 .acc 48) */}
          <View style={st.acc}>
            <Pressable onPress={openFmt} accessibilityRole="button" accessibilityLabel="서식" accessibilityState={{ selected: fmt }} style={[st.accB, fmt && st.accOn]}>
              <Text style={[st.accT, fmt && { color: A2 }]}>
                가<Text style={[st.accT, { fontSize: 12 }, fmt && { color: A2 }]}>가</Text>
              </Text>
            </Pressable>
            <Pressable onPress={insertCk} accessibilityRole="button" accessibilityLabel="체크리스트" style={st.accB}>
              <JChecklist color={appColor.ink} size={22} />
            </Pressable>
          </View>
          {fmt ? <FmtPanel b={items[cur] ?? items[0]} pad={insets.bottom} onClose={openFmt} onStyle={setStyle} onMark={toggleMark} onList={toggleList} /> : null}
        </View>
      ) : (
        /* 아래 도구 (원본 .ntb 56: 체크리스트 · 새 기록) */
        <View style={[st.ntb, { height: 56 + insets.bottom, paddingBottom: 4 + insets.bottom }]}>
          <Pressable onPress={insertCk} accessibilityRole="button" accessibilityLabel="체크리스트" style={({ pressed }) => [st.ntbB, pressed && { backgroundColor: '#F1EEFB' }]}>
            <JChecklist color={A2} />
          </Pressable>
          <Pressable onPress={() => p.onNew(strip(items))} accessibilityRole="button" accessibilityLabel="새 기록" style={({ pressed }) => [st.ntbB, pressed && { backgroundColor: '#F1EEFB' }]}>
            <JCompose color={A2} />
          </Pressable>
        </View>
      )}

      <Pill toast={toastV} bottom={editing ? (fmt ? 340 : 70) : 70 + insets.bottom} />

      {/* 기록 더 보기 (원본 #nmore — '제안' 표시는 뺌) */}
      <Sheet open={more} onClose={() => setMore(false)} label="기록 더 보기">
        <View style={{ paddingTop: 4 }}>
          <SRow
            label={p.pinned ? '고정 해제' : '고정'}
            onPress={() => {
              setMore(false);
              toast(p.pinned ? '고정을 풀었어요' : '고정했어요');
              p.onPin();
            }}
          />
          <SRow label="기록 안에서 찾기" onPress={() => (setMore(false), toast(NOT_YET))} />
          <SRow
            label="내용 복사"
            onPress={() => {
              setMore(false);
              copyText(text());
              toast('내용을 복사했어요');
            }}
          />
          <SRow
            label="휴지통으로 이동"
            red
            onPress={() => {
              setMore(false);
              Keyboard.dismiss();
              p.onTrash();
            }}
          />
        </View>
      </Sheet>
    </KeyboardAvoidingView>
  );
}

/** 줄 글 모양 (원본 #ned .b[data-s] · 줄 서식) */
function textStyle(b: JBlock): TextStyle {
  const base: TextStyle = b.s === 'title' ? { fontSize: 26, lineHeight: 35, fontWeight: '800' } : b.s === 'head' ? { ...ft(20, 1.65), fontWeight: '800' } : b.s === 'sub' ? { ...ft(17.5, 1.65), fontWeight: '700' } : { ...ft(16, 1.65) };
  const deco = [b.u && 'underline', b.x && 'line-through'].filter(Boolean).join(' ') as TextStyle['textDecorationLine'];
  return {
    ...base,
    color: b.l === 'quote' ? appColor.ink2 : appColor.ink,
    ...(b.b ? { fontWeight: '800' as const } : null),
    ...(b.i ? { fontStyle: 'italic' as const } : null),
    ...(deco ? { textDecorationLine: deco } : null),
  };
}

function Rb({ label, onPress, children }: { label: string; onPress: () => void; children: React.ReactNode }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={({ pressed }) => [st.rb, pressed && { transform: [{ scale: 0.88 }] }]}>
      {children}
    </Pressable>
  );
}

function SRow({ label, onPress, red }: { label: string; onPress: () => void; red?: boolean }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [st.sr, pressed && { backgroundColor: '#F5F5F8' }]}>
      <Text style={[st.srT, red && { color: appColor.red }]}>{label}</Text>
    </Pressable>
  );
}

const STY: [JBlockStyle, string, TextStyle][] = [
  ['title', '제목', { fontSize: 19, fontWeight: '800' }],
  ['head', '머리말', { fontSize: 16, fontWeight: '800' }],
  ['sub', '부제목', { fontSize: 14.5, fontWeight: '700' }],
  ['body', '본문', { fontSize: 14, fontWeight: '500' }],
];

/** 서식 패널 (원본 .fmt: #F3F4F6 · 274 · 안쪽 14 16 · 글 모양 알약이 미끄러짐 · B I U S · 목록 4종 · 안내 11.5) */
function FmtPanel({ b, pad, onClose, onStyle, onMark, onList }: { b: JBlock; pad: number; onClose: () => void; onStyle: (s: JBlockStyle) => void; onMark: (m: 'b' | 'i' | 'u' | 'x') => void; onList: (l: JList) => void }) {
  const k = useMotionK();
  const [lay, setLay] = useState<Partial<Record<JBlockStyle, { x: number; w: number }>>>({});
  const [x] = useState(() => new Animated.Value(0));
  const [w] = useState(() => new Animated.Value(0));
  const on = lay[b.s];
  useEffect(() => {
    if (!on) return;
    const a = Animated.parallel([Animated.timing(x, { toValue: on.x, duration: 320 * k, easing: curve.spring, useNativeDriver: false }), Animated.timing(w, { toValue: on.w, duration: 320 * k, easing: curve.spring, useNativeDriver: false })]);
    a.start();
    return () => a.stop();
  }, [on, x, w, k]);
  const marks: ['b' | 'i' | 'u' | 'x', string, TextStyle][] = [
    ['b', 'B', { fontWeight: '800' }],
    ['i', 'I', { fontStyle: 'italic', fontSize: 17 }],
    ['u', 'U', { textDecorationLine: 'underline' }],
    ['x', 'S', { textDecorationLine: 'line-through' }],
  ];
  const lists: [JList, string][] = [
    ['dot', '• 목록'],
    ['dash', '– 목록'],
    ['num', '1. 목록'],
    ['quote', '│ 인용'],
  ];
  return (
    <View style={[st.fmt, { paddingBottom: 14 + pad }]}>
      <View style={st.fmtHd}>
        <Text style={st.fmtT}>서식</Text>
        <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="닫기" style={st.fmtX}>
          <JX />
        </Pressable>
      </View>
      <View style={st.sty}>
        {on ? <Animated.View style={[st.pl, { left: x, width: w }]} /> : null}
        {STY.map(([s, l, ts]) => (
          <Pressable key={s} onPress={() => onStyle(s)} onLayout={(e: LayoutChangeEvent) => setLay((o) => ({ ...o, [s]: { x: e.nativeEvent.layout.x, w: e.nativeEvent.layout.width } }))} accessibilityRole="button" accessibilityState={{ selected: b.s === s }} style={[st.styB, b.s === s && on && { backgroundColor: 'transparent' }]}>
            <Text style={[ts, { color: b.s === s ? '#FFFFFF' : appColor.ink }]}>{l}</Text>
          </Pressable>
        ))}
      </View>
      <View style={st.seg}>
        {marks.map(([m, l, ts], i) => (
          <Pressable key={m} onPress={() => onMark(m)} accessibilityRole="button" accessibilityLabel={{ b: '굵게', i: '기울임', u: '밑줄', x: '취소선' }[m]} accessibilityState={{ selected: !!b[m] }} style={[st.segB, i > 0 && st.segL, b[m] && st.segOn]}>
            <Text style={[{ fontSize: 15, color: b[m] ? A2 : appColor.ink }, ts]}>{l}</Text>
          </Pressable>
        ))}
      </View>
      <View style={st.seg}>
        {lists.map(([l, t], i) => (
          <Pressable key={l} onPress={() => onList(l)} accessibilityRole="button" accessibilityState={{ selected: b.l === l }} style={[st.segB, i > 0 && st.segL, b.l === l && st.segOn]}>
            <Text style={{ fontSize: 13, color: b.l === l ? A2 : appColor.ink }}>{t}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={st.cap}>어느 줄이든 고른 서식이 바로 적용돼요 · 첫 줄은 제목, 줄을 바꾸면 본문으로 시작</Text>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#FFFFFF' },
  flex: { flex: 1 },
  nh: { height: 56, flexDirection: 'row', alignItems: 'center', paddingLeft: 4, paddingRight: 10, backgroundColor: '#FFFFFF', zIndex: 6 },
  nhSh: { borderBottomWidth: 1, borderBottomColor: '#EEF0F3' },
  bk: { flexDirection: 'row', alignItems: 'center', gap: 2, height: 44, paddingHorizontal: 8 },
  bkT: { ...ft(16.5), fontWeight: '500', color: A2 },
  rt: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 8, height: 40 },
  rb: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F1F0F6', alignItems: 'center', justifyContent: 'center' },
  undo: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  done: { height: 36, paddingHorizontal: 6, justifyContent: 'center' },
  doneT: { ...ft(16.5), fontWeight: '800', color: A2 },
  scr: { paddingHorizontal: 20, paddingBottom: 40 },
  ndt: { ...ft(12.5), color: appColor.ink3, textAlign: 'center', marginTop: 4, marginBottom: 12 },
  b: { marginBottom: 6 },
  bTitle: { marginBottom: 10 },
  bHead: { marginTop: 12 },
  /* 체크 줄: 26.4 + 위아래 3.3 = 33 */
  bCk: { marginTop: 0, marginBottom: 0, paddingVertical: 3.3 },
  bList: { paddingLeft: 22 },
  bQuote: { paddingLeft: 14, borderLeftWidth: 3, borderLeftColor: '#D9D2F5' },
  in: { padding: 0, margin: 0, textAlignVertical: 'top' },
  inFit: { position: 'absolute', left: 0, top: 0, width: '100%', height: '100%', overflow: 'hidden' },
  ghost: { opacity: 0 },
  mk: { position: 'absolute', top: 0 },
  ckl: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  cbx: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: '#C5C8CF', marginTop: 3, alignItems: 'center', justifyContent: 'center' },
  cbxOn: { backgroundColor: appColor.accent, borderColor: appColor.accent },
  ntb: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 22, backgroundColor: '#FFFFFF' },
  ntbB: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  acc: { height: 48, backgroundColor: '#FFFFFF', borderTopWidth: 1, borderTopColor: '#ECEDF1', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', paddingHorizontal: 8 },
  accB: { width: 44, height: 40, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  accOn: { backgroundColor: appColor.accentSoft },
  accT: { fontSize: 16, fontWeight: '800', color: appColor.ink },
  fmt: { backgroundColor: '#F3F4F6', paddingTop: 14, paddingHorizontal: 16, minHeight: 274 },
  fmtHd: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  fmtT: { ...ft(16), fontWeight: '700', color: appColor.ink },
  fmtX: { marginLeft: 'auto', width: 30, height: 30, borderRadius: 15, backgroundColor: '#E3E4E9', alignItems: 'center', justifyContent: 'center' },
  sty: { flexDirection: 'row', gap: 6, marginBottom: 12 },
  pl: { position: 'absolute', top: 0, bottom: 0, borderRadius: 10, backgroundColor: appColor.accent },
  styB: { height: 42, paddingHorizontal: 13, borderRadius: 10, backgroundColor: '#FFFFFF', justifyContent: 'center' },
  seg: { flexDirection: 'row', backgroundColor: '#FFFFFF', borderRadius: 12, marginBottom: 10, overflow: 'hidden' },
  segB: { flex: 1, height: 42, alignItems: 'center', justifyContent: 'center' },
  segL: { borderLeftWidth: 1, borderLeftColor: '#EDEEF1' },
  segOn: { backgroundColor: appColor.accentSoft },
  cap: { ...ft(11.5), color: appColor.ink3, marginTop: 4 },
  sr: { flexDirection: 'row', alignItems: 'center', height: 52, paddingHorizontal: 20 },
  srT: { ...ft(15.5), color: appColor.ink },
});
