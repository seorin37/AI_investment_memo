/**
 * 담기 버튼 (Lucian #051 product-add-to-cart) — 주간보고서 「메모에 추가」 · 종목 추가.
 * 누르면 버튼이 .9배로 눌렸다 spring 으로 돌아오고, 글이 위로 빠지며 "✓ 추가됨"이 아래에서 올라옴 (.35s).
 * 체크는 .6배 → 1배로 톡. 한 번 추가되면 다시 누를 수 없음(added).
 */
import { useEffect, useRef } from 'react';
import { Animated, Pressable, StyleSheet, Text, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { EASE, ND, SPRING, tween, useValue } from '@/components/motion/motion';

export interface AddButtonProps {
  added: boolean;
  onPress: () => void;
  label: string;
  addedLabel?: string;
  style?: StyleProp<ViewStyle>;
  addedStyle?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
  addedTextStyle?: StyleProp<TextStyle>;
  addedColor: string;
}

export function AddButton({ added, onPress, label, addedLabel = '추가됨', style, addedStyle, textStyle, addedTextStyle, addedColor }: AddButtonProps) {
  const t = useValue(added ? 1 : 0);
  const press = useValue(1);
  const was = useRef(added);
  useEffect(() => {
    if (was.current === added) return;
    was.current = added;
    Animated.parallel([
      tween(t, added ? 1 : 0, 350, EASE, ND),
      Animated.sequence([tween(press, 0.9, 100, EASE, ND), tween(press, 1, 450, SPRING, ND)]),
    ]).start();
  }, [added, t, press]);
  return (
    <Pressable onPress={onPress} disabled={added} accessibilityRole="button" accessibilityState={{ disabled: added }} accessibilityLabel={added ? addedLabel : label}>
      <Animated.View style={[st.btn, style, added && addedStyle, { transform: [{ scale: press }] }]}>
        <Animated.View style={[st.layer, { opacity: t.interpolate({ inputRange: [0, 0.5], outputRange: [1, 0], extrapolate: 'clamp' }), transform: [{ translateY: t.interpolate({ inputRange: [0, 1], outputRange: [0, -14] }) }] }]}>
          <Text style={textStyle} numberOfLines={1}>{label}</Text>
        </Animated.View>
        <Animated.View style={[st.layer, st.row, { opacity: t.interpolate({ inputRange: [0.4, 1], outputRange: [0, 1], extrapolate: 'clamp' }), transform: [{ translateY: t.interpolate({ inputRange: [0, 1], outputRange: [14, 0] }) }] }]}>
          <Animated.View style={{ transform: [{ scale: t.interpolate({ inputRange: [0, 0.6, 1], outputRange: [0.6, 0.6, 1] }) }] }}>
            <MobileIcon name="check" size={14} color={addedColor} strokeWidth={2.6} />
          </Animated.View>
          <Text style={addedTextStyle} numberOfLines={1}>{addedLabel}</Text>
        </Animated.View>
        <Text style={[textStyle, st.ghost]} numberOfLines={1}>{label.length > addedLabel.length + 2 ? label : `✓ ${addedLabel}`}</Text>
      </Animated.View>
    </Pressable>
  );
}

const st = StyleSheet.create({
  btn: { overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  layer: { position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, alignItems: 'center', justifyContent: 'center' },
  row: { flexDirection: 'row', gap: 4 },
  /** 폭을 잡아 주는 보이지 않는 글 */
  ghost: { opacity: 0 },
});
