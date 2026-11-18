/**
 * 모바일 상단 바 하나로 모든 화면 머리줄을 처리.
 *  - left 'logo'  : 홈 (memo's 로고 자리)
 *  - left 'title' : 탭 첫 화면 (내 종목 · 최신 업데이트 · 투자 기록 · 스튜디오), 제목 21px
 *  - left 'back'  : 안쪽 화면 (꺾쇠 ‹ + 제목 · 뒤로 가기 아이콘은 꺾쇠로 통일)
 *  - left 'cancel': 새 메모 · 새 체크리스트 (취소 · 가운데 제목 · 오른쪽 완료)
 * 오른쪽 버튼은 actions 배열 순서대로. 누르는 영역은 44 이상.
 * 움직임: 스크롤하면 아래 선이 나타남(lineOpacity · #332 useLargeTitle 과 짝) · 알림 점은 새로 생길 때 톡.
 */
import type { ReactNode } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import { PopWhen } from '@/components/motion/Appear';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MobileIcon, type MobileIconName } from '@/components/icons/MobileIcons';

const C = {
  bg: '#FFFFFF',
  text: '#16171A',
  sub: '#575B63',
  accent: '#6A42AB',
  accentSoft: '#EEE9FB',
  badge: '#E5484D',
  disabled: '#C9CDD4',
  pillLine: '#DADDE2',
  onAccent: '#FFFFFF',
  line: '#EEF0F3',
} as const;
const BAR_H = 56;
const PAD = 16;

export type TopBarAction =
  | { kind: 'icon'; icon: Extract<MobileIconName, 'search' | 'bell' | 'more' | 'more_h' | 'check_all'>; label: string; onPress: () => void; dot?: boolean; disabled?: boolean }
  | { kind: 'profile'; initial: string; onPress: () => void }
  | { kind: 'text'; label: string; onPress: () => void; emphasis?: boolean; disabled?: boolean }
  | { kind: 'pill'; label: string; onPress: () => void; on?: boolean };

export interface TopBarProps {
  left: 'logo' | 'title' | 'back' | 'cancel';
  /** title·back·cancel 에서 보이는 글자 (cancel 이면 가운데 정렬) */
  title?: string;
  onBack?: () => void;
  onCancel?: () => void;
  /** 로고 자리에 넣을 요소 (우리 쪽 로고 이미지). 없으면 글자 로고 */
  logo?: ReactNode;
  actions?: TopBarAction[];
  /** 기기 위쪽 안전 영역을 더할지 (화면 맨 위에 둘 때 true) */
  safeTop?: boolean;
  /** 스크롤에 따라 아래 선이 나타나는 정도 (useLargeTitle().barLineOpacity) */
  lineOpacity?: Animated.AnimatedInterpolation<number>;
  /** 스크롤에 따라 제목이 나타나는 정도 (useLargeTitle().barTitleOpacity · 화면 안에 큰 제목이 있을 때) */
  titleOpacity?: Animated.AnimatedInterpolation<number>;
}

export function TopBar({ left, title, onBack, onCancel, logo, actions = [], safeTop = true, lineOpacity, titleOpacity }: TopBarProps) {
  const insets = useSafeAreaInsets();
  const centered = left === 'cancel';
  return (
    <View style={[st.bar, { paddingTop: safeTop ? insets.top : 0, height: BAR_H + (safeTop ? insets.top : 0) }]}>
      <View style={st.row}>
        {left === 'logo' && (logo ?? <Text style={st.logoText}>{"memo's"}</Text>)}
        {left === 'title' && <Animated.Text style={[st.title, titleOpacity !== undefined && { opacity: titleOpacity }]} numberOfLines={1}>{title}</Animated.Text>}
        {left === 'back' && (
          <Pressable style={st.backBtn} onPress={onBack} hitSlop={8} accessibilityRole="button" accessibilityLabel="뒤로">
            <MobileIcon name="back" size={22} color={C.text} strokeWidth={2.2} />
            {!!title && <Text style={st.backTitle} numberOfLines={1}>{title}</Text>}
          </Pressable>
        )}
        {left === 'cancel' && (
          <Pressable style={st.textBtn} onPress={onCancel} accessibilityRole="button">
            <Text style={st.cancel}>취소</Text>
          </Pressable>
        )}
        {centered && <Text style={st.centerTitle} numberOfLines={1}>{title}</Text>}
        <View style={st.spacer} />
        {actions.map((a, i) => <Action key={i} a={a} />)}
      </View>
      {lineOpacity !== undefined && <Animated.View pointerEvents="none" style={[st.line, { opacity: lineOpacity }]} />}
    </View>
  );
}

