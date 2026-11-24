import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text, TextInput } from '@/components/ui/AppText';
import { Sheet } from '@/ui/shared/Sheet';
import type { FeedbackDraft } from '../My.types';
import type { Hover } from './parts';

/**
 * 웹 피드백 보내기 / 오류 신고 = 원본 overlays.tsx Feedback (680 · 라운드 28 · 테두리 #E8ECF3 · 안쪽 32/31)
 * 제목 26 · 설명 14 · 큰 따옴표 장식 · 탭(일반 피드백 | 오류 신고) · 별 32(hover·선택 #15171A) · 내용 156 / 오류: 위치 · 유형 칩 · 상세 120 · [취소] [보내기]
 * 보내기는 연결 안 됨 → onSend 에서 안내만 (메일·외부 전송 없음)
 */
const STAR = 'M16 3L20 11.4L29 12.6L22.4 18.8L24 27.8L16 23.4L8 27.8L9.6 18.8L3 12.6L12 11.4L16 3Z';
const KIND_W: Record<string, number> = { '기능 작동 오류': 148, '화면·표시 오류': 148, '데이터·연결 오류': 148, '속도·접속 문제': 140, 기타: 72 };

export function WebFeedback({ open, kinds, onClose, onSend }: { open: boolean; kinds: string[]; onClose: () => void; onSend: (d: FeedbackDraft) => void }) {
  const [tab, setTab] = useState<'general' | 'bug'>('general');
  const [star, setStar] = useState(0);
  const [hov, setHov] = useState(0);
  const [txt, setTxt] = useState('');
  const [where, setWhere] = useState('');
  const [picked, setPicked] = useState<string[]>([]);
  const [detail, setDetail] = useState('');
  const [prev, setPrev] = useState(open);
  if (open !== prev) {
    setPrev(open);
    if (open) { setTab('general'); setStar(0); setHov(0); setTxt(''); setWhere(''); setPicked([]); setDetail(''); }
  }
  const g = tab === 'general';
  return (
    <Sheet open={open} onClose={onClose} width={680} label="피드백 보내기">
      <View style={[st.box, { gap: g ? 24 : 16 }]}>
        <View style={{ gap: 8 }}>
          <Text style={st.title}>{g ? '피드백 보내기' : '오류 신고'}</Text>
          <Text style={st.desc}>{g ? 'MEMO’S(메모스)를 사용하며 느낀 점을 알려주세요.\n소중한 의견을 모아 더 좋은 서비스를 만들겠습니다.' : '서비스 이용 중 발생한 문제를 알려주세요.\n남겨주신 내용을 확인하고 개선하겠습니다.'}</Text>
        </View>
        <Text style={st.quote} accessibilityElementsHidden importantForAccessibility="no">“</Text>
        <View style={st.tabs}>
          {([['general', '일반 피드백'], ['bug', '오류 신고']] as const).map(([k, l]) => (
            <Pressable key={k} onPress={() => setTab(k)} accessibilityRole="tab" accessibilityState={{ selected: tab === k }} style={[st.tab, tab === k && st.tabOn]}>
              <Text style={[st.tabT, tab === k && { color: '#15171A' }]}>{l}</Text>
            </Pressable>
          ))}
        </View>
        {g ? (
          <>
            <View style={{ alignItems: 'center', gap: 8 }}>
              <Text style={st.l}>얼마나 만족하셨나요?</Text>
              <View style={st.starsBox}>
                <View style={st.stars}>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <Pressable key={n} onPress={() => setStar(n)} onHoverIn={() => setHov(n)} onHoverOut={() => setHov(0)} accessibilityRole="button" accessibilityLabel={`${n}점`} style={({ pressed }) => [st.star, pressed && { transform: [{ scale: 0.92 }] }]}>
                      <Svg width={32} height={32} viewBox="0 0 32 32" fill="none"><Path d={STAR} fill={(hov || star) >= n ? '#15171A' : '#E8ECF3'} /></Svg>
                    </Pressable>
                  ))}
                </View>
                <Text style={st.hint}>별점을 선택해 주세요</Text>
              </View>
            </View>
            <View style={{ gap: 8 }}>
              <Text style={st.l}>피드백 내용</Text>
              <TextInput value={txt} onChangeText={(v) => setTxt(v.slice(0, 500))} placeholder={'좋았던 점이나 개선이 필요한 점을\n자유롭게 작성해 주세요.'} placeholderTextColor="#747D8D" multiline textAlignVertical="top" accessibilityLabel="피드백 내용" style={[st.area, { height: 156 }]} />
              <Note n={txt.length} />
            </View>
          </>
        ) : (
          <>
            <View style={{ gap: 8 }}>
              <Text style={st.l}>문제가 발생한 화면·기능 (선택)</Text>
              <TextInput value={where} onChangeText={setWhere} placeholder="예: 로그인, 투자 기록, 최신 업데이트" placeholderTextColor="#747D8D" accessibilityLabel="문제가 발생한 화면·기능" style={st.input} />
              <Text style={st.note}>문제가 발생한 위치를 알면 더 빠르게 확인할 수 있어요.</Text>
            </View>
            <View style={{ gap: 8 }}>
              <Text style={st.l}>신고 유형 · 복수 선택 가능</Text>
              {[kinds.slice(0, 2), kinds.slice(2)].map((row, ri) => (
                <View key={ri} style={{ flexDirection: 'row', gap: 8 }}>
                  {row.map((k) => {
                    const on = picked.includes(k);
                    return (
                      <Pressable key={k} onPress={() => setPicked((a) => (on ? a.filter((x) => x !== k) : [...a, k]))} accessibilityRole="button" accessibilityState={{ selected: on }} style={({ hovered }: Hover) => [st.kind, { width: KIND_W[k] ?? 148 }, on ? st.kindOn : hovered && { backgroundColor: '#FAFBFC' }]}>
                        <Text style={[st.kindT, on && { color: '#FFFFFF' }]}>{k}</Text>
                      </Pressable>
                    );
                  })}
                </View>
              ))}
            </View>
            <View style={{ gap: 8 }}>
              <Text style={st.l}>상세 내용</Text>
              <TextInput value={detail} onChangeText={(v) => setDetail(v.slice(0, 500))} placeholder={'어떤 작업 중에 문제가 발생했나요?\n발생 상황과 기대했던 동작을 알려주세요.'} placeholderTextColor="#747D8D" multiline textAlignVertical="top" accessibilityLabel="상세 내용" style={[st.area, { height: 120 }]} />
              <Note n={detail.length} />
            </View>
          </>
        )}
        <View style={st.btns}>
          <Pressable onPress={onClose} accessibilityRole="button" style={[st.btn, { width: 104, backgroundColor: '#F2F3F4' }]}><Text style={st.btnT}>취소</Text></Pressable>
          <Pressable onPress={() => onSend({ mode: tab, star, text: txt, where, kinds: picked, detail })} accessibilityRole="button" style={[st.btn, { width: 136, backgroundColor: '#14171C' }]}><Text style={[st.btnT, { color: '#FFFFFF' }]}>보내기</Text></Pressable>
        </View>
      </View>
    </Sheet>
  );
}

