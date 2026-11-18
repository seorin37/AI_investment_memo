/**
 * 공통 UI 부품 — 시안의 버튼·칩·토글·체크박스·입력창을 한곳에 정의.
 */
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  type PressableProps,
  type PressableStateCallbackType,
  StyleSheet,
  TextInput,
  type TextInputProps,
  View,
  type ViewProps,
  type ViewStyle,
  type StyleProp,
} from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { Icon, type IconName } from '@/components/icons/Icon';
import { colors, fonts, radius, shadow } from '@/theme/tokens';
import { T } from './Text';

type PressState = PressableStateCallbackType & { hovered?: boolean };

/** hover 상태를 받을 수 있는 Pressable (웹에서 마우스 오버 표현) */
export function Hoverable({
  style,
  hoverStyle,
  pressedStyle,
  children,
  ...rest
}: Omit<PressableProps, 'style'> & {
  style?: StyleProp<ViewStyle>;
  hoverStyle?: StyleProp<ViewStyle>;
  pressedStyle?: StyleProp<ViewStyle>;
}) {
  return (
    <Pressable
      {...rest}
      style={(s) => {
        const st = s as PressState;
        return [style, st.hovered && hoverStyle, st.pressed && (pressedStyle ?? { opacity: 0.85 })];
      }}
    >
      {children}
    </Pressable>
  );
}

// ─── 버튼 ────────────────────────────────────────────────────
type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'blue' | 'danger' | 'dangerOutline';
type ButtonSize = 'sm' | 'md' | 'lg';

const btnTone: Record<ButtonVariant, { bg: string; fg: string; border?: string; hover: string }> = {
  primary: { bg: colors.black, fg: '#FFFFFF', hover: '#2A2C31' },
  secondary: { bg: colors.surfaceWarm, fg: colors.text, hover: '#ECE9E3' },
  outline: { bg: colors.surface, fg: colors.text, border: colors.border, hover: '#F7F8FA' },
  ghost: { bg: 'transparent', fg: colors.textSub, hover: '#F3F4F6' },
  blue: { bg: colors.blue, fg: '#FFFFFF', hover: '#3A6BEB' },
  danger: { bg: colors.danger, fg: '#FFFFFF', hover: '#D13C41' },
  dangerOutline: { bg: colors.surface, fg: colors.danger, border: '#F5C2C7', hover: '#FFF5F5' },
};

const btnSize: Record<ButtonSize, { h: number; px: number; fs: number; r: number }> = {
  sm: { h: 32, px: 12, fs: 13, r: 8 },
  md: { h: 44, px: 18, fs: 15, r: 12 },
  lg: { h: 48, px: 22, fs: 16, r: 12 },
};

export function Button({
  label,
  onPress,
  variant = 'primary',
  size = 'md',
  icon,
  disabled,
  loading,
  fullWidth,
  style,
}: {
  label: string;
  onPress?: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: IconName;
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const tone = btnTone[variant];
  const sz = btnSize[size];
  return (
    <Hoverable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={disabled || loading ? undefined : onPress}
      style={[
        {
          height: sz.h,
          paddingHorizontal: sz.px,
          borderRadius: sz.r,
          backgroundColor: tone.bg,
          borderWidth: tone.border ? 1 : 0,
          borderColor: tone.border,
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 6,
          opacity: disabled ? 0.4 : 1,
        },
        fullWidth && { alignSelf: 'stretch' },
        style,
      ]}
      hoverStyle={!disabled && { backgroundColor: tone.hover }}
    >
      {loading ? <ActivityIndicator size="small" color={tone.fg} /> : icon ? <Icon name={icon} size={sz.fs + 2} color={tone.fg} /> : null}
      <T size={sz.fs} weight="semibold" color={tone.fg} lh={1.2}>
        {label}
      </T>
    </Hoverable>
  );
}

export function IconButton({
  name,
  onPress,
  size = 20,
  color = colors.textSub,
  box = 32,
  label,
  style,
}: {
  name: IconName;
  onPress?: () => void;
  size?: number;
  color?: string;
  box?: number;
  label: string;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <Hoverable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      hitSlop={6}
      style={[{ width: box, height: box, borderRadius: box / 4, alignItems: 'center', justifyContent: 'center' }, style]}
      hoverStyle={{ backgroundColor: '#F1F2F4' }}
    >
      <Icon name={name} size={size} color={color} />
    </Hoverable>
  );
}

// ─── 탭 칩 (검정 알약) ───────────────────────────────────────
export function PillTabs<K extends string>({
  items,
  value,
  onChange,
  size = 'md',
}: {
  items: { key: K; label: string }[];
  value: K;
  onChange: (k: K) => void;
  size?: 'sm' | 'md';
}) {
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
      {items.map((it) => {
        const active = it.key === value;
        return (
          <Hoverable
            key={it.key}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            aria-selected={active}
            onPress={() => onChange(it.key)}
            style={{
              height: size === 'sm' ? 30 : 32,
              paddingHorizontal: size === 'sm' ? 14 : 16,
              borderRadius: radius.pill,
              backgroundColor: active ? colors.black : colors.surfaceMuted,
              alignItems: 'center',
              justifyContent: 'center',
            }}
            hoverStyle={!active && { backgroundColor: '#EFF0F2' }}
          >
            <T size={13} weight={active ? 'semibold' : 'regular'} color={active ? '#FFFFFF' : colors.textSub} lh={1.2}>
              {it.label}
            </T>
          </Hoverable>
        );
      })}
    </View>
  );
}

