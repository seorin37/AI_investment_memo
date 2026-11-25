import React, { useEffect, useRef, useState } from 'react';
import { Animated, KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, View, type TextInputInstance } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Confetti, DotBurst } from '@/components/motion/Celebrate';
import { MiniSpace } from '@/ui/screens/studio/app/MiniBar';
import { Text, TextInput } from '@/components/ui/AppText';
import { CheckMark } from '@/ui/icons/BoardGlyphs';
import { AppIconButton } from '@/ui/shared/IconButton';
import { Collapse } from '@/ui/motion/Collapse';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { useChecklistTone } from '@/ui/shared/Dark';
import { AppTape } from '@/ui/shared/MemoPaper';
import { appColor, curve, ft } from '@/ui/theme';
import type { AppChecklistProps } from '../Checklist.types';

/**
 * 앱 체크리스트 페이지 = 원본 app/memo.html .ckp (11.17 검수 2차 · #324 · Lucian #093)
 * 머리: 보드에서 열면 .dh 56 [뒤로] '메모 보드' 17/600 · [고정] 알약 32 (켜면 귤색 '고정됨') /
 *       + 버튼으로 새로 만들면 .nmh 56 [취소] '{종목} · 새 체크리스트' 15.5/800 [완료]
 * 본문 .ckpb 16 (아래 160): 귤색 종이 .ckpaper 라운드 22 · 안쪽 24/18/8 · 고정이면 테이프
 *   이름 22/800 (바로 수정, 20자) · 작성일 12.5 #9A6B4F + 'd / L' 14/800 #C2410C · 막대 8 (흰 .8 · #FFB547→#FF7A1A, .6s 반동)
 *   모두 끝내면 '모두 확인했어요' 칸이 펼쳐지고(.45s) 배지가 -25° · .3배에서 돌며 튀어나와(.7s, .15s 뒤) 물결(1.1s, .45s 뒤) · .45초 뒤 색종이
 *   항목 줄 54 (아래 선 rgba(194,65,12,.12)): 상자 24 라운드 8 (안쪽 2 #E7B08C / 한 것 #FF7A1A · 1.08배) · 체크하면 점 8개
 *     글자 15.5/600 · 한 것 #A89A92 + 줄이 왼쪽부터 그어짐(.35s) · [×] 36 #C9A792 · 새 줄은 위에서 8px 내려옴(.45s 반동)
 *   '항목 추가' 줄 56: 점선 상자 + · 입력 (40자, 없으면 '확인할 일을 한 줄씩 적어 보세요')
 * 아래 '체크리스트는 AI 연결 없이 나만 보는 확인 목록이에요' 12 #9A9EA7 가운데
 */
