import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import type { Memo, MemoVersion } from '@/types/models';
import { NudgeArrow, NudgeCross, NudgeSpark, WebChev14, WebKindIcon, WebRevIcon, WebSparkle14, WebThreadArrow } from '@/ui/icons/MemoGlyphs';
import { Collapse } from '@/ui/motion/Collapse';
import { mmdd } from '@/ui/shared/memoFormat';
import { fpx } from '@/ui/theme';
import type { AiTrackItem, MemoFeedItem } from '../MemoDetail.types';
import { buildTimeline } from '../memoTimeline';
import { INK } from './parts';
import { usePaper } from '@/ui/shared/Dark';
import { useCoachRef } from '@/ui/shared/Coach';
import { useNudge } from '@/store/nudge';

type Hover = { pressed: boolean; hovered?: boolean };
/* 원본 KIND: 바탕 · 왼쪽 막대 */
const KIND = { 뉴스: { bg: '#E3EDFF', bar: '#3D73F0' }, 주가: { bg: '#FFF1D6', bar: '#C98A0B' }, 공시: { bg: '#EEE8FF', bar: '#7046F5' } } as const;
/* 원본 웹 날짜 'M월 D일' */
const md = (iso: string) => {
  const m = iso.match(/-(\d\d)-(\d\d)T/);
  return m ? `${Number(m[1])}월 ${Number(m[2])}일` : '';
};

/**
 * 웹 AI 업데이트 (원본 board.tsx Feed): 처음 생각 → 그 뒤 도착한 소식 · '도착한 소식 N 최신순' · (소식 없음 안내)
 * 기록 줄 (AI 연결 시작 점 · 메모 고침/첫 메모 펼치면 그때 메모) · 소식 카드 (종류 바탕 · 왼쪽 막대 3 · 자세히)
 * 넛지 (소식 2개 이상) · 'AI가 요약했어요' · 투자 권유 아님 안내. AI 연결이 꺼져 있으면 첫 메모 줄만.
 */