/** 회색 트랙 위 흰색 선택 세그먼트 (메모 팝업 · 피드백 · 설정) */
export function Segmented<K extends string>({
  items,
  value,
  onChange,
  tone = 'warm',
  height = 48,
  fontSize = 15,
}: {
  items: { key: K; label: string }[];
  value: K;
  onChange: (k: K) => void;
  tone?: 'warm' | 'cool';
  height?: number;
  fontSize?: number;
}) {
  return (
    <View
      style={{
        flexDirection: 'row',
        backgroundColor: tone === 'warm' ? colors.surfaceWarm : '#F1F3F6',
        borderRadius: 14,
        padding: 4,
        height,
      }}
    >
      {items.map((it) => {
        const active = it.key === value;
        return (
          <Pressable
            key={it.key}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            aria-selected={active}
            onPress={() => onChange(it.key)}
            style={[
              { flex: 1, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
              active && { backgroundColor: colors.surface, ...shadow.card },
            ]}
          >
            <T size={fontSize} weight={active ? 'semibold' : 'medium'} color={active ? colors.text : colors.textWarm} lh={1.2}>
              {it.label}
            </T>
          </Pressable>
        );
      })}
    </View>
  );
}

/** 작은 세그먼트 (설정 · 접근 권한/민감도) */
export function MiniSegmented<K extends string>({ items, value, onChange }: { items: { key: K; label: string }[]; value: K; onChange: (k: K) => void }) {
  return (
    <View style={{ flexDirection: 'row', backgroundColor: '#F3F4F6', borderRadius: 10, padding: 3 }}>
      {items.map((it) => {
        const active = it.key === value;
        return (
          <Pressable
            key={it.key}
            onPress={() => onChange(it.key)}
            style={[{ paddingHorizontal: 12, height: 30, borderRadius: 8, justifyContent: 'center' }, active && { backgroundColor: '#FFF', ...shadow.card }]}
          >
            <T size={12} weight={active ? 'semibold' : 'regular'} color={active ? colors.text : colors.textSub} lh={1.2}>
              {it.label}
            </T>
          </Pressable>
        );
      })}
    </View>
  );
}

// ─── 토글 ────────────────────────────────────────────────────
/** AI 연결 토글: ON = 청록 + 체크, OFF = 회색 + × (시안 그대로) */
export function AiToggle({ value, onChange, size = 'md', disabled }: { value: boolean; onChange?: (v: boolean) => void; size?: 'sm' | 'md'; disabled?: boolean }) {
  const w = size === 'sm' ? 34 : 36;
  const h = size === 'sm' ? 20 : 20;
  const knob = h - 4;
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityState={{ checked: value, disabled }}
      aria-checked={value}
      accessibilityLabel="AI 연결"
      hitSlop={8}
      onPress={(e) => {
        e.stopPropagation?.();
        if (!disabled) onChange?.(!value);
      }}
      style={{
        width: w,
        height: h,
        borderRadius: h / 2,
        backgroundColor: value ? colors.teal : '#F1F1F1',
        borderWidth: value ? 0 : 1,
        borderColor: '#DADADA',
        justifyContent: 'center',
        paddingHorizontal: 2,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <View
        style={{
          width: knob,
          height: knob,
          borderRadius: knob / 2,
          backgroundColor: '#FFF',
          alignSelf: value ? 'flex-end' : 'flex-start',
          alignItems: 'center',
          justifyContent: 'center',
          ...shadow.card,
        }}
      >
        <Icon name={value ? 'check' : 'x'} size={9} color={value ? colors.teal : '#9A9A9A'} strokeWidth={3} />
      </View>
    </Pressable>
  );
}

/** 일반 스위치 (설정 화면 — 보라 / 위젯 — 파랑) */
export function Switch({ value, onChange, tone = 'purple' }: { value: boolean; onChange: (v: boolean) => void; tone?: 'purple' | 'blue' }) {
  const on = tone === 'purple' ? '#7C5CD6' : colors.blue;
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityState={{ checked: value }}
      aria-checked={value}
      hitSlop={8}
      onPress={(e) => {
        e.stopPropagation?.();
        onChange(!value);
      }}
      style={{ width: 40, height: 24, borderRadius: 12, backgroundColor: value ? on : '#E2E4E8', padding: 3, justifyContent: 'center' }}
    >
      <View style={{ width: 18, height: 18, borderRadius: 9, backgroundColor: '#FFF', alignSelf: value ? 'flex-end' : 'flex-start', ...shadow.card }} />
    </Pressable>
  );
}

// ─── 체크박스 ────────────────────────────────────────────────
/** 원형 체크 (보드 체크리스트 · 투자 기록) */
export function CircleCheck({ checked, onPress, size = 20, tone = 'purple' }: { checked: boolean; onPress?: () => void; size?: number; tone?: 'purple' | 'gray' }) {
  const fill = tone === 'purple' ? '#8B6CDB' : colors.textSub;
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      aria-checked={checked}
      hitSlop={8}
      onPress={onPress}
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        borderWidth: checked ? 0 : 1.5,
        borderColor: '#C9CDD4',
        backgroundColor: checked ? fill : 'transparent',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {checked && <Icon name="check" size={size * 0.62} color="#FFF" strokeWidth={3} />}
    </Pressable>
  );
}

