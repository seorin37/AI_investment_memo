import React, { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { AppIcon } from '@/ui/icons/Icon';
import { MenuIcon, SelIcon } from '@/ui/icons/BoardGlyphs';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { appColor, curve, fpx, ft, webColor } from '@/ui/theme';

/**
 * 앱 고르기 머리 (원본 memo.html .selhdr: 흰 · 높이 56 · 왼쪽 6 · 오른쪽 12 · 사이 4
 * ✕ 42 · 'N개 선택' 18px 700 · '전체 선택'/'선택 해제' 14px 700 #6A42AB · 안쪽 8). 상단 바 자리에 바꿔 끼움.
 */
export function AppSelectHeader({ count, allSelected, onClose, onToggleAll }: { count: number; allSelected: boolean; onClose: () => void; onToggleAll: () => void }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ paddingTop: insets.top, backgroundColor: appColor.bg }}>
      <View style={st.hdr}>
        <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="선택 끝내기" hitSlop={1} style={st.x}>
          <AppIcon name="close" size={20} color={appColor.ink} />
        </Pressable>
        <Text style={st.cnt} numberOfLines={1}>
          {count}개 선택
        </Text>
        <Pressable onPress={onToggleAll} accessibilityRole="button" style={st.all}>
          <Text style={st.allT}>{allSelected ? '선택 해제' : '전체 선택'}</Text>
        </Pressable>
      </View>
    </View>
  );
}

export type AppSelAction = 'pin' | 'color' | 'ai' | 'copy' | 'del';

/**
 * 앱 고르기 막대 (원본 .selbar: 탭바 자리 · 높이 80 · 아래 14 · 흰 · 위 선 · 아래에서 올라옴 .38s spring
 * 버튼 5개: 아이콘 22 · 11.5px #3F434A · 사이 3 · 못 쓰면 .3 · 휴지통 빨강)
 */
export function AppSelectBar({ visible, pinLabel, aiLabel, disabled, onAction }: { visible: boolean; pinLabel: string; aiLabel: string; disabled: Partial<Record<AppSelAction, boolean>>; onAction: (a: AppSelAction) => void }) {
  const insets = useSafeAreaInsets();
  const k = useMotionK();
  const padB = Math.max(14, insets.bottom);
  const [v] = useState(() => new Animated.Value(visible ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: visible ? 1 : 0, duration: 380 * k, easing: curve.spring, useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [visible, v, k]);
  const H = 66 + padB;
  const items: { a: AppSelAction; label: string }[] = [
    { a: 'pin', label: pinLabel },
    { a: 'color', label: '색상' },
    { a: 'ai', label: aiLabel },
    { a: 'copy', label: '복사' },
    { a: 'del', label: '휴지통' },
  ];
  return (
    <Animated.View pointerEvents={visible ? 'auto' : 'none'} style={[st.bar, { height: H, paddingBottom: padB, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [H, 0] }) }] }]}>
      {items.map((it) => {
        const color = it.a === 'del' ? appColor.red : appColor.tabInk;
        const off = !!disabled[it.a];
        return (
          <Pressable key={it.a} disabled={off} onPress={() => onAction(it.a)} accessibilityRole="button" accessibilityLabel={it.label} accessibilityState={{ disabled: off }} style={[st.sb, off && { opacity: 0.3 }]}>
            <SelIcon k={it.a} color={color} />
            <Text style={[st.sbT, { color }]} numberOfLines={1}>
              {it.label}
            </Text>
          </Pressable>
        );
      })}
    </Animated.View>
  );
}

type HoverState = { pressed: boolean; hovered?: boolean };