export function WebFeed({ memo, versions, feed, trackItems, onOpenSource, onOpenEvidence, onNudge }: { memo: Memo; versions: MemoVersion[]; feed: MemoFeedItem[]; trackItems: AiTrackItem[]; onOpenSource?: (f: MemoFeedItem) => void; onOpenEvidence?: (f: MemoFeedItem) => void; onNudge?: () => void }) {
  const paper = usePaper();
  const feedRef = useCoachRef('feed');
  const [open, setOpen] = useState<Set<string>>(new Set());
  /* 넛지 닫은 상태는 한 곳(store/nudge)에 — 다시 들어와도 안 뜸 · 사용법 안내 중엔 숨김 */
  const nudgeS = useNudge('memo');
  const nudge = nudgeS.show;
  const setNudge = (v: boolean) => {
    if (!v) nudgeS.hide();
  };
  const rows = buildTimeline(memo, versions, feed).filter((r) => memo.ai_linked || (r.t === 'rev' && r.first));
  const n = memo.ai_linked ? feed.length : 0;
  const first = versions[versions.length - 1];
  const tog = (k: string) =>
    setOpen((s) => {
      const t = new Set(s);
      if (t.has(k)) t.delete(k);
      else t.add(k);
      return t;
    });
  return (
    /* 사용법 안내 ③ 대상 '내 생각 아래 소식이 쌓여요' (앱 MemoFeed 'feed' 와 같은 자리: 처음 생각 → 소식 목록) */
    <View ref={feedRef} collapsable={false} style={st.wrap}>
      {memo.ai_linked ? (
        <View style={st.thread}>
          <View style={[st.sq, { backgroundColor: paper[memo.color].bg }]} />
          <View style={st.flex}>
            <Text style={st.c13}>처음 생각 · {first ? mmdd(first.saved_at) : mmdd(memo.created_at)}</Text>
            <Text style={st.b15} numberOfLines={1}>
              {first?.title ?? memo.title}
            </Text>
          </View>
          <WebThreadArrow />
          <View style={st.endCol}>
            <Text style={st.c13}>그 뒤 도착한 소식</Text>
            <Text style={st.b15}>{n}건</Text>
          </View>
        </View>
      ) : null}
      <View style={st.head}>
        <Text style={st.headT}>도착한 소식</Text>
        <Text style={[st.headT, { width: 12 }]}>{n}</Text>
        <Text style={st.headR}>최신순</Text>
      </View>
      {memo.ai_linked && n === 0 ? (
        <View style={st.empty}>
          <Text style={st.emptyT}>아직 도착한 소식이 없어요</Text>
          <Text style={st.emptyP}>추적 중인 항목과 관련된 공시·뉴스·종가 변화가 생기면 여기에 모아 드려요.</Text>
          {trackItems.length ? (
            <View style={st.chips}>
              {trackItems.map((t, i) => (
                <View key={i} style={st.chip}>
                  <Text style={st.chipT}>{t.label}</Text>
                </View>
              ))}
            </View>
          ) : null}
        </View>
      ) : null}
      <View style={st.list}>
        {rows.map((r) => {
          if (r.t === 'ai')
            return (
              <View key="ai" style={st.start}>
                <View style={st.dot} />
                <Text style={st.startT}>{mmdd(r.at)} · AI 연결 시작</Text>
              </View>
            );
          if (r.t === 'rev') {
            const key = `v${r.v.version}`;
            const o = open.has(key);
            return (
              <View key={key}>
                <Pressable onPress={() => tog(key)} accessibilityRole="button" accessibilityState={{ expanded: o }} style={({ hovered }: Hover) => [st.rev, hovered && { backgroundColor: '#F9F9F9' }]}>
                  <View style={st.revIc}>
                    <WebRevIcon first={r.first} />
                  </View>
                  <Text style={st.revT}>
                    {mmdd(r.v.saved_at)} · {r.first ? '첫 메모를 남겼어요' : '메모를 수정했어요'}
                  </Text>
                  <WebChev14 up={o} />
                </Pressable>
                <Collapse open={o}>
                  <View style={st.oldWrap}>
                    <View style={[st.old, { backgroundColor: paper[memo.color].bg }]}>
                      <Text style={st.oldW}>
                        버전 {r.v.version} · {mmdd(r.v.saved_at)} 저장
                      </Text>
                      <Text style={st.oldT}>{r.v.title}</Text>
                      {r.v.body ? <Text style={st.oldB}>{r.v.body}</Text> : null}
                    </View>
                  </View>
                </Collapse>
              </View>
            );
          }
          const f = r.item;
          const K = KIND[f.kind];
          const o = open.has(f.id);
          const ver = versions.find((v) => v.version === f.memo_version);
          return (
            <View key={f.id} style={[st.card, { backgroundColor: K.bg }]}>
              <Pressable onPress={() => tog(f.id)} accessibilityRole="button" accessibilityState={{ expanded: o }} style={st.cardBtn}>
                <View style={st.cardIc}>
                  <WebKindIcon kind={f.kind} />
                </View>
                <View style={st.flex}>
                  <Text style={st.c13b}>
                    {f.kind} · {md(f.at)}
                  </Text>
                  <Text style={st.cardT}>{f.headline}</Text>
                </View>
                <View style={st.more}>
                  <Text style={st.moreT}>{o ? '접기' : '자세히'}</Text>
                  <WebChev14 up={o} />
                </View>
              </Pressable>
              <Collapse open={o}>
                <View style={st.cardBody}>
                  <Text style={st.sum}>{f.summary}</Text>
                  <View style={[st.lm, { backgroundColor: paper[memo.color].bg }]}>
                    <Text style={st.lmL}>연결된 내 메모{ver ? ` · 버전 ${ver.version}` : ''}</Text>
                    <Text style={st.lmT} numberOfLines={1}>
                      {ver?.title ?? memo.title}
                    </Text>
                  </View>
                  <View style={st.src}>
                    <Text style={st.srcT}>{f.source}</Text>
                    {/* ④-2: 앱과 같은 근거 상세로 (원본 웹에는 근거 화면이 없음) */}
                    {onOpenEvidence ? (
                      <Pressable onPress={() => onOpenEvidence(f)} accessibilityRole="button">
                        <Text style={st.srcA}>근거 자세히 보기 ›</Text>
                      </Pressable>
                    ) : null}
                    {f.kind !== '주가' ? (
                      <Pressable onPress={() => onOpenSource?.(f)} accessibilityRole="link">
                        <Text style={st.srcA}>원문 열기 ↗</Text>
                      </Pressable>
                    ) : null}
                  </View>
                </View>
              </Collapse>
              <View style={[st.bar, { backgroundColor: K.bar }]} />
            </View>
          );
        })}
      </View>
      {memo.ai_linked && n >= 2 && nudge && onNudge ? (
        <View style={st.nudge}>
          <Pressable onPress={() => { setNudge(false); onNudge(); }} accessibilityRole="button" style={st.nGo}>
            <NudgeSpark />
            <Text style={st.nGoT} numberOfLines={1}>
              이 메모에 붙은 소식, 한 번에 정리해 드릴까요?
            </Text>
            <NudgeArrow />
          </Pressable>
          <View style={st.nSep} />
          <Pressable onPress={() => setNudge(false)} accessibilityRole="button" accessibilityLabel="제안 닫기" style={({ hovered }: Hover) => [st.nX, hovered && { backgroundColor: 'rgba(255,255,255,0.1)' }]}>
            <NudgeCross />
          </Pressable>
        </View>
      ) : null}
      {memo.ai_linked ? (
        <>
          <View style={st.fn}>
            <WebSparkle14 />
            <Text style={st.fnT}>뉴스·공시는 AI가 요약했어요. 자세히에서 출처를 볼 수 있어요.</Text>
          </View>
          <Text style={st.disc}>투자 권유가 아닌 참고 정보예요 · AI는 틀릴 수 있어 원문을 꼭 확인해 주세요</Text>
        </>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { gap: 16 },
  flex: { flex: 1, minWidth: 0 },
  thread: { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 14, backgroundColor: '#F7F8FA', paddingHorizontal: 16, paddingVertical: 12 },
  sq: { width: 36, height: 36, borderTopLeftRadius: 9, borderTopRightRadius: 9, borderBottomLeftRadius: 9 },
  endCol: { alignItems: 'flex-end' },
  c13: { ...fpx(13, 20), fontWeight: '500', color: '#747D8D' },
  b15: { ...fpx(15, 23), fontWeight: '700', color: INK },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headT: { ...fpx(17, 26), fontWeight: '700', color: INK },
  headR: { flex: 1, textAlign: 'right', ...fpx(13, 20), fontWeight: '500', color: '#575B63' },
  empty: { alignItems: 'center', gap: 8, borderRadius: 16, backgroundColor: '#F7F8FA', padding: 24 },
  emptyT: { ...fpx(17, 26), fontWeight: '700', color: INK },
  emptyP: { ...fpx(14, 21), color: '#747D8D', textAlign: 'center' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 6, marginTop: 4 },
  chip: { borderRadius: 999, backgroundColor: '#FFFFFF', paddingHorizontal: 12, paddingVertical: 4, borderWidth: 1, borderColor: '#E5E7EB' },
  chipT: { ...fpx(13, 20), fontWeight: '700', color: '#333D4B' },
  list: { gap: 8 },
  start: { flexDirection: 'row', alignItems: 'center', gap: 32, paddingLeft: 24, paddingVertical: 4 },
  dot: { width: 4, height: 4, borderRadius: 2, backgroundColor: '#747D8D' },
  startT: { ...fpx(13, 20), fontWeight: '500', color: '#575B63' },
  rev: { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 12, paddingHorizontal: 16, paddingVertical: 12 },
  revIc: { width: 32, height: 22, borderRadius: 8, backgroundColor: '#F2F3F4', alignItems: 'center', justifyContent: 'center' },
  revT: { flex: 1, ...fpx(14, 21), color: '#575B63' },
  oldWrap: { paddingLeft: 60, paddingRight: 16, paddingBottom: 12 },
  old: { gap: 4, borderRadius: 12, paddingHorizontal: 16, paddingVertical: 12 },
  oldW: { ...fpx(13, 20), fontWeight: '500', color: '#575B63' },
  oldT: { ...fpx(14, 21), color: INK },
  oldB: { ...fpx(14, 21), color: '#575B63' },
  card: { borderRadius: 16, overflow: 'hidden' },
  cardBtn: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16 },
  cardIc: { width: 32, height: 32, borderRadius: 10, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  c13b: { ...fpx(13, 20), fontWeight: '500', color: '#575B63' },
  cardT: { ...fpx(17, 26), fontWeight: '700', color: INK, marginTop: 4 },
  more: { width: 64, flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: 4 },
  moreT: { ...fpx(13, 20), fontWeight: '500', color: '#575B63' },
  cardBody: { gap: 12, paddingBottom: 20, paddingLeft: 60, paddingRight: 20 },
  sum: { ...fpx(14, 21), color: '#575B63' },
  lm: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10 },
  lmL: { ...fpx(13, 20), fontWeight: '700', color: '#575B63' },
  lmT: { flex: 1, ...fpx(13, 20), fontWeight: '500', color: INK },
  src: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: 12, borderTopWidth: 1, borderTopColor: '#E8ECF3', paddingTop: 12 },
  srcT: { flex: 1, ...fpx(13, 20), fontWeight: '500', color: '#575B63' },
  srcA: { ...fpx(13, 20), fontWeight: '700', color: INK, textDecorationLine: 'underline' },
  bar: { position: 'absolute', left: 0, top: 18, width: 3, height: 40, borderRadius: 1.5 },
  nudge: { flexDirection: 'row', alignItems: 'center', height: 48, borderRadius: 14, backgroundColor: INK },
  nGo: { flex: 1, minWidth: 0, height: 48, flexDirection: 'row', alignItems: 'center', gap: 8, paddingLeft: 16, paddingRight: 12 },
  nGoT: { flex: 1, minWidth: 0, ...fpx(15, 23), fontWeight: '700', color: '#FFFFFF' },
  nSep: { width: 1, height: 20, backgroundColor: 'rgba(255,255,255,0.2)' },
  nX: { width: 44, height: 48, alignItems: 'center', justifyContent: 'center', borderTopRightRadius: 14, borderBottomRightRadius: 14 },
  fn: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  fnT: { flex: 1, ...fpx(13, 20), fontWeight: '500', color: '#575B63' },
  disc: { ...fpx(13, 20), color: '#9A9EA7' },
});
