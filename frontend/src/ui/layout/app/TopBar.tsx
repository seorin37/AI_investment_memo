import React, { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View, type TextStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { Logo } from '@/ui/icons/Icon';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { Avatar } from '@/ui/shared/Avatar';
import { AppIconButton } from '@/ui/shared/IconButton';
import { appColor, ft } from '@/ui/theme';
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

/* 원본 실측 (412 폭, 상태 바 36 아래) */
const TAB_TITLE: TextStyle = { ...ft(21), fontWeight: '800', color: appColor.ink };
const SPEC: Record<TopBarPreset, Spec> = {
  home: { h: 60, padL: 18, padR: 12, bg: appColor.bg, btn: 42, btnGap: 2, avatarGap: 6, logo: true },
  start: { h: 56, padL: 18, padR: 10, bg: appColor.bg, btn: 40, btnGap: 2, avatarGap: 6, logo: true },
  updates: { h: 60, padL: 18, padR: 12, bg: appColor.bg, btn: 40, btnGap: 2, avatarGap: 6, title: TAB_TITLE },
  stocks: { h: 60, padL: 18, padR: 12, bg: appColor.bg, btn: 40, btnGap: 2, avatarGap: 6, title: TAB_TITLE },
  journal: { h: 60, padL: 18, padR: 12, bg: appColor.bg, btn: 40, btnGap: 6, avatarGap: 6, title: TAB_TITLE },
  studio: { h: 56, padL: 18, padR: 10, bg: appColor.bg, btn: 42, btnGap: 0, avatarGap: 6, title: TAB_TITLE },
  board: { h: 56, padL: 6, padR: 8, bg: appColor.surface, btn: 42, btnGap: 0, avatarGap: 0, back: 42, backIcon: 'back2', titleGap: 2, title: { ...ft(20), fontWeight: '700', color: appColor.ink } },
  memoDetail: { h: 56, padL: 6, padR: 6, bg: appColor.surface, btn: 42, btnGap: 0, avatarGap: 0, back: 42, backIcon: 'back', titleGap: 0, title: { ...ft(17), fontWeight: '600', color: appColor.ink } },
  company: { h: 56, padL: 6, padR: 6, bg: appColor.bg, btn: 40, btnGap: 0, avatarGap: 0, back: 40, backIcon: 'back', titleGap: 4, title: { ...ft(18), fontWeight: '700', color: appColor.ink } },
  my: { h: 58, padL: 10, padR: 10, bg: appColor.bg, btn: 42, btnGap: 0, avatarGap: 0, back: 42, backIcon: 'back', titleGap: 6, title: { ...ft(19), fontWeight: '700', color: appColor.ink } },
  market: { h: 56, padL: 6, padR: 6, bg: appColor.surface, btn: 42, btnGap: 0, avatarGap: 0, back: 42, backIcon: 'back', titleGap: 0, title: { ...ft(17), fontWeight: '700', color: appColor.ink } },
};

/**
 * 앱 상단 바. 원본의 가짜 상태 바(36) 대신 기기 상태 바 높이(안전 영역)만큼 같은 바탕으로 띄움.
 * 뒤로 아이콘은 원본 11.17 결정대로 꺾쇠(‹).
 */
export function TopBar({ preset, title, onBack, actions = [], avatar, showLine = false }: TopBarProps) {
  const s = SPEC[preset];
  const insets = useSafeAreaInsets();
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
        <BarLine on={showLine} />
      </View>
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
  line: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 1, backgroundColor: appColor.line },
});
