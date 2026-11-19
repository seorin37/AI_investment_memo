import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import type { Memo, MemoVersion } from '@/types/models';
import { ChevDown16 } from '@/ui/icons/MemoGlyphs';
import { Collapse } from '@/ui/motion/Collapse';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { mmdd } from '@/ui/shared/memoFormat';
import { appColor, ft } from '@/ui/theme';
import { diffParts, revSummary } from './memoTimeline';

/**
 * 수정 이력 (원본 memo.html 10 openHist: '수정 이력' 26px 800 · '제목 · N개 버전' 13px
 * 버전 카드 (테두리 #E7E8EC · 라운드 16 · 펼치면 #C6B6F5 / #FBF9FF): 점 9 (현재 #8569E3) · 'MM.DD 수정 · 현재' 15.5px + '버전 N' 칩 · 바뀐 내용 12.5px
 * 펼치면 그 버전 글 (14.5px 줄 1.75 · 더한 글 초록 · 지운 글 빨강 줄) · 아래 안내 12.5px). 근거 상세의 메모 카드에서 열면 그 버전이 펼쳐짐.
 */
export function HistoryContent({ memo, versions, openVersion }: { memo: Memo; versions: MemoVersion[]; openVersion?: number }) {
  const [open, setOpen] = useState<Set<number>>(new Set());
  /* 원본: 화면이 밀려 들어온 뒤(.38s) 펼침 */
  useEffect(() => {
    if (openVersion == null) return;
    const t = setTimeout(() => setOpen((s) => new Set(s).add(openVersion)), 380);
    return () => clearTimeout(t);
  }, [openVersion]);
  const tog = (v: number) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(v)) n.delete(v);
      else n.add(v);
      return n;
    });
  const last = versions.length - 1;
  return (
    <View>
      <Text style={st.hh1}>수정 이력</Text>
      <Text style={st.hsub}>
        {memo.title} · {versions.length}개 버전
      </Text>
      {versions.map((v, i) => {
        const prev = versions[i + 1];
        const o = open.has(v.version);
        const cur = i === 0;
        return (
          <View key={v.version} style={[st.vc, o && st.vcOpen]}>
            <Pressable onPress={() => tog(v.version)} accessibilityRole="button" accessibilityState={{ expanded: o }} style={st.vh}>
              <View style={[st.dot, cur && { backgroundColor: appColor.accent }]} />
              <View style={st.flex}>
                <View style={st.bRow}>
                  <Text style={st.b}>
                    {mmdd(v.saved_at)} {i === last ? '첫 메모' : '수정'}
                    {cur ? ' · 현재' : ''}
                  </Text>
                  <View style={st.vtag}>
                    <Text style={st.vtagT}>버전 {v.version}</Text>
                  </View>
                </View>
                <Text style={st.small}>{revSummary(v, prev)}</Text>
              </View>
              <Turn on={o}>
                <ChevDown16 />
              </Turn>
            </Pressable>
            <Collapse open={o} duration={420}>
              <View style={st.vbody}>
                <Text style={st.vbB}>{v.title}</Text>
                <Text style={st.vbP}>
                  {diffParts(prev?.body, v.body).map((x, j) => (
                    <Text key={j} style={x.k === 'ins' ? st.ins : x.k === 'del' ? st.del : null}>
                      {x.t}
                    </Text>
                  ))}
                </Text>
              </View>
            </Collapse>
          </View>
        );
      })}
      <Text style={st.vnote}>편집 화면을 나갈 때 한 번씩 저장돼요 · 초록 = 이 버전에서 더한 글</Text>
    </View>
  );
}

function Turn({ on, children }: { on: boolean; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(on ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: on ? 1 : 0, duration: 350 * k, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [on, v, k]);
  return <Animated.View style={{ marginLeft: 'auto', transform: [{ rotate: v.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '180deg'] }) }] }}>{children}</Animated.View>;
}

const st = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  hh1: { ...ft(26), fontWeight: '800', color: appColor.ink, marginTop: 4, marginHorizontal: 2, marginBottom: 4 },
  hsub: { ...ft(13), color: appColor.ink2, marginHorizontal: 2, marginBottom: 14 },
  vc: { borderWidth: 1, borderColor: '#E7E8EC', borderRadius: 16, marginBottom: 10, backgroundColor: '#FFFFFF' },
  vcOpen: { borderColor: '#C6B6F5', backgroundColor: '#FBF9FF' },
  vh: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingTop: 14, paddingHorizontal: 14, paddingBottom: 12 },
  dot: { width: 9, height: 9, borderRadius: 5, backgroundColor: '#D3D6DC', marginTop: 7 },
  bRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' },
  b: { ...ft(15.5), fontWeight: '700', color: appColor.ink },
  vtag: { backgroundColor: appColor.accentSoft, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1, marginLeft: 6 },
  vtagT: { ...ft(11), fontWeight: '700', color: appColor.deepPurple },
  small: { ...ft(12.5), color: appColor.ink2, marginTop: 2 },
  vbody: { marginHorizontal: 14, marginBottom: 14, paddingTop: 12, borderTopWidth: 1, borderTopColor: '#EDE8FB' },
  vbB: { ...ft(15.5), fontWeight: '700', color: appColor.ink, marginBottom: 4 },
  vbP: { ...ft(14.5, 1.75), color: appColor.ink },
  ins: { backgroundColor: 'rgba(47,174,104,0.22)' },
  del: { color: '#B42318', opacity: 0.75, textDecorationLine: 'line-through' },
  vnote: { textAlign: 'center', ...ft(12.5), color: appColor.ink3, marginTop: 16 },
});