function Action({ a }: { a: TopBarAction }) {
  if (a.kind === 'icon') {
    return (
      <Pressable style={st.iconBtn} onPress={a.onPress} disabled={a.disabled} accessibilityRole="button" accessibilityLabel={a.label}>
        <MobileIcon name={a.icon} size={22} color={a.disabled ? C.disabled : C.text} />
        <PopWhen show={!!a.dot} style={st.dot} />
      </Pressable>
    );
  }
  if (a.kind === 'profile') {
    return (
      <Pressable style={st.iconBtn} onPress={a.onPress} accessibilityRole="button" accessibilityLabel="MY">
        <View style={st.avatar}><Text style={st.avatarText}>{a.initial}</Text></View>
      </Pressable>
    );
  }
  if (a.kind === 'pill') {
    return (
      <Pressable style={st.pillWrap} onPress={a.onPress} accessibilityRole="button">
        <View style={[st.pill, a.on && st.pillOn]}><Text style={[st.pillText, a.on && st.pillTextOn]}>{a.label}</Text></View>
      </Pressable>
    );
  }
  return (
    <Pressable style={st.textBtn} onPress={a.onPress} disabled={a.disabled} accessibilityRole="button">
      <Text style={[st.textAct, a.emphasis && st.textActStrong, a.disabled && { color: C.disabled }]}>{a.label}</Text>
    </Pressable>
  );
}

const st = StyleSheet.create({
  bar: { backgroundColor: C.bg },
  row: { flex: 1, flexDirection: 'row', alignItems: 'center', paddingLeft: PAD, paddingRight: PAD - 10 },
  logoText: { fontSize: 22, fontWeight: '900', color: C.text, letterSpacing: -0.5 },
  title: { fontSize: 21, fontWeight: '800', color: C.text, flexShrink: 1 },
  backBtn: { flexDirection: 'row', alignItems: 'center', minHeight: 44, marginLeft: -10, paddingHorizontal: 10, gap: 6, flexShrink: 1 },
  backTitle: { fontSize: 18, fontWeight: '700', color: C.text, flexShrink: 1 },
  centerTitle: { position: 'absolute', left: 72, right: 72, textAlign: 'center', fontSize: 16, fontWeight: '700', color: C.text },
  cancel: { fontSize: 16, color: C.text },
  spacer: { flex: 1 },
  line: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 1, backgroundColor: C.line },
  iconBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  dot: { position: 'absolute', top: 10, right: 11, width: 7, height: 7, borderRadius: 4, backgroundColor: C.badge },
  avatar: { width: 32, height: 32, borderRadius: 16, backgroundColor: C.accentSoft, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 14, fontWeight: '700', color: C.accent },
  textBtn: { minHeight: 44, minWidth: 44, paddingHorizontal: 10, alignItems: 'center', justifyContent: 'center' },
  textAct: { fontSize: 16, color: C.sub, fontWeight: '600' },
  textActStrong: { color: C.accent, fontWeight: '800' },
  pillWrap: { minHeight: 44, justifyContent: 'center', paddingHorizontal: 4 },
  pill: { height: 32, paddingHorizontal: 12, borderRadius: 16, borderWidth: 1, borderColor: C.pillLine, justifyContent: 'center' },
  pillOn: { backgroundColor: C.accent, borderColor: C.accent },
  pillText: { fontSize: 13, fontWeight: '700', color: C.sub },
  pillTextOn: { color: C.onAccent },
});