/** 사각 체크 (위젯 '확인할 것' · 설정) */
export function SquareCheck({ checked, onPress, tone = 'blue', size = 18 }: { checked: boolean; onPress?: () => void; tone?: 'blue' | 'purple'; size?: number }) {
  const fill = tone === 'blue' ? colors.blue : '#7C5CD6';
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      aria-checked={checked}
      hitSlop={8}
      onPress={onPress}
      style={{
        width: size,
        height: size,
        borderRadius: 4,
        borderWidth: checked ? 0 : 1.5,
        borderColor: '#D3D7DE',
        backgroundColor: checked ? fill : '#FFF',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {checked && <Icon name="check" size={size * 0.7} color="#FFF" strokeWidth={3} />}
    </Pressable>
  );
}

export function LabeledCheck({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <Pressable onPress={() => onChange(!checked)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      <SquareCheck checked={checked} onPress={() => onChange(!checked)} tone="purple" />
      <T size={14} color={colors.textBody}>
        {label}
      </T>
    </Pressable>
  );
}

// ─── 진행 링 (1/4) ───────────────────────────────────────────
export function ProgressRing({ done, total, size = 32, color = '#8B6CDB', dashed }: { done: number; total: number; size?: number; color?: string; dashed?: boolean }) {
  const stroke = 2.5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const ratio = total === 0 ? 0 : done / total;
  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size} style={{ position: 'absolute', transform: [{ rotate: '-90deg' }] }}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke="#E8EAEE" strokeWidth={stroke} fill="none" strokeDasharray={dashed ? '3 3' : undefined} />
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeDasharray={`${c * ratio} ${c}`} strokeLinecap="round" />
      </Svg>
      <T size={size <= 28 ? 9 : 10} weight="medium" color={colors.textSub} lh={1}>
        {done}/{total}
      </T>
    </View>
  );
}