function Note({ n }: { n: number }) {
  return <View style={st.noteRow}><Text style={st.note}>개인정보는 입력하지 말아 주세요.</Text><Text style={st.note}>{n} / 500</Text></View>;
}

const st = StyleSheet.create({
  box: { width: 680, maxWidth: '100%', overflow: 'hidden', borderRadius: 28, borderWidth: 1, borderColor: '#E8ECF3', backgroundColor: '#FFFFFF', paddingHorizontal: 32, paddingVertical: 31 },
  title: { fontSize: 26, lineHeight: 35, fontWeight: '700', color: '#15171A' },
  desc: { width: 616, maxWidth: '100%', fontSize: 14, lineHeight: 21, color: '#747D8D' },
  quote: { position: 'absolute', left: 574, top: -2, fontSize: 112, lineHeight: 112, fontWeight: '700', color: '#15171A', opacity: 0.18 },
  tabs: { height: 48, flexDirection: 'row', gap: 4, borderRadius: 12, backgroundColor: '#F2F3F4', padding: 4 },
  tab: { flex: 1, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  tabOn: { backgroundColor: '#FFFFFF' },
  tabT: { fontSize: 15, lineHeight: 23, fontWeight: '500', color: '#747D8D' },
  l: { fontSize: 15, lineHeight: 23, fontWeight: '500', color: '#15171A' },
  starsBox: { height: 78, alignItems: 'center', justifyContent: 'center', gap: 8 },
  stars: { flexDirection: 'row', gap: 8 },
  star: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  hint: { fontSize: 14, lineHeight: 21, color: '#747D8D' },
  area: { borderRadius: 12, borderWidth: 1, borderColor: '#E8ECF3', backgroundColor: '#FAFBFC', padding: 16, fontSize: 14, lineHeight: 21, color: '#15171A' },
  input: { height: 44, borderRadius: 12, borderWidth: 1, borderColor: '#E8ECF3', backgroundColor: '#FAFBFC', paddingHorizontal: 16, fontSize: 14, lineHeight: 21, color: '#15171A' },
  noteRow: { flexDirection: 'row', justifyContent: 'space-between' },
  note: { fontSize: 13, lineHeight: 20, fontWeight: '500', color: '#747D8D' },
  kind: { height: 36, borderRadius: 999, borderWidth: 1, borderColor: '#E8ECF3', backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12 },
  kindOn: { borderColor: '#15171A', backgroundColor: '#15171A' },
  kindT: { fontSize: 14, lineHeight: 21, color: '#15171A' },
  btns: { height: 48, flexDirection: 'row', justifyContent: 'flex-end', gap: 8 },
  btn: { height: 48, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  btnT: { fontSize: 15, lineHeight: 23, fontWeight: '500', color: '#15171A' },
});
