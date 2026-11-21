import React, { useEffect, useRef, useState } from 'react';
import { Animated, Easing, Modal, Platform, Pressable, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { useCoach } from '@/store/coach';
import { useMotionK } from '@/ui/motion/useMotion';
import { appColor, size } from '@/ui/theme';
import { Keep } from './Dark';
import { AppSnackbar, WebSnackbar } from './Snackbar';

/*
 * 사용법 안내 4단계 (원본 앱 x/app.js 85~220줄 · app.css .u197 / 웹 coach.tsx · v2.css · Lucian #197)
 * 화면 전체를 어둡게 덮고(rgba(10,12,22,.66)) 대상 자리만 구멍(라운드 14 · 동그라미)으로 밝힘. 구멍은 넘쳤다 멈추며 520ms 이동,
 * 흰 고리 2px + 맥박(1.5s), 꼬리 달린 말풍선(320 · 라운드 18 · 안쪽 18/20/16), 점 표시, [이전] [다음/완료] · 건너뛰기.
 * 대상은 각 화면이 useCoachRef(id) 로 알려 주고, 화면 이동은 레이아웃(CoachDriver)이 맡음.
 */
type Side = 'rt' | 'lt' | 'dn' | 'up';
type Box = { x: number; y: number; w: number; h: number };
type StepDef = { id: string; pad: number; round?: boolean; prefer: Side[]; t: string; d: string };

const WEB = Platform.OS === 'web';
const TEXT = [
  { t: '생각을 한 줄 적어 보세요', d: '형식은 없어요. 궁금한 점, 산 이유, 걱정 무엇이든 괜찮아요.' },
  { t: 'AI 연결을 켜면 대신 지켜봐요', d: '하루 한 번 공시·뉴스·주가를 확인해 이 메모에 붙여 드려요.' },
  { t: '내 생각 아래 소식이 쌓여요', d: '처음 생각과 새 소식을 나란히 보며 판단을 이어가세요.' },
  { t: '읽기 바쁠 땐 스튜디오', d: '쌓인 소식을 라디오·보고서로 바꿔 드려요. 퀴즈는 무료예요.' },
];
/* 앱(app.js memo.html · studio.html coachHooks) / 웹(coach.tsx COACH_STEPS) 대상 · 여백 · 말풍선 자리 순서 */
export const COACH_STEPS: StepDef[] = WEB
  ? [
      { id: 'fab', pad: 8, round: true, prefer: ['lt', 'up'], ...TEXT[0] },
      { id: 'ai', pad: 6, prefer: ['rt', 'lt', 'up'], ...TEXT[1] },
      { id: 'feed', pad: 4, prefer: ['rt', 'lt', 'up'], ...TEXT[2] },
      { id: 'studio', pad: 6, prefer: ['lt', 'up'], ...TEXT[3] },
    ]
  : [
      { id: 'fab', pad: 8, round: true, prefer: ['up'], ...TEXT[0] },
      { id: 'ai', pad: 6, prefer: ['up', 'dn'], ...TEXT[1] },
      { id: 'feed', pad: 4, prefer: ['dn', 'up'], ...TEXT[2] },
      { id: 'studio', pad: 6, prefer: ['dn', 'up'], ...TEXT[3] },
    ];
const N = COACH_STEPS.length;
const TIP_W = 320;
const EDGE = 16;
const GAP = 16;

/* 대상 등록 (화면이 그린 버튼·카드의 ref) */
type Measurable = { measureInWindow: (cb: (x: number, y: number, w: number, h: number) => void) => void };
const registry = new Map<string, { current: Measurable | null }>();
export function useCoachRef(id: string) {
  const ref = useRef<React.ComponentRef<typeof View>>(null);
  useEffect(() => {
    const r = ref as unknown as { current: Measurable | null };
    registry.set(id, r);
    return () => {
      if (registry.get(id) === r) registry.delete(id);
    };
  }, [id]);
  return ref;
}
const measure = (id: string) =>
  new Promise<Box | null>((res) => {
    const node = registry.get(id)?.current;
    if (!node) return res(null);
    node.measureInWindow((x, y, w, h) => res(w > 3 && h > 3 ? { x, y, w, h } : null));
  });

const radius = (b: Box, round?: boolean) => (round ? Math.min(b.w, b.h) / 2 : Math.min(14, b.h / 2, b.w / 2));
const holePath = (W: number, H: number, b: Box | null, round?: boolean) => {
  let d = `M0 0H${W}V${H}H0Z`;
  if (b && b.w > 0.5 && b.h > 0.5) {
    const r = radius(b, round);
    const { x, y, w, h } = b;
    d += ` M${x + r} ${y}H${x + w - r}A${r} ${r} 0 0 1 ${x + w} ${y + r}V${y + h - r}A${r} ${r} 0 0 1 ${x + w - r} ${y + h}H${x + r}A${r} ${r} 0 0 1 ${x} ${y + h - r}V${y + r}A${r} ${r} 0 0 1 ${x + r} ${y}Z`;
  }
  return d;
};

export function CoachOverlay() {
  const k = useMotionK();
  const insets = useSafeAreaInsets();
  const step = useCoach((s) => s.step);
  const go = useCoach((s) => s.go);
  const end = useCoach((s) => s.end);
  const done = useCoach((s) => s.done);
  const [vp, setVp] = useState({ w: 0, h: 0 });
  /* 단계마다 찾은 대상 (단계·화면 크기가 바뀌면 다시 찾을 때까지 준비 안 됨) */
  const [found, setFound] = useState<{ key: string; box: Box | null } | null>(null);
  const [hole, setHole] = useState<Box | null>(null);
  const [tipH, setTipH] = useState(0);
  const holeRef = useRef<Box | null>(null);
  const rootRef = useRef<React.ComponentRef<typeof View>>(null);
  const S = step != null && step >= 0 ? COACH_STEPS[step] : null;
  const findKey = `${step}:${vp.w}:${vp.h}`;
  const ready = step === -1 || found?.key === findKey;
  const target = step === -1 ? null : found?.key === findKey ? found.box : null;

  /* 대상 찾기: 자리가 멈출 때까지(8번 같은 자리 · 0.24초 뒤) 기다렸다가 잼. 2.6초 안에 못 찾으면 가운데 카드 (원본 measure) */
  useEffect(() => {
    if (step == null || !S) return;
    let dead = false;
    let stable = 0;
    let last = '';
    const t0 = Date.now();
    const tick = async () => {
      if (dead) return;
      const r0 = await measure(S.id);
      /* 대상 자리를 덮개 기준으로 (안드로이드는 창 기준 좌표에 상태 표시줄이 빠져 있음) */
      const o = await new Promise<{ x: number; y: number }>((res) => (rootRef.current ? rootRef.current.measureInWindow((x, y) => res({ x, y })) : res({ x: 0, y: 0 })));
      const r = r0 ? { ...r0, x: r0.x - o.x, y: r0.y - o.y } : null;
      if (dead) return;
      const b = r && vp.w ? (() => { const x = Math.max(4, r.x - S.pad); const y = Math.max(4, r.y - S.pad); return { x, y, w: Math.min(vp.w - 4, r.x + r.w + S.pad) - x, h: Math.min(vp.h - 4, r.y + r.h + S.pad) - y }; })() : null;
      const key = b ? [b.x, b.y, b.w, b.h].map(Math.round).join(',') : '';
      stable = b && key === last ? stable + 1 : 0;
      last = key;
      const waited = Date.now() - t0;
      if ((b && stable >= 8 && waited > 240) || waited > 2600) {
        setFound({ key: findKey, box: b });
        return;
      }
      setTimeout(tick, 33);
    };
    const t = setTimeout(tick, 33);
    return () => {
      dead = true;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, vp.w, vp.h]);

  /* 구멍 옮기기: 넘쳤다 멈추는 520ms (easeOutBack c=1.4) — 대상이 없으면 가운데로 접힘 */
  useEffect(() => {
    if (step == null || !ready) return;
    const to = target ?? (holeRef.current ? { x: holeRef.current.x + holeRef.current.w / 2, y: holeRef.current.y + holeRef.current.h / 2, w: 0, h: 0 } : { x: vp.w / 2, y: vp.h / 2, w: 0, h: 0 });
    const from = holeRef.current ?? { x: to.x + to.w / 2, y: to.y + to.h / 2, w: 0, h: 0 };
    const dur = 520 * k;
    const t0 = Date.now();
    let raf = 0;
    const f = () => {
      const p = dur < 20 ? 1 : Math.max(0, Math.min(1, (Date.now() - t0) / dur));
      const c = 1.4;
      const e = 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2);
      const b = { x: from.x + (to.x - from.x) * e, y: from.y + (to.y - from.y) * e, w: Math.max(0, from.w + (to.w - from.w) * e), h: Math.max(0, from.h + (to.h - from.h) * e) };
      holeRef.current = b;
      setHole(b);
      if (p < 1) raf = requestAnimationFrame(f);
    };
    raf = requestAnimationFrame(f);
    return () => cancelAnimationFrame(raf);
  }, [step, ready, target, vp.w, vp.h, k]);

  /* 끝나면 다음 시작을 위해 구멍 초기화 */
  useEffect(() => {
    if (step != null) return;
    const t = setTimeout(() => {
      holeRef.current = null;
      setHole(null);
      setFound(null);
    }, 0);
    return () => clearTimeout(t);
  }, [step]);

  /* 끝난 뒤 알림 (원본 coachdone: 홈 스낵바) */
  const [snack, setSnack] = useState<{ key: number; msg: string } | null>(null);
  const [doneKey, setDoneKey] = useState(done?.key);
  if (done && done.key !== doneKey) {
    setDoneKey(done.key);
    setSnack({ key: done.key, msg: done.finished ? '준비됐어요. 떠오른 생각 한 줄부터 적어 보세요' : WEB ? '사용법은 설정 › 정보에서 다시 볼 수 있어요' : '사용법은 MY › 도움말에서 다시 볼 수 있어요' });
  }
  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack((s) => (s && s.key === snack.key ? null : s)), 2400 * Math.max(k, 0.5) + 450);
    return () => clearTimeout(t);
  }, [snack, k]);

  const onRoot = (e: LayoutChangeEvent) => setVp({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height });
  const snackEl = WEB ? (
    <WebSnackbar visible={!!snack} message={snack?.msg ?? ''} check={done?.finished} style={st.webSnack} />
  ) : (
    <AppSnackbar visible={!!snack} message={snack?.msg ?? ''} style={[st.appSnack, { bottom: 1 + 65 + Math.max(size.tabBarPadBottom, insets.bottom) + 16 }]} />
  );
  if (step == null) return snack ? <View pointerEvents="box-none" style={StyleSheet.absoluteFill}>{snackEl}</View> : null;

  /* 말풍선 자리: 고른 순서대로 들어가는 첫 자리 (원본 place) */
  const W = vp.w;
  const H = vp.h;
  const tw = Math.min(TIP_W, W - EDGE * 2);
  const th = tipH || 170;
  const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
  let pos: { left: number; top: number; side: Side | 'no'; ax: number } = { left: (W - tw) / 2, top: Math.max(EDGE, (H - th) / 2), side: 'no', ax: 0 };
  if (target && S) {
    const t = target;
    const cx = t.x + t.w / 2;
    const cy = t.y + t.h / 2;
    let found = false;
    for (const side of S.prefer) {
      if (side === 'rt' && t.x + t.w + GAP + tw <= W - EDGE) {
        const top = clamp(cy - th / 2, EDGE, H - th - EDGE);
        pos = { left: t.x + t.w + GAP, top, side, ax: clamp(cy - top, 24, th - 24) };
      } else if (side === 'lt' && t.x - GAP - tw >= EDGE) {
        const top = clamp(cy - th / 2, EDGE, H - th - EDGE);
        pos = { left: t.x - GAP - tw, top, side, ax: clamp(cy - top, 24, th - 24) };
      } else if (side === 'dn' && t.y + t.h + GAP + th <= H - EDGE) {
        const left = clamp(cx - tw / 2, EDGE, W - tw - EDGE);
        pos = { left, top: t.y + t.h + GAP, side, ax: clamp(cx - left, 24, tw - 24) };
      } else if (side === 'up' && t.y - GAP - th >= EDGE) {
        const left = clamp(cx - tw / 2, EDGE, W - tw - EDGE);
        pos = { left, top: t.y - GAP - th, side, ax: clamp(cx - left, 24, tw - 24) };
      } else continue;
      found = true;
      break;
    }
    if (!found) pos = { left: clamp(cx - tw / 2, EDGE, W - tw - EDGE), top: clamp(t.y + t.h - th - 24, EDGE, H - th - EDGE), side: 'no', ax: 0 };
  }
  const shown = ready && W > 0;
  const next = () => (S ? (step! < N - 1 ? go(step! + 1) : end(true)) : go(0));
  const prev = () => (S ? (step! > 0 ? go(step! - 1) : undefined) : end(false));

  const body = (
    <View ref={rootRef} collapsable={false} style={StyleSheet.absoluteFill} onLayout={onRoot} onStartShouldSetResponder={() => true} accessibilityViewIsModal>
      {/* 덮개 · 고리는 다크에서도 원래 색 (원본 html.dark .u197-ov · .u197-ring) */}
      <Keep style={StyleSheet.absoluteFill} pointerEvents="none">
        {W > 0 ? (
          <Svg width={W} height={H}>
            <Path d={holePath(W, H, hole, S?.round)} fill="rgba(10,12,22,0.66)" fillRule="evenodd" />
          </Svg>
        ) : null}
        {shown && target && S && hole ? <Ring b={hole} r={radius(hole, S.round)} /> : null}
      </Keep>
      <Tip key={step} pos={pos} width={tw} shown={shown} onHeight={setTipH}>
        {S ? (
          <Pressable onPress={() => end(false)} accessibilityRole="button" style={st.x} hitSlop={6}>
            <Text style={st.xT}>건너뛰기</Text>
          </Pressable>
        ) : null}
        <Text style={st.small}>{S ? `${step! + 1} / ${N}` : '처음 오셨네요'}</Text>
        <Text style={st.b}>{S ? S.t : '30초만 둘러볼까요?'}</Text>
        <Text style={st.p}>{S ? S.d : '메모 쓰기부터 스튜디오까지, 꼭 필요한 4가지만 알려 드릴게요.'}</Text>
        <View style={st.tf}>
          <View style={st.dots}>{S ? COACH_STEPS.map((_, i) => <Dot key={i} on={i === step} />) : null}</View>
          {S ? (
            step! > 0 ? (
              <Btn label="이전" onPress={prev} />
            ) : null
          ) : (
            <Btn label="나중에" onPress={prev} />
          )}
          <Btn label={S ? (step === N - 1 ? '완료' : '다음') : '둘러보기'} onPress={next} primary />
        </View>
      </Tip>
    </View>
  );
  /* 웹: 메모 창 같은 Modal 보다 위에 오도록 Modal 로 그리고, 단계마다 다시 붙여 맨 위로 (원본 coach.tsx 는 body 끝에 portal) */
  return WEB ? (
    <Modal key={step} transparent visible animationType="none" onRequestClose={() => end(false)}>
      {body}
    </Modal>
  ) : (
    body
  );
}