// ─── 배지 · 카드 · 구분선 ────────────────────────────────────
export function Badge({ label, bg = '#EEF0F3', fg = colors.textBody, size = 12 }: { label: string; bg?: string; fg?: string; size?: number }) {
  return (
    <View style={{ backgroundColor: bg, borderRadius: 4, paddingHorizontal: 6, height: size + 8, justifyContent: 'center' }}>
      <T size={size} weight="medium" color={fg} lh={1.2}>
        {label}
      </T>
    </View>
  );
}

export function CountBadge({ count, tone = 'red' }: { count: number; tone?: 'red' | 'soft' }) {
  if (count <= 0) return null;
  const solid = tone === 'red';
  return (
    <View
      style={{
        minWidth: 24,
        height: 24,
        paddingHorizontal: 6,
        borderRadius: 12,
        backgroundColor: solid ? '#E5484D' : '#FDECEC',
        borderWidth: solid ? 2 : 0,
        borderColor: '#F5C2C7',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <T size={12} weight="semibold" color={solid ? '#FFF' : '#E5484D'} lh={1}>
        {count}
      </T>
    </View>
  );
}

export function Card({ style, children, ...rest }: ViewProps) {
  return (
    <View {...rest} style={[styles.card, style]}>
      {children}
    </View>
  );
}

export function Divider({ style }: { style?: StyleProp<ViewStyle> }) {
  return <View style={[{ height: 1, backgroundColor: colors.borderSoft }, style]} />;
}

// ─── 입력창 ──────────────────────────────────────────────────
export function TextField({
  style,
  inputStyle,
  icon,
  right,
  ...rest
}: TextInputProps & { style?: StyleProp<ViewStyle>; inputStyle?: TextInputProps['style']; icon?: IconName; right?: React.ReactNode }) {
  const [focused, setFocused] = useState(false);
  return (
    <View
      style={[
        {
          flexDirection: 'row',
          alignItems: 'center',
          height: 44,
          borderRadius: 10,
          borderWidth: 1,
          borderColor: focused ? '#9AA3B2' : colors.border,
          backgroundColor: colors.surface,
          paddingHorizontal: 14,
          gap: 8,
        },
        style,
      ]}
    >
      {icon && <Icon name={icon} size={16} color={colors.textMuted} />}
      <TextInput
        placeholderTextColor={colors.placeholder}
        {...rest}
        onFocus={(e) => {
          setFocused(true);
          rest.onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          rest.onBlur?.(e);
        }}
        style={[styles.input, inputStyle]}
      />
      {right}
    </View>
  );
}

export function TextArea({ style, minHeight = 120, ...rest }: TextInputProps & { minHeight?: number }) {
  return (
    <TextInput
      multiline
      textAlignVertical="top"
      placeholderTextColor={colors.placeholder}
      {...rest}
      style={[
        styles.input,
        {
          minHeight,
          borderRadius: 12,
          backgroundColor: colors.surfaceWarm,
          padding: 16,
          lineHeight: 22,
        },
        style,
      ]}
    />
  );
}

// ─── 드롭다운 ────────────────────────────────────────────────
export function Select<K extends string>({
  value,
  options,
  onChange,
  width,
  placeholder = '선택',
}: {
  value: K | null;
  options: { key: K; label: string; disabled?: boolean }[];
  onChange: (k: K) => void;
  width?: number;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const current = options.find((o) => o.key === value);
  return (
    <View style={{ width, zIndex: open ? 50 : 1 }}>
      <Hoverable
        onPress={() => setOpen((o) => !o)}
        style={{
          height: 38,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: colors.border,
          backgroundColor: colors.surface,
          paddingHorizontal: 12,
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
        hoverStyle={{ borderColor: '#C9CED6' }}
      >
        <T size={14} color={current ? colors.text : colors.placeholder} numberOfLines={1} style={{ flexShrink: 1 }}>
          {current?.label ?? placeholder}
        </T>
        <Icon name={open ? 'chevronUp' : 'chevronDown'} size={14} color={colors.textSub} />
      </Hoverable>
      {open && (
        <View style={[styles.menu, { top: 42 }]}>
          {options.map((o) => (
            <Hoverable
              key={o.key}
              disabled={o.disabled}
              onPress={() => {
                onChange(o.key);
                setOpen(false);
              }}
              style={{ paddingHorizontal: 12, height: 36, justifyContent: 'center', borderRadius: 6, opacity: o.disabled ? 0.4 : 1 }}
              hoverStyle={{ backgroundColor: '#F4F5F7' }}
            >
              <T size={14} weight={o.key === value ? 'semibold' : 'regular'} numberOfLines={1}>
                {o.label}
              </T>
            </Hoverable>
          ))}
        </View>
      )}
    </View>
  );
}

// ─── 기타 ────────────────────────────────────────────────────
export function Avatar({ name, size = 40, url }: { name: string; size?: number; url?: string | null }) {
  const initial = name.trim().charAt(0) || '?';
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: '#F1ECFB',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
      }}
    >
      {url ? null : (
        <T size={size * 0.38} weight="semibold" color={colors.brand} lh={1}>
          {initial}
        </T>
      )}
    </View>
  );
}

export function Loading({ height = 120 }: { height?: number }) {
  return (
    <View style={{ height, alignItems: 'center', justifyContent: 'center' }}>
      <ActivityIndicator color={colors.textMuted} />
    </View>
  );
}

export function EmptyState({ title, desc, action }: { title: string; desc?: string; action?: React.ReactNode }) {
  return (
    <View style={{ alignItems: 'center', justifyContent: 'center', paddingVertical: 32, gap: 6 }}>
      <T size={15} weight="semibold" color={colors.textBody}>
        {title}
      </T>
      {desc ? (
        <T size={13} color={colors.textSub} align="center">
          {desc}
        </T>
      ) : null}
      {action}
    </View>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <View style={{ alignItems: 'center', paddingVertical: 24, gap: 10 }}>
      <T size={14} color={colors.textSub} align="center">
        {message}
      </T>
      {onRetry && <Button label="다시 시도" size="sm" variant="outline" onPress={onRetry} />}
    </View>
  );
}

export function InfoNote({ title, desc, icon = 'info' }: { title: string; desc: string; icon?: IconName }) {
  return (
    <View style={{ flexDirection: 'row', gap: 12, backgroundColor: colors.surfaceWarm, borderRadius: 14, padding: 16, alignItems: 'center' }}>
      <Icon name={icon} size={20} color={colors.textWarm} strokeWidth={1.4} />
      <View style={{ flex: 1, gap: 2 }}>
        <T size={14} weight="medium">
          {title}
        </T>
        <T size={12} color={colors.textWarm}>
          {desc}
        </T>
      </View>
    </View>
  );
}

/** 물음표 원형 버튼 (지표 설명) */
export function QuestionDot({ onPress, active }: { onPress?: () => void; active?: boolean }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="설명 보기"
      hitSlop={8}
      onPress={onPress}
      style={{
        width: 16,
        height: 16,
        borderRadius: 8,
        backgroundColor: active ? '#FFFFFF' : '#EEF1F6',
        borderWidth: active ? 1.2 : 0,
        borderColor: active ? colors.danger : 'transparent',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <T size={10} weight="semibold" color={active ? colors.danger : '#7A8594'} lh={1}>
        ?
      </T>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
  },
  input: {
    flex: 1,
    minWidth: 0,
    fontFamily: fonts.regular,
    fontSize: 15,
    color: colors.text,
    paddingVertical: 0,
    ...(Platform.OS === 'web' ? ({ outlineStyle: 'none' } as object) : {}),
  },
  menu: {
    position: 'absolute',
    left: 0,
    right: 0,
    backgroundColor: colors.surface,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 4,
    zIndex: 100,
    ...shadow.pop,
  },
});
