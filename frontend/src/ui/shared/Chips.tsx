import React, { useState } from 'react';
import { Pressable, StyleSheet, View, type LayoutRectangle } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { SlidingPill } from '@/ui/motion/SlidingPill';
import { appColor, ft, fpx, webColor } from '@/ui/theme';

export interface ChipOption<K extends string> {
  key: K;
  label: string;
  /** 글자 뒤 숫자 (원본: 'AI 연결 3') */
  count?: number;
  /** 앞 빨간 점 (원본 '새 소식') */
  dot?: boolean;
}

/**
 * 앱 거르기 칩 줄 (원본 memo.html .frow .chip: 32 · 좌우 12 · 라운드 16 · 테두리 #E6E8EC · 13px
 * 고르면 바탕·테두리 #8569E3 + 흰 글자 700. 칩 사이 6, 새 소식 점 6×6 #E5484D)
 */
export function AppChips<K extends string>({ value, options, onChange }: { value: K; options: ChipOption<K>[]; onChange: (k: K) => void }) {
  return (
    <View style={st.appRow}>
      {options.map((o) => {
        const on = o.key === value;
        return (
          <Pressable key={o.key} onPress={() => onChange(o.key)} accessibilityRole="button" accessibilityState={{ selected: on }} style={[st.appChip, on && st.appOn]}>
            {o.dot ? <View style={[st.appDot, on && { backgroundColor: '#FFFFFF' }]} /> : null}
            <Text style={[st.appT, on && st.appTOn]} numberOfLines={1}>
              {o.label}
              {o.count != null ? ` ${o.count}` : ''}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/**
 * 웹 거르기 칩 (원본 memox.tsx BoardHead: 36 · 좌우 14 · 14px bold · 검정 #111 알약이 미끄러짐 .45s spring
 * 안 고른 칩 #8B95A1, 새 소식 점 6 #E5484D(고르면 흰색), '전체' 외에는 숫자)
 */
export function WebChips<K extends string>({ value, options, onChange }: { value: K; options: ChipOption<K>[]; onChange: (k: K) => void }) {
  const [lay, setLay] = useState<Record<string, LayoutRectangle>>({});
  const cur = lay[value];
  return (
    <View style={st.webRow}>
      <SlidingPill target={cur ? { x: cur.x, width: cur.width } : null} style={st.webPill} />
      {options.map((o) => {
        const on = o.key === value;
        return (
          <Pressable
            key={o.key}
            onPress={() => onChange(o.key)}
            onLayout={(e) => {
              const l = e.nativeEvent.layout;
              setLay((m) => ({ ...m, [o.key]: l }));
            }}
            accessibilityRole="button"
            accessibilityState={{ selected: on }}
            style={st.webChip}
          >
            {({ hovered }: { pressed: boolean; hovered?: boolean }) => (
              <>
                {o.dot ? <View style={[st.appDot, on && { backgroundColor: '#FFFFFF' }]} /> : null}
                <Text style={[st.webT, { color: on ? '#FFFFFF' : hovered ? webColor.strong : webColor.sub2 }]} numberOfLines={1}>
                  {o.label}
                  {o.count != null ? ` ${o.count}` : ''}
                </Text>
              </>
            )}
          </Pressable>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  appRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  appChip: { minHeight: 32, paddingVertical: 6, paddingHorizontal: 12, borderRadius: 16, borderWidth: 1, borderColor: appColor.line, backgroundColor: appColor.surface, flexDirection: 'row', alignItems: 'center', gap: 4 },
  appOn: { backgroundColor: appColor.accent, borderColor: appColor.accent },
  appDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: appColor.red },
  appT: { ...ft(13), color: appColor.ink2, fontWeight: '400', flexShrink: 1 },
  appTOn: { color: '#FFFFFF', fontWeight: '700' },
  webRow: { position: 'relative', flexDirection: 'row', alignItems: 'center', gap: 4 },
  webPill: { top: 0, bottom: 0, borderRadius: 999, backgroundColor: '#111111' },
  webChip: { minHeight: 36, paddingVertical: 7, paddingHorizontal: 14, borderRadius: 999, flexDirection: 'row', alignItems: 'center', gap: 4 },
  webT: { ...fpx(14, 21), fontWeight: '700' },
});
