import React, { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import Svg, { ClipPath, Defs, Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import type { Memo } from '@/types/models';
import { AppPlug, CheckMark, Dots, WebPlug } from '@/ui/icons/BoardGlyphs';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, fpx, ft } from '@/ui/theme';
import { AppTape, PaperFace, WebTape } from './MemoPaper';
import { mmdd, oneLine } from './memoFormat';
import { usePaper } from '@/ui/shared/Dark';

/** 고르기 원 (원본 .gchk: 25 · 위 -8 · 왼쪽 -6 · 흰 바탕 + 안쪽 2 #C9CDD4 + 바깥 흰 2 / 고르면 #8569E3 · 등장 scale .5 → 1, .35s spring) */
export function SelCircle({ visible, on, size = 25, style }: { visible: boolean; on: boolean; size?: number; style?: object }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(visible ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: visible ? 1 : 0, duration: 350 * k, easing: curve.spring, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [visible, v, k]);
  return (
    <Animated.View
      pointerEvents="none"
      style={[
        { width: size + 4, height: size + 4, borderRadius: (size + 4) / 2, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center', opacity: v, transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.5, 1] }) }] },
        style,
      ]}
    >
      <View style={{ width: size, height: size, borderRadius: size / 2, alignItems: 'center', justifyContent: 'center', backgroundColor: on ? appColor.accent : '#FFFFFF', borderWidth: on ? 0 : 2, borderColor: '#C9CDD4' }}>
        {on ? <CheckMark size={14} /> : null}
      </View>
    </Animated.View>
  );
}

/** 빨간 숫자 배지 (원본 .nb: 22 · 라운드 11 · 흰 테두리 2 · 12px 700 / 웹: 24 · 13px 500) */
function NumBadge({ n, variant }: { n: number; variant: 'app' | 'web' }) {
  const s = variant === 'app' ? 22 : 24;
  return (
    <View pointerEvents="none" style={[st.badge, { width: s, height: s, borderRadius: s / 2 }, variant === 'app' ? st.badgeApp : st.badgeWeb]}>
      <Text style={variant === 'app' ? st.badgeTApp : st.badgeTWeb}>{n}</Text>
    </View>
  );
}

export interface AppMemoCardProps {
  memo: Memo;
  width: number;
  height: number;
  selecting: boolean;
  selected: boolean;
  /** AI 사용량 다 씀: 플러그 흐리게 (원본 .spent .plug) */
  aiSpent?: boolean;
  onPress: () => void;
  onLongPress: () => void;
}

/**
 * 앱 2열 메모 카드 (원본 memo.html .grid .item)
 * 종이: PaperFace (r16 · 귀퉁이 24) / 안쪽 14·13 / 날짜 줄 최소 22 (날짜 11.5px 500 #4A4A55 · 플러그 22 원 rgba(255,255,255,.8))
 * 제목 15px 800 줄 1.36 · 위아래 6 · 두 줄 / 본문 12.5px 줄 1.5 #2E2E38 · 세 줄
 * 누르면 .12초 뒤 .965 로 줄어듦 (.45s cubic-bezier(.3,1.3,.5,1)) · .48초 꾹 누르면 고르기
 */
export function AppMemoCard({ memo: m, width, height, selecting, selected, aiSpent, onPress, onLongPress }: AppMemoCardProps) {
  const paper = usePaper();
  const k = useMotionK();
  const p = paper[m.color];
  const [s] = useState(() => new Animated.Value(1));
  const scaleTo = (v: number, delay = 0) => Animated.timing(s, { toValue: v, duration: 450 * k, delay: delay * k, easing: curve.land, useNativeDriver: NATIVE }).start();
  const d = `M16 0H${width - 16}A16 16 0 0 1 ${width} 16V${height - 24}L${width - 24} ${height}H16A16 16 0 0 1 0 ${height - 16}V16A16 16 0 0 1 16 0Z`;
  return (
    <View style={{ width, height }}>
      <Pressable
        onPress={onPress}
        onLongPress={onLongPress}
        delayLongPress={480}
        onPressIn={() => scaleTo(0.965, 120)}
        onPressOut={() => scaleTo(1)}
        accessibilityRole="button"
        accessibilityLabel={m.title}
        accessibilityState={{ selected }}
      >
        <Animated.View style={{ width, height, transform: [{ scale: s }] }}>
          <PaperFace width={width} height={height} bg={p.bg} accent={p.accent} variant="app" />
          {selected ? (
            /* 원본: inset 0 0 0 2.5px var(--a) — 종이 모양 안쪽 테두리 */
            <Svg width={width} height={height} style={StyleSheet.absoluteFill} pointerEvents="none">
              <Defs>
                <ClipPath id={`sel${m.id}`}>
                  <Path d={d} />
                </ClipPath>
              </Defs>
              <Path d={d} fill="none" stroke={appColor.accent} strokeWidth={5} clipPath={`url(#sel${m.id})`} />
            </Svg>
          ) : null}
          <View style={st.g}>
            <View style={st.dtr}>
              <Text style={st.dt}>{mmdd(m.created_at)} 작성</Text>
              {m.ai_linked ? (
                <View style={[st.plug, aiSpent && st.plugSpent]}>
                  <View style={{ opacity: aiSpent ? 0.4 : 1 }}>
                    <AppPlug size={12} color={aiSpent ? '#9A9EA7' : '#16161C'} />
                  </View>
                </View>
              ) : null}
            </View>
            <Text style={st.tt} numberOfLines={2}>
              {m.title}
            </Text>
            <Text style={st.bd} numberOfLines={3}>
              {oneLine(m.body)}
            </Text>
          </View>
        </Animated.View>
      </Pressable>
      {m.pinned ? <AppTape color={p.accent} /> : null}
      {m.unread_updates > 0 ? (
        <View style={st.nbAt} pointerEvents="none">
          <NumBadge n={m.unread_updates} variant="app" />
        </View>
      ) : null}
      <SelCircle visible={selecting} on={selected} style={st.gchk} />
    </View>
  );
}

export interface WebMemoCardProps {
  memo: Memo;
  selecting: boolean;
  selected: boolean;
  onOpen: () => void;
  onPin: () => void;
  onToggleAi: () => void;
  onMenu: (at: { x: number; y: number }) => void;
  onPick: () => void;
  /** 크레딧을 다 써서 멈춤(끄기 대기): AI 플러그를 꺼진 모양으로 (2026-11-24) */
  aiSpent?: boolean;
}

type HoverState = { pressed: boolean; hovered?: boolean };

function Tip({ children, style }: { children: string; style: object }) {
  return (
    <View pointerEvents="none" style={[st.tip, style]}>
      <Text style={st.tipT}>{children}</Text>
    </View>
  );
}

/**
 * 웹 메모 카드 (원본 board.tsx MemoCard: 276 칸 · 높이 200 · 종이 r16 · 귀퉁이 30 · 안쪽 위 18 · 좌우 20 · 아래 40 · 사이 8)
 * 날짜 13/20 500 #4A4A55 · 플러그 28 원 (켜짐 rgba(255,255,255,.8) / 꺼짐 .4) · 제목 20px bold 줄 1.36 두 줄 · 본문 14px 줄 1.5 두 줄 #2E2E38
 * 테이프 84×34 (위 -16): 고정이면 붙은 테이프 (hover 시 떼려는 모양) · 아니면 hover 시 점선 · 배지 24 (위 -10 · 오른쪽 -10) · ⋯ 메뉴 hover (아래 8 · 왼쪽 12)
 * hover: 종이가 위로 3 · -.3° 기울고 그림자
 */
export function WebMemoCard({ memo: m, selecting, selected, onOpen, onPin, onToggleAi, onMenu, onPick, aiSpent }: WebMemoCardProps) {
  const aiOn = m.ai_linked && !aiSpent;
  const paper = usePaper();
  const p = paper[m.color];
  const [hov, setHov] = useState(false);
  const [tape, setTape] = useState(false);
  const [plug, setPlug] = useState(false);
  return (
    <View
      style={[st.web, (tape || plug) && { zIndex: 20 }]}
      onPointerEnter={() => setHov(true)}
      onPointerLeave={() => {
        setHov(false);
        setTape(false);
        setPlug(false);
      }}
    >
      {/* 원본도 카드 바깥은 div (안에 플러그 버튼이 있어 button 으로 두면 웹에서 button 이 겹침) */}
      <Pressable onPress={selecting ? onPick : onOpen} accessibilityLabel={m.title} style={[st.webPaperWrap, hov && !selecting && st.webHover]}>
        <PaperFace width={276} height={200} bg={p.bg} accent={p.accent} variant="web" />
        <View style={st.webIn}>
          <View style={st.webTop}>
            <Text style={st.webDate}>{mmdd(m.created_at)} 작성</Text>
            <Pressable
              onPress={onToggleAi}
              onHoverIn={() => setPlug(true)}
              onHoverOut={() => setPlug(false)}
              accessibilityRole="button"
              accessibilityLabel={aiOn ? 'AI 연결 끄기' : 'AI 연결 켜기'}
              accessibilityState={{ selected: aiOn }}
              style={[st.webPlug, { backgroundColor: aiOn ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.4)' }, plug && st.webPlugHover]}
            >
              <WebPlug on={aiOn} />
            </Pressable>
          </View>
          <Text style={st.webTitle} numberOfLines={2}>
            {m.title}
          </Text>
          <Text style={st.webBody} numberOfLines={2}>
            {oneLine(m.body)}
          </Text>
        </View>
      </Pressable>
      {/* 테이프 칸 (84×34, 가운데 · 위 -16) */}
      <Pressable onPress={onPin} onHoverIn={() => setTape(true)} onHoverOut={() => setTape(false)} accessibilityRole="button" accessibilityLabel={m.pinned ? '테이프 떼기' : '테이프 붙이기 · 칸 맨 위로'} style={st.webTape}>
        {m.pinned ? <WebTape color={p.accent} state={tape ? 'lift' : 'on'} /> : hov ? <WebTape color={p.accent} state="dash" /> : null}
      </Pressable>
      {tape ? <Tip style={st.tipTape}>{m.pinned ? '눌러서 테이프 떼기' : '눌러서 테이프 붙이기 · 칸 맨 위로'}</Tip> : null}
      {plug && !aiOn ? <Tip style={st.tipPlug}>{m.ai_linked ? 'AI 사용량을 다 써서 멈췄어요' : 'AI 연결 켜기'}</Tip> : null}
      {m.unread_updates > 0 ? (
        <View style={st.webBadgeAt} pointerEvents="none">
          <NumBadge n={m.unread_updates} variant="web" />
        </View>
      ) : null}
      {selecting ? (
        <Pressable onPress={onPick} accessibilityRole="checkbox" accessibilityState={{ checked: selected }} accessibilityLabel={`${m.title} 선택`} style={({ hovered }: HoverState) => [st.webPickCover, hovered && !selected && { backgroundColor: 'rgba(0,0,0,0.03)' }]}>
          {selected ? (
            <Svg width={276} height={200} style={StyleSheet.absoluteFill} pointerEvents="none">
              <Path d="M16 0H260A16 16 0 0 1 276 16V170L246 200H16A16 16 0 0 1 0 184V16A16 16 0 0 1 16 0Z" fill="none" stroke="#111111" strokeWidth={5} clipPath="url(#webpick)" />
              <Defs>
                <ClipPath id="webpick">
                  <Path d="M16 0H260A16 16 0 0 1 276 16V170L246 200H16A16 16 0 0 1 0 184V16A16 16 0 0 1 16 0Z" />
                </ClipPath>
              </Defs>
            </Svg>
          ) : null}
          <View style={st.webPick}>
            <Pick on={selected} />
          </View>
        </Pressable>
      ) : hov ? (
        <Pressable
          onPress={(e) => onMenu({ x: e.nativeEvent.pageX, y: e.nativeEvent.pageY + 6 })}
          accessibilityRole="button"
          accessibilityLabel="메모 메뉴"
          style={({ hovered }: HoverState) => [st.webMenu, hovered && { backgroundColor: 'rgba(255,255,255,0.6)' }]}
        >
          <Dots color="#4A4A55" />
        </Pressable>
      ) : null}
    </View>
  );
}

/** 웹 고르기 동그라미 (원본 memox.tsx Pick: 22 · 고르면 #111 · 아니면 흰 + 안쪽 1.6 #C9CCD2) */
export function Pick({ on }: { on: boolean }) {
  return (
    <View style={{ width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: on ? '#111111' : '#FFFFFF', borderWidth: on ? 0 : 1.6, borderColor: '#C9CCD2' }}>
      {on ? <CheckMark kind="pick" size={12} stroke={1.8} /> : null}
    </View>
  );
}

const st = StyleSheet.create({
  g: { paddingTop: 14, paddingHorizontal: 13 },
  dtr: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 22 },
  dt: { ...ft(11.5), fontWeight: '500', color: '#4A4A55', flexShrink: 1 },
  plug: { marginLeft: 'auto', width: 22, height: 22, borderRadius: 11, backgroundColor: 'rgba(255,255,255,0.8)', alignItems: 'center', justifyContent: 'center' },
  plugSpent: { backgroundColor: '#E9EAEE' },
  tt: { ...ft(15, 1.36), fontWeight: '800', color: appColor.ink, marginVertical: 6 },
  bd: { ...ft(12.5, 1.5), color: '#2E2E38' },
  nbAt: { position: 'absolute', top: -7, right: -7 },
  gchk: { position: 'absolute', top: -10, left: -8 },
  badge: { borderWidth: 2, borderColor: '#FFFFFF', backgroundColor: appColor.red, alignItems: 'center', justifyContent: 'center' },
  badgeApp: {},
  badgeWeb: {},
  badgeTApp: { ...ft(12, 1), fontWeight: '700', color: '#FFFFFF' },
  badgeTWeb: { ...fpx(13, 20), fontWeight: '500', color: '#FFFFFF' },
  web: { width: 276, height: 200 },
  webPaperWrap: { width: 276, height: 200, borderRadius: 16, shadowColor: '#111111', shadowOpacity: 0, shadowRadius: 15, shadowOffset: { width: 0, height: 16 } },
  /* 원본 .paper:hover — translateY(-3px) rotate(-.3deg) · 0 16px 30px -18px rgba(17,17,17,.35) */
  webHover: { transform: [{ translateY: -3 }, { rotate: '-0.3deg' }], shadowOpacity: 0.35, elevation: 6 },
  webIn: { paddingTop: 18, paddingHorizontal: 20, paddingBottom: 40, gap: 8 },
  webTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  webDate: { ...fpx(13, 20), fontWeight: '500', color: '#4A4A55' },
  webPlug: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  webPlugHover: { borderWidth: 1, borderColor: 'rgba(22,22,28,0.25)' },
  webTitle: { ...fpx(20, 27.2), fontWeight: '700', color: '#16161C' },
  webBody: { ...fpx(14, 21), color: '#2E2E38' },
  webTape: { position: 'absolute', left: 96, top: -16, width: 84, height: 34, zIndex: 10 },
  webBadgeAt: { position: 'absolute', right: -10, top: -10, zIndex: 10 },
  webMenu: { position: 'absolute', bottom: 8, left: 12, width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center', zIndex: 10 },
  webPickCover: { ...StyleSheet.absoluteFill, zIndex: 20, borderTopLeftRadius: 16, borderTopRightRadius: 16, borderBottomLeftRadius: 16 },
  webPick: { position: 'absolute', bottom: 12, left: 12 },
  tip: { position: 'absolute', zIndex: 30, borderRadius: 8, backgroundColor: '#16161C', paddingHorizontal: 10, paddingVertical: 6 },
  tipT: { ...fpx(13, 20), fontWeight: '500', color: '#FFFFFF' },
  tipTape: { top: -56, alignSelf: 'center' },
  tipPlug: { right: 0, top: -28 },
});
