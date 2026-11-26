import React, { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View, type TextStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { Logo } from '@/ui/icons/Icon';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { Avatar } from '@/ui/shared/Avatar';
import { AppIconButton } from '@/ui/shared/IconButton';
import { nf } from '@/ui/shared/app/nf';
import { appColor, ft } from '@/ui/theme';
import { TAB_BAR_H, useTabScrolled, useTabScrollY } from './TabFrame';
import type { TopBarPreset, TopBarProps } from './TopBar.types';

type Spec = {
  h: number;
  padL: number;
  padR: number;
  bg: string;
  /** 오른쪽 버튼 기본 크기 · 버튼 사이 · 마지막 버튼과 아바타 사이 */
  btn: number;
  btnGap: number;
  avatarGap: number;
  /** 뒤로 버튼 크기 · 뒤로 버튼과 제목 사이 */
  back?: number;
  backIcon?: 'back' | 'back2';
  titleGap?: number;
  title?: TextStyle;
  logo?: boolean;
};

/* 부제목: 제목 줄(높이 24, 세로 가운데 32 → 아래 끝 44) 아래 6 = 50 ~ 64. 바 높이 안이라 부제목이 있어도 없어도 본문 시작이 같음 */
const SUB_TOP = 50;
/* 부제목이 올라가며 잘리는 위치 (제목 바로 아래) */
const SUB_CLIP = 46;
/* 탭 5개 공용 (높이 64 · 좌우 20 · 부제목은 제목 아래 6 · 첫 본문 간격 12 는 TabScroll) */
const TAB: Spec = { h: TAB_BAR_H, padL: 20, padR: 20, bg: appColor.bg, btn: 40, btnGap: 2, avatarGap: 6, title: { ...nf(21), fontWeight: '800', color: appColor.ink } };
/* 나머지는 원본 실측 (412 폭, 상태 바 36 아래) */
const SPEC: Record<TopBarPreset, Spec> = {
  home: { ...TAB, logo: true },
  start: { h: 56, padL: 18, padR: 10, bg: appColor.bg, btn: 40, btnGap: 2, avatarGap: 6, logo: true },
  updates: TAB,
  stocks: TAB,
  journal: TAB,
  studio: TAB,
  board: { h: 56, padL: 6, padR: 8, bg: appColor.bg, btn: 42, btnGap: 0, avatarGap: 0, back: 42, backIcon: 'back2', titleGap: 2, title: { ...ft(20), fontWeight: '700', color: appColor.ink } },
  memoDetail: { h: 56, padL: 6, padR: 6, bg: appColor.surface, btn: 42, btnGap: 0, avatarGap: 0, back: 42, backIcon: 'back', titleGap: 0, title: { ...ft(17), fontWeight: '600', color: appColor.ink } },
  company: { h: 56, padL: 6, padR: 6, bg: appColor.bg, btn: 40, btnGap: 0, avatarGap: 0, back: 40, backIcon: 'back', titleGap: 4, title: { ...ft(18), fontWeight: '700', color: appColor.ink } },
  my: { h: 58, padL: 10, padR: 10, bg: appColor.bg, btn: 42, btnGap: 0, avatarGap: 0, back: 42, backIcon: 'back', titleGap: 6, title: { ...ft(19), fontWeight: '700', color: appColor.ink } },
  market: { h: 56, padL: 6, padR: 6, bg: appColor.surface, btn: 42, btnGap: 0, avatarGap: 0, back: 42, backIcon: 'back', titleGap: 0, title: { ...ft(17), fontWeight: '700', color: appColor.ink } },
};

/**
 * 앱 상단 바. 원본의 가짜 상태 바(36) 대신 기기 상태 바 높이(안전 영역)만큼 같은 바탕으로 띄움.
 * 뒤로 아이콘은 원본 11.17 결정대로 꺾쇠(‹).
 */
export function TopBar({ preset, title, subtitle, onBack, actions = [], avatar, showLine = false }: TopBarProps) {
  const s = SPEC[preset];
  const insets = useSafeAreaInsets();
  const y = useTabScrollY();
  /* 탭 화면: 스크롤을 시작하면 아래 선 */
  const scrolled = useTabScrolled();
  const rise = s.h - SUB_CLIP;
  return (
    <View style={{ paddingTop: insets.top, backgroundColor: s.bg }}>
      <View style={[st.row, { height: s.h, paddingLeft: s.padL, paddingRight: s.padR, backgroundColor: s.bg }]}>
        {s.back ? <AppIconButton label="뒤로" size={s.back} icon={s.backIcon} iconSize={22} color={appColor.ink} onPress={onBack} /> : null}
        {s.logo ? (
          <View style={st.flex}>
            <Logo kind="app" size={110} />
          </View>
        ) : (
          <View style={[st.flex, { marginLeft: s.titleGap ?? 0 }]}>
            {title ? (
              <Text style={[s.title, st.shrink]} numberOfLines={1}>
                {title}
              </Text>
            ) : null}
          </View>
        )}
        {actions.map((a, i) => (
          <AppIconButton key={a.label} label={a.label} size={a.size ?? s.btn} icon={a.icon} iconSize={a.iconSize ?? 22} color={a.color ?? appColor.ink} onPress={a.onPress} style={i > 0 ? { marginLeft: s.btnGap } : undefined} />
        ))}
        {avatar ? (
          <Pressable onPress={avatar.onPress} accessibilityRole="button" accessibilityLabel="MY" hitSlop={6} style={{ marginLeft: actions.length ? s.avatarGap : 0 }}>
            <Avatar name={avatar.name} photoUrl={avatar.photoUrl} size={32} variant="app" />
          </Pressable>
        ) : null}
      </View>
      {subtitle ? (
        <View pointerEvents="none" style={[st.subClip, { top: insets.top + SUB_CLIP, left: s.padL, right: s.padR, height: rise }]}>
          <Animated.View style={y ? { transform: [{ translateY: y.interpolate({ inputRange: [0, rise], outputRange: [0, -rise], extrapolate: 'clamp' }) }] } : null}>
            <Text style={st.sub} numberOfLines={1}>
              {subtitle}
            </Text>
          </Animated.View>
        </View>
      ) : null}
      <BarLine on={showLine || scrolled} />
    </View>
  );
}

/** 아래 선: 0.25초 페이드 */
function BarLine({ on }: { on: boolean }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(on ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: on ? 1 : 0, duration: 250 * k, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [on, v, k]);
  return <Animated.View pointerEvents="none" style={[st.line, { opacity: v }]} />;
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center' },
  flex: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center' },
  shrink: { flexShrink: 1 },
  /* 원본 내 종목 .sub · 스튜디오 .subr: 12.5 · ink3 */
  subClip: { position: 'absolute', overflow: 'hidden' },
  sub: { marginTop: SUB_TOP - SUB_CLIP, fontSize: 13, lineHeight: 14, color: '#6B7079' },
  line: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 1, backgroundColor: appColor.line },
});
