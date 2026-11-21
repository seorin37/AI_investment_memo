import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import type { MemoColor } from '@/types/models';
import { SelIcon } from '@/ui/icons/BoardGlyphs';
import { ClockIcon } from '@/ui/icons/MemoGlyphs';
import { Sheet } from '@/ui/shared/Sheet';
import { appColor, ft } from '@/ui/theme';
import { usePaper } from '@/ui/shared/Dark';

/* 원본 C 순서: 노랑 · 초록 · 파랑 · 보라 · 분홍 */
const COLORS: MemoColor[] = ['yellow', 'green', 'blue', 'purple', 'pink'];
export type MoreAction = 'hist' | 'copy' | 'pin' | 'ai' | 'del';

/**
 * 앱 메모 ⋯ 시트 (원본 memo.html #sheet: 제목 16.5px 800 · '아래로 끌어 내리면 닫혀요' 12.5px #9A9EA7
 * 색 줄 (좌우 22 · 위 16 · 아래 10 · 사이 16 · 동그라미 34 · 고른 색은 흰 2 + 색 2 고리) · 구분선 (좌우 22 · 위아래 4)
 * 줄 52 (좌우 22 · 사이 14 · 15.5px): 수정 이력 보기 · 내용 복사 · 고정 · AI 연결 · 휴지통으로 이동(빨강))
 */
export function MemoMoreSheet({ open, title, color, pinned, aiLinked, onColor, onAction, onClose }: { open: boolean; title: string; color: MemoColor; pinned: boolean; aiLinked: boolean; onColor: (c: MemoColor) => void; onAction: (a: MoreAction) => void; onClose: () => void }) {
  const paper = usePaper();
  const rows: { a: MoreAction; label: string; icon: React.ReactNode; danger?: boolean }[] = [
    { a: 'hist', label: '수정 이력 보기 (AI 업데이트 탭)', icon: <ClockIcon color={appColor.ink} /> },
    { a: 'copy', label: '내용 복사', icon: <SelIcon k="copy" size={20} color={appColor.ink} /> },
    { a: 'pin', label: pinned ? '고정 해제' : '고정', icon: <SelIcon k="pin" size={20} color={appColor.ink} /> },
    { a: 'ai', label: aiLinked ? 'AI 연결 끄기' : 'AI 연결 켜기', icon: <SelIcon k="ai" size={20} color={appColor.ink} /> },
    { a: 'del', label: '휴지통으로 이동', icon: <SelIcon k="del" size={20} color={appColor.red} />, danger: true },
  ];
  return (
    <Sheet open={open} onClose={onClose} label="메모 메뉴">
      <View style={st.head}>
        <Text style={st.sht} numberOfLines={1}>
          {title}
        </Text>
        <Text style={st.shs}>아래로 끌어 내리면 닫혀요</Text>
      </View>
      <View style={st.colors}>
        {COLORS.map((c) => (
          <Pressable key={c} onPress={() => onColor(c)} accessibilityRole="button" accessibilityLabel={paper[c].label} accessibilityState={{ selected: c === color }} style={[st.ring, c === color && { borderColor: paper[c].accent }]}>
            <View style={[st.dot, { backgroundColor: paper[c].bg }]} />
          </Pressable>
        ))}
      </View>
      <View style={st.sdiv} />
      {rows.map((r) => (
        <Pressable key={r.a} onPress={() => onAction(r.a)} accessibilityRole="button" style={({ pressed }) => [st.srow, pressed && { backgroundColor: '#F4F4F6' }]}>
          {r.icon}
          <Text style={[st.srowT, r.danger && { color: appColor.red }]}>{r.label}</Text>
        </Pressable>
      ))}
    </Sheet>
  );
}

const st = StyleSheet.create({
  head: { paddingHorizontal: 22, marginTop: -4 },
  sht: { ...ft(16.5), fontWeight: '800', color: appColor.ink },
  shs: { ...ft(12.5), color: appColor.ink3, marginTop: 2 },
  colors: { flexDirection: 'row', gap: 8, paddingTop: 12, paddingHorizontal: 18, paddingBottom: 6 },
  /* 고리 42 = 동그라미 34 + 흰 2 + 색 2 */
  ring: { width: 42, height: 42, borderRadius: 21, borderWidth: 2, borderColor: 'transparent', alignItems: 'center', justifyContent: 'center' },
  dot: { width: 34, height: 34, borderRadius: 17, borderWidth: 1, borderColor: 'rgba(0,0,0,0.07)' },
  sdiv: { height: 1, backgroundColor: appColor.line, marginVertical: 4, marginHorizontal: 22 },
  srow: { minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 22, paddingVertical: 14 },
  srowT: { ...ft(15.5), color: appColor.ink },
});
