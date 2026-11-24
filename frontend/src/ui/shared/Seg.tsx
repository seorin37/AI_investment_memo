import React, { useState } from 'react';
import { Pressable, StyleSheet, View, type LayoutRectangle } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { SlidingPill } from '@/ui/motion/SlidingPill';
import { appColor, ft, shadow, tw } from '@/ui/theme';
import { CountBadge } from './CountBadge';

export interface SegOption<K extends string> {
  key: K;
  label: string;
  /** 오른쪽 빨간 숫자 (원본 메모 상세 'AI 업데이트 2') */
  count?: number;
}

export interface SegProps<K extends string> {
  value: K;
  options: SegOption<K>[];
  onChange: (k: K) => void;
  /**
   * appBoard: 앱 메모 보드 [메모 보드 | 기업정보] (.seg: 48 · 안쪽 4 · 라운드 14 · 칸 라운드 11 · 14.5px 600)
   * appDetail: 앱 메모 상세 [메모 | AI 업데이트] (.ptabs: 48 · 라운드 15 · 흰 알약 라운드 12 · 15px 800)
   * web: 웹 kit.tsx Seg (zinc-100 · 안쪽 3 · 라운드 11 · 알약 라운드 9 · 36/28)
   */
  variant: 'appBoard' | 'appDetail' | 'web';
  /** web 만: md 36 · sm 28 */
  size?: 'md' | 'sm';
}

/** 칸을 나눠 고르는 탭 (흰 알약) */
export function Seg<K extends string>({ value, options, onChange, variant, size = 'md' }: SegProps<K>) {
  const [lay, setLay] = useState<Record<string, LayoutRectangle>>({});
  const cur = lay[value];
  const pillStyle = variant === 'appDetail' ? st.pillDetail : variant === 'web' ? st.pillWeb : null;
  return (
    <View style={variant === 'appBoard' ? st.board : variant === 'appDetail' ? st.detail : st.web} accessibilityRole="tablist">
      {pillStyle ? <SlidingPill target={cur ? { x: cur.x, width: cur.width } : null} style={pillStyle} /> : null}
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
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            style={[variant === 'appBoard' ? [st.boardBtn, on && st.boardOn] : variant === 'appDetail' ? st.detailBtn : [st.webBtn, { height: size === 'sm' ? 28 : 36 }]]}
          >
            <Text
              numberOfLines={1}
              style={
                variant === 'appBoard'
                  ? [st.boardT, { fontWeight: on ? '600' : '400', color: on ? appColor.ink : appColor.ink2 }]
                  : variant === 'appDetail'
                    ? [st.detailT, { fontWeight: on ? '800' : '400', color: on ? appColor.ink : appColor.ink2 }]
                    : [size === 'sm' ? ft(13, 1.5) : ft(14, 1.5), { fontWeight: on ? '700' : '400', color: on ? tw.zinc950 : tw.zinc500 }]
              }
            >
              {o.label}
            </Text>
            {o.count ? <CountBadge count={o.count} borderColor="transparent" style={st.count} /> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  board: { flexDirection: 'row', padding: 4, borderRadius: 14, backgroundColor: appColor.sf },
  boardBtn: { flex: 1, height: 40, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  /* 원본 0 1px 3px rgba(0,0,0,.07) */
  boardOn: { backgroundColor: appColor.surface, shadowColor: '#000000', shadowOpacity: 0.07, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  boardT: { ...ft(14.5) },
  detail: { flexDirection: 'row', padding: 4, borderRadius: 15, backgroundColor: appColor.sf },
  pillDetail: { top: 4, bottom: 4, borderRadius: 12, backgroundColor: appColor.surface, ...shadow.pill },
  detailBtn: { flex: 1, height: 40, flexDirection: 'row', gap: 6, alignItems: 'center', justifyContent: 'center' },
  detailT: { ...ft(15) },
  count: { borderWidth: 0, height: 19, minWidth: 19, borderRadius: 9, paddingHorizontal: 5 },
  web: { flexDirection: 'row', padding: 3, borderRadius: 11, backgroundColor: tw.zinc100 },
  pillWeb: { top: 3, bottom: 3, borderRadius: 9, backgroundColor: '#FFFFFF', ...shadow.seg },
  webBtn: { flex: 1, paddingHorizontal: 12, alignItems: 'center', justifyContent: 'center' },
});