/** 흰 고리 2px + 맥박 (원본 .u197-ring · ::after 1.5s: 바깥으로 2 → 12 · .9 → 0) */
function Ring({ b, r }: { b: Box; r: number }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (k < 1) return;
    const a = Animated.loop(Animated.timing(v, { toValue: 1, duration: 1500, easing: Easing.out(Easing.ease), useNativeDriver: false }));
    a.start();
    return () => a.stop();
  }, [v, k]);
  const grow = v.interpolate({ inputRange: [0, 1], outputRange: [2, 12] });
  return (
    <>
      <View style={[st.ring, { left: b.x - 2, top: b.y - 2, width: b.w + 4, height: b.h + 4, borderRadius: r + 2 }]} />
      <Animated.View
        style={[
          st.ring,
          {
            left: Animated.subtract(b.x, grow),
            top: Animated.subtract(b.y, grow),
            width: Animated.add(b.w, Animated.multiply(grow, 2)),
            height: Animated.add(b.h, Animated.multiply(grow, 2)),
            borderRadius: r + 6,
            opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0.9, 0] }),
          },
        ]}
      />
    </>
  );
}

/** 말풍선 (원본 .u197-tip: 흰 · 라운드 18 · 그림자 · 꼬리 14 회전 · 처음엔 톡 튀며 나타남) */
function Tip({ pos, width, shown, onHeight, children }: { pos: { left: number; top: number; side: Side | 'no'; ax: number }; width: number; shown: boolean; onHeight: (h: number) => void; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!shown) return;
    const a = Animated.timing(v, { toValue: 1, duration: 350 * k, easing: Easing.bezier(0.34, 1.45, 0.64, 1), useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [shown, v, k]);
  return (
    <Animated.View
      onLayout={(e) => onHeight(e.nativeEvent.layout.height)}
      accessibilityRole="alert"
      accessibilityLabel="화면 안내"
      style={[st.tip, { left: pos.left, top: pos.top, width, opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [pos.side === 'up' ? -6 : 6, 0] }) }] }]}
    >
      {pos.side === 'dn' || pos.side === 'up' ? <View style={[st.arrow, pos.side === 'dn' ? { top: -6 } : { bottom: -6 }, { left: pos.ax - 7 }]} /> : null}
      {/* 웹 옆 꼬리 (원본 v2.css .u197-tip.rt · .lt) */}
      {pos.side === 'rt' || pos.side === 'lt' ? <View style={[st.arrow, pos.side === 'rt' ? { left: -6 } : { right: -6 }, { top: pos.ax - 7 }]} /> : null}
      {children}
    </Animated.View>
  );
}