export function AppChecklist(p: AppChecklistProps) {
  const insets = useSafeAreaInsets();
  const tone = useChecklistTone();
  const k = useMotionK();
  const L = p.items.length;
  const d = p.items.filter((x) => x.done).length;
  const all = L > 0 && d === L;
  const [draft, setDraft] = useState('');
  const input = useRef<TextInputInstance>(null);
  const root = useRef<React.ComponentRef<typeof View>>(null);
  const badge = useRef<React.ComponentRef<typeof View>>(null);
  /* 처음 있던 줄은 그대로, 나중에 더한 줄만 내려오며 나타남 (원본 .ckrw2.old) */
  const [known] = useState(() => new Set(p.items.map((x) => x.id)));
  /* 점 터짐: 체크한 줄 id 와 횟수 */
  const [pop, setPop] = useState<{ id: string; n: number } | null>(null);
  const [cf, setCf] = useState<{ x: number; y: number; id: number } | null>(null);

  /* 막대 (원본 .ckbar2 i: scaleX · .6s 반동) */
  const [bar] = useState(() => new Animated.Value(L ? d / L : 0));
  useEffect(() => {
    const a = Animated.timing(bar, { toValue: L ? d / L : 0, duration: 600 * k, easing: curve.spring, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [bar, d, L, k]);

  /* 새로 만들기면 열리고 .38초 뒤 입력 (원본 openCheck focus) */
  useEffect(() => {
    if (p.mode !== 'new') return;
    const t = setTimeout(() => input.current?.focus(), 380 * k);
    return () => clearTimeout(t);
  }, [p.mode, k]);

  const toggle = (id: string) => {
    const it = p.items.find((x) => x.id === id);
    const was = all;
    const will = p.items.every((x) => (x.id === id ? !x.done : x.done));
    if (it && !it.done) setPop((v) => ({ id, n: (v?.n ?? 0) + 1 }));
    p.onToggleItem(id);
    /* 원본 ckSync(win): 모두 끝내면 .45초 뒤 배지 높이에서 색종이 */
    if (!was && will)
      setTimeout(() => {
        /* 원본 confetti(W/2, 배지 y) — 가로는 화면 가운데 */
        root.current?.measureInWindow((rx, ry, rw) => badge.current?.measureInWindow((bx, by, bw, bh) => setCf({ x: rw / 2, y: by - ry + bh / 2, id: Date.now() })));
      }, 450 * k);
  };
  const add = () => {
    const v = draft.trim();
    if (!v) return;
    p.onAddItem(v);
    setDraft('');
    input.current?.focus();
  };

  return (
    <View ref={root} collapsable={false} style={[st.root, { paddingTop: insets.top }]}>
      {p.mode === 'new' ? (
        <View style={st.nmh}>
          <Pressable onPress={p.onCancel} accessibilityRole="button" style={st.hb}>
            <Text style={st.hbT}>취소</Text>
          </Pressable>
          <Text style={st.ttl} numberOfLines={1}>
            {p.stock_name} · 새 체크리스트
          </Text>
          <Pressable onPress={p.onDone} accessibilityRole="button" style={st.hb}>
            <Text style={[st.hbT, st.ok]}>완료</Text>
          </Pressable>
        </View>
      ) : (
        <View style={st.dh}>
          <AppIconButton label="뒤로" size={42} icon="back2" iconSize={22} color={appColor.ink} onPress={p.onBack} />
          <Text style={st.dhT}>메모 보드</Text>
          <Pressable onPress={p.onTogglePin} accessibilityRole="button" accessibilityState={{ selected: p.pinned }} style={[st.pin, p.pinned && { backgroundColor: tone.tape, borderWidth: 0 }]}>
            <Text style={[st.pinT, p.pinned && { color: '#FFFFFF' }]}>{p.pinned ? '고정됨' : '고정'}</Text>
          </Pressable>
        </View>
      )}
      <KeyboardAvoidingView style={st.flex} behavior="padding">
        <ScrollView style={st.flex} contentContainerStyle={st.body} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          <View style={[st.paper, { backgroundColor: tone.paper }]}>
            {p.pinned && p.mode === 'edit' ? <AppTape color={tone.tape} /> : null}
            <TextInput style={st.title} value={p.title} onChangeText={p.onChangeTitle} maxLength={20} accessibilityLabel="체크리스트 이름" />
            <View style={st.meta}>
              <Text style={st.metaT}>{p.date_full}</Text>
              <Text style={[st.cnt, { color: tone.ink }]}>
                {d} / {L}
              </Text>
            </View>
            <View style={st.bar}>
              <Animated.View style={[st.barI, { backgroundColor: tone.tape, width: bar.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'], extrapolate: 'clamp' }) }]} />
            </View>
            <Collapse open={all} duration={450}>
              <View style={st.winWrap}>
                <Win on={all} tone={tone.tape} badgeRef={badge} />
              </View>
            </Collapse>
            {p.items.map((x) => (
              <Row key={x.id} text={x.text} done={x.done} fresh={!known.has(x.id)} pop={pop?.id === x.id ? pop.n : 0} tone={tone} onToggle={() => toggle(x.id)} onDelete={() => p.onDeleteItem(x.id)} />
            ))}
            <Pressable style={st.addRow} onPress={() => input.current?.focus()}>
              <View style={[st.plus, { borderColor: tone.box }]}>
                <Text style={[st.plusT, { color: tone.ink }]}>+</Text>
              </View>
              <TextInput
                ref={input}
                style={st.addIn}
                value={draft}
                onChangeText={setDraft}
                onSubmitEditing={add}
                submitBehavior="submit"
                returnKeyType="done"
                maxLength={40}
                placeholder={L ? '항목 추가' : '확인할 일을 한 줄씩 적어 보세요'}
                placeholderTextColor="#C29A80"
                accessibilityLabel="항목 추가"
              />
            </Pressable>
          </View>
          <Text style={st.ai}>체크리스트는 AI 연결 없이 나만 보는 확인 목록이에요</Text>
          <MiniSpace />
        </ScrollView>
      </KeyboardAvoidingView>
      <Confetti fire={cf} />
    </View>
  );
}

/** 항목 줄: 상자 (.4s 반동 1.08배 · 체크 그려짐 · 점 8개) · 글자 줄 긋기 (.35s) · 새 줄은 위에서 8px (.45s 반동) */
function Row({ text, done, fresh, pop, tone, onToggle, onDelete }: { text: string; done: boolean; fresh: boolean; pop: number; tone: ReturnType<typeof useChecklistTone>; onToggle: () => void; onDelete: () => void }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(done ? 1 : 0));
  const [inV] = useState(() => new Animated.Value(fresh ? 0 : 1));
  const [tw, setTw] = useState(0);
  useEffect(() => {
    const a = Animated.timing(v, { toValue: done ? 1 : 0, duration: 350 * k, easing: curve.ease, useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [done, v, k]);
  useEffect(() => {
    const a = Animated.timing(inV, { toValue: 1, duration: 450 * k, easing: curve.spring, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [inV, k]);
  return (
    <Animated.View style={[st.row, { opacity: inV, transform: [{ translateY: inV.interpolate({ inputRange: [0, 1], outputRange: [-8, 0] }) }] }]}>
      <Pressable style={st.rowBtn} onPress={onToggle} accessibilityRole="checkbox" accessibilityState={{ checked: done }} accessibilityLabel={text}>
        <View style={[st.box, done ? { backgroundColor: tone.tape, borderColor: tone.tape, transform: [{ scale: 1.08 }] } : { borderColor: tone.box, backgroundColor: tone.boxBg }]}>
          {done ? <CheckMark kind="cki" size={18} stroke={2.2} /> : null}
          <DotBurst fire={pop} size={24} />
        </View>
        <View style={st.flex}>
          {/* 줄은 글자 폭만큼 (원본 .ct::after 는 글자 span 기준 · 양옆 2 더) */}
          <Text keepAll style={[st.ct, done && st.ctDone]} onTextLayout={(e) => setTw(Math.max(0, ...e.nativeEvent.lines.map((l) => l.width)))}>
            {text}
          </Text>
          <Animated.View pointerEvents="none" style={[st.strike, { width: v.interpolate({ inputRange: [0, 1], outputRange: [0, tw + 4] }) }]} />
        </View>
      </Pressable>
      <Pressable style={st.del} onPress={onDelete} accessibilityRole="button" accessibilityLabel="항목 지우기" hitSlop={4}>
        <Text style={[st.delT, { color: tone.del }]}>×</Text>
      </Pressable>
    </Animated.View>
  );
}

/** '모두 확인했어요' 배지: -25° · .3배 → 제자리 (.7s 반동 · .15초 뒤) · 물결 (1.1s · .45초 뒤) */
function Win({ on, tone, badgeRef }: { on: boolean; tone: string; badgeRef: React.RefObject<React.ComponentRef<typeof View> | null> }) {
  const k = useMotionK();
  const [b] = useState(() => new Animated.Value(on ? 1 : 0));
  const [w] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!on) {
      b.setValue(0);
      return;
    }
    w.setValue(0);
    const a = Animated.parallel([
      Animated.timing(b, { toValue: 1, duration: 700 * k, delay: 150 * k, easing: curve.spring, useNativeDriver: NATIVE }),
      Animated.timing(w, { toValue: 1, duration: 1100 * k, delay: 450 * k, easing: curve.ease, useNativeDriver: NATIVE }),
    ]);
    a.start();
    return () => a.stop();
  }, [on, b, w, k]);
  return (
    <View style={st.win}>
      <View ref={badgeRef} collapsable={false}>
        <Animated.View pointerEvents="none" style={[st.wave, { backgroundColor: tone, opacity: w.interpolate({ inputRange: [0, 0.01, 1], outputRange: [0, 0.5, 0] }), transform: [{ scale: w.interpolate({ inputRange: [0, 1], outputRange: [1, 1.95] }) }] }]} />
        <Animated.View style={[st.badge, { backgroundColor: tone, transform: [{ scale: b.interpolate({ inputRange: [0, 1], outputRange: [0.3, 1] }) }, { rotate: b.interpolate({ inputRange: [0, 1], outputRange: ['-25deg', '0deg'] }) }] }]}>
          <CheckMark kind="cki" size={24} stroke={2.4} />
        </Animated.View>
      </View>
      <View style={st.flex}>
        <Text style={st.winB}>모두 확인했어요</Text>
        <Text style={st.winS}>다 끝낸 체크리스트도 보드에 그대로 남아요</Text>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#FFFFFF' },
  flex: { flex: 1, minWidth: 0 },
  nmh: { height: 56, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16 },
  hb: { paddingVertical: 8, paddingHorizontal: 2, minHeight: 44, justifyContent: 'center' },
  hbT: { ...ft(15.5), color: appColor.ink },
  ok: { fontWeight: '800', color: appColor.deepPurple },
  ttl: { flex: 1, textAlign: 'center', ...ft(15.5), fontWeight: '800', color: appColor.ink },
  dh: { height: 56, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 6 },
  dhT: { flex: 1, ...ft(17), fontWeight: '600', color: appColor.ink },
  pin: { height: 32, paddingHorizontal: 12, borderRadius: 16, borderWidth: 1, borderColor: '#DADDE2', justifyContent: 'center', marginRight: 8 },
  pinT: { fontSize: 13, lineHeight: 18, fontWeight: '700', color: appColor.ink2 },
  body: { padding: 16, paddingBottom: 160 },
  paper: { borderRadius: 22, paddingTop: 24, paddingHorizontal: 18, paddingBottom: 8 },
  title: { fontSize: 22, lineHeight: 30, fontWeight: '800', color: appColor.ink, letterSpacing: -0.4, padding: 0, paddingVertical: 2 },
  meta: { flexDirection: 'row', alignItems: 'center', marginTop: 6, marginBottom: 10 },
  metaT: { flex: 1, fontSize: 12.5, lineHeight: 18, color: '#9A6B4F' },
  cnt: { fontSize: 14, lineHeight: 20, fontWeight: '800' },
  bar: { height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.8)', overflow: 'hidden', marginBottom: 6 },
  barI: { height: 8, borderRadius: 4 },
  winWrap: { paddingTop: 12, paddingBottom: 6 },
  win: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FFFFFF', borderRadius: 16, padding: 12 },
  badge: { width: 46, height: 46, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  wave: { position: 'absolute', left: 0, top: 0, width: 46, height: 46, borderRadius: 16 },
  winB: { fontSize: 16, lineHeight: 22, fontWeight: '800', color: appColor.ink },
  winS: { fontSize: 12.5, lineHeight: 18, color: appColor.ink2, marginTop: 2 },
  row: { flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1, borderBottomColor: 'rgba(194,65,12,0.12)' },
  rowBtn: { flex: 1, minWidth: 0, minHeight: 54, flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8 },
  box: { width: 24, height: 24, borderRadius: 8, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  ct: { fontSize: 15.5, lineHeight: 22.5, fontWeight: '600', color: appColor.ink },
  ctDone: { color: '#A89A92' },
  /* 첫 줄 가운데 (줄 높이 22.5 × .52) */
  strike: { position: 'absolute', left: -2, top: 11, height: 2, borderRadius: 1, backgroundColor: '#B9A296' },
  del: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  delT: { fontSize: 20, lineHeight: 24 },
  addRow: { flexDirection: 'row', alignItems: 'center', gap: 12, height: 56 },
  plus: { width: 24, height: 24, borderRadius: 8, borderWidth: 2, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center' },
  plusT: { fontSize: 16, lineHeight: 18, fontWeight: '800' },
  addIn: { flex: 1, minWidth: 0, fontSize: 15.5, color: appColor.ink, padding: 0, minHeight: 44 },
  ai: { textAlign: 'center', fontSize: 12, lineHeight: 18, color: '#9A9EA7', marginTop: 14 },
});
