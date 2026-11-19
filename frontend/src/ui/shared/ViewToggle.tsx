import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path, Rect } from 'react-native-svg';
import { AppIcon } from '@/ui/icons/Icon';
import { appColor, webColor } from '@/ui/theme';

export type BoardView = 'grid' | 'list';

/**
 * 앱 2열/목록 전환 (원본 memo.html .vt: 74×36 · 안쪽 3 · 라운드 11 · #F2F2F5 · 흰 손잡이 34×30 라운드 8 · 그림자 0 1px 3px .1
 * 고른 아이콘 #16171A · 아닌 아이콘 #9A9EA7). 누르는 영역은 위아래로 넓힘 (원본 11.17 검수: hitSlop 44 안팎)
 */
export function AppViewToggle({ value, onChange }: { value: BoardView; onChange: (v: BoardView) => void }) {
  return (
    <View style={st.app}>
      <View style={[st.knob, { left: value === 'grid' ? 3 : 37 }]} />
      {(['grid', 'list'] as const).map((v) => (
        <Pressable key={v} onPress={() => onChange(v)} hitSlop={{ top: 7, bottom: 7 }} accessibilityRole="button" accessibilityLabel={v === 'grid' ? '2열 보기' : '목록 보기'} accessibilityState={{ selected: value === v }} style={st.appBtn}>
          <AppIcon name={v === 'grid' ? 'viewGrid' : 'viewList'} size={16} color={value === v ? appColor.ink : appColor.ink3} />
        </Pressable>
      ))}
    </View>
  );
}

/**
 * 웹 격자/목록 전환 (원본 memox.tsx: 흰 바탕 · 안쪽 4 · 라운드 10 · 안쪽 테두리 1 #E5E7EB · 버튼 32 라운드 8
 * 고르면 #15171A 바탕 흰 아이콘 · 아니면 #8B95A1, hover #F5F6F8)
 */
export function WebViewToggle({ value, onChange }: { value: BoardView; onChange: (v: BoardView) => void }) {
  return (
    <View style={st.web}>
      {(['grid', 'list'] as const).map((v) => {
        const on = value === v;
        return (
          <Pressable key={v} onPress={() => onChange(v)} accessibilityRole="button" accessibilityLabel={v === 'grid' ? '격자로 보기' : '목록으로 보기'} accessibilityState={{ selected: on }} style={({ hovered }: { pressed: boolean; hovered?: boolean }) => [st.webBtn, { backgroundColor: on ? webColor.ink : hovered ? webColor.row : 'transparent' }]}>
            <Svg width={16} height={16} viewBox="0 0 16 16" fill="none">
              {v === 'grid' ? (
                <>
                  <Rect x={2} y={2} width={5} height={5} rx={1.2} stroke={on ? '#FFFFFF' : webColor.sub2} strokeWidth={1.6} />
                  <Rect x={9} y={2} width={5} height={5} rx={1.2} stroke={on ? '#FFFFFF' : webColor.sub2} strokeWidth={1.6} />
                  <Rect x={2} y={9} width={5} height={5} rx={1.2} stroke={on ? '#FFFFFF' : webColor.sub2} strokeWidth={1.6} />
                  <Rect x={9} y={9} width={5} height={5} rx={1.2} stroke={on ? '#FFFFFF' : webColor.sub2} strokeWidth={1.6} />
                </>
              ) : (
                <Path d="M2.5 4h11M2.5 8h11M2.5 12h11" stroke={on ? '#FFFFFF' : webColor.sub2} strokeWidth={1.6} strokeLinecap="round" />
              )}
            </Svg>
          </Pressable>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  app: { width: 74, height: 36, padding: 3, borderRadius: 11, backgroundColor: appColor.sf, flexDirection: 'row' },
  knob: { position: 'absolute', top: 3, bottom: 3, width: 34, borderRadius: 8, backgroundColor: appColor.surface, shadowColor: '#000000', shadowOpacity: 0.1, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  appBtn: { width: 34, height: 30, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  web: { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 10, backgroundColor: webColor.surface, padding: 4, borderWidth: 1, borderColor: webColor.line },
  webBtn: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
});