function Dot({ on }: { on: boolean }) {
  return <View style={[st.dot, on && st.dotOn]} />;
}

function Btn({ label, onPress, primary }: { label: string; onPress: () => void; primary?: boolean }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [st.btn, primary && st.btnP, pressed && { opacity: 0.85 }]}>
      <Text style={[st.btnT, primary && { color: '#FFFFFF' }]}>{label}</Text>
    </Pressable>
  );
}

const st = StyleSheet.create({
  ring: { position: 'absolute', borderWidth: 2, borderColor: '#FFFFFF' },
  tip: { position: 'absolute', paddingTop: 18, paddingHorizontal: 20, paddingBottom: 16, borderRadius: 18, backgroundColor: '#FFFFFF', shadowColor: '#000000', shadowOpacity: 0.45, shadowRadius: 15, shadowOffset: { width: 0, height: 14 }, elevation: 12 },
  arrow: { position: 'absolute', width: 14, height: 14, borderRadius: 2, backgroundColor: '#FFFFFF', transform: [{ rotate: '45deg' }] },
  /* 앱 = app.css .u197 (보라) · 웹 = v2.css .u197 (검정 · 제목 20/29 · 본문 15/23 · 버튼 40) */
  x: WEB ? { position: 'absolute', right: 12, top: 12, height: 28, paddingHorizontal: 8, borderRadius: 8, justifyContent: 'center', zIndex: 2 } : { position: 'absolute', right: 10, top: 10, height: 32, paddingHorizontal: 8, justifyContent: 'center', zIndex: 2 },
  xT: { fontSize: 13, fontWeight: '700', color: WEB ? '#8E8A97' : appColor.ink3 },
  small: { fontSize: 13, lineHeight: 20, fontWeight: '700', color: WEB ? '#8E8A97' : appColor.ink3 },
  b: WEB ? { marginTop: 2, fontSize: 20, lineHeight: 29, fontWeight: '700', color: '#15171A' } : { marginTop: 2, fontSize: 19, lineHeight: 27, fontWeight: '800', color: appColor.ink, letterSpacing: -0.3 },
  p: WEB ? { marginTop: 4, marginBottom: 14, fontSize: 15, lineHeight: 23, color: '#575B63' } : { marginTop: 4, marginBottom: 14, fontSize: 14.5, lineHeight: 22, color: appColor.ink2 },
  tf: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  dots: { flexDirection: 'row', gap: 5, marginRight: 'auto' },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D5D8DD' },
  dotOn: { width: 18, backgroundColor: WEB ? '#111111' : appColor.deepPurple },
  btn: { height: WEB ? 40 : 44, paddingHorizontal: 16, borderRadius: 12, backgroundColor: WEB ? '#F2F3F4' : '#F2F2F5', justifyContent: 'center' },
  btnP: { backgroundColor: WEB ? '#111111' : appColor.accent },
  btnT: { fontSize: 15, fontWeight: '700', color: appColor.ink },
  appSnack: { position: 'absolute', left: 12, right: 12 },
  webSnack: { position: 'absolute', bottom: 30 },
});