function WebBarBtn({ label, onPress, disabled, danger, icon }: { label: string; onPress: () => void; disabled?: boolean; danger?: boolean; icon?: 'pin' | 'copy' | 'trash' }) {
  const color = danger ? '#FF8A8F' : '#FFFFFF';
  return (
    <Pressable disabled={disabled} onPress={onPress} accessibilityRole="button" style={({ hovered }: HoverState) => [st.wb, hovered && { backgroundColor: 'rgba(255,255,255,0.1)' }, disabled && { opacity: 0.4 }]}>
      {icon ? <MenuIcon k={icon} color={color} /> : null}
      <Text style={[st.wbT, { color }]}>{label}</Text>
    </Pressable>
  );
}

/**
 * 웹 고르기 막대 (원본 memox.tsx SelectBar: 가운데 아래 28 · 검정 #15171A · 높이 56 · 라운드 18 · 왼 20 · 오른 8
 * 'N개 선택' 15 bold · '전체 선택 N'/'전체 해제' · | · 고정 · 복사 · 휴지통(#FF8A8F) · | · 선택 끝내기 (14 bold · 40 · 라운드 10))
 * 위치는 부모가 정함.
 */
export function WebSelectBar({ n, total, all, onAll, onPin, onCopy, onTrash, onEnd, extra }: { n: number; total: number; all: boolean; onAll: () => void; onPin?: () => void; onCopy?: () => void; onTrash: () => void; onEnd: () => void; extra?: { label: string; onPress: () => void }[] }) {
  return (
    <View style={st.web}>
      <Text style={st.webN}>{n}개 선택</Text>
      <Pressable onPress={onAll} accessibilityRole="button" style={({ hovered }: HoverState) => [st.wb, st.webAll, hovered && { backgroundColor: 'rgba(255,255,255,0.1)' }]}>
        <Text style={[st.wbT, { color: 'rgba(255,255,255,0.8)' }]}>{all ? '전체 해제' : `전체 선택 ${total}`}</Text>
      </Pressable>
      <View style={st.webDiv} />
      {extra?.map((e) => <WebBarBtn key={e.label} label={e.label} disabled={!n} onPress={e.onPress} />)}
      {onPin ? <WebBarBtn label="고정" icon="pin" disabled={!n} onPress={onPin} /> : null}
      {onCopy ? <WebBarBtn label="복사" icon="copy" disabled={!n} onPress={onCopy} /> : null}
      <WebBarBtn label="휴지통" icon="trash" danger disabled={!n} onPress={onTrash} />
      <View style={st.webDiv} />
      <WebBarBtn label="선택 끝내기" onPress={onEnd} />
    </View>
  );
}

const st = StyleSheet.create({
  hdr: { height: 56, flexDirection: 'row', alignItems: 'center', gap: 4, paddingLeft: 6, paddingRight: 12, backgroundColor: appColor.bg },
  x: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  cnt: { flex: 1, ...ft(18), fontWeight: '700', color: appColor.ink },
  all: { padding: 8 },
  allT: { ...ft(14), fontWeight: '700', color: appColor.deepPurple },
  bar: { position: 'absolute', left: 0, right: 0, bottom: 0, flexDirection: 'row', backgroundColor: appColor.surface, borderTopWidth: 1, borderTopColor: appColor.line, zIndex: 22 },
  sb: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 3 },
  sbT: { ...ft(11.5), textAlign: 'center' },
  web: { flexDirection: 'row', alignItems: 'center', gap: 4, minHeight: 56, borderRadius: 18, backgroundColor: webColor.ink, paddingLeft: 20, paddingRight: 8, shadowColor: '#111111', shadowOpacity: 0.45, shadowRadius: 24, shadowOffset: { width: 0, height: 16 }, elevation: 10 },
  webN: { ...fpx(15, 23), fontWeight: '700', color: '#FFFFFF' },
  webAll: { marginLeft: 8 },
  webDiv: { marginHorizontal: 4, height: 20, width: 1, backgroundColor: 'rgba(255,255,255,0.2)' },
  wb: { minHeight: 40, flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 10, paddingHorizontal: 12 },
  wbT: { ...fpx(14, 21), fontWeight: '700', color: '#FFFFFF' },
});
