import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, View } from 'react-native';
import { InlineSpark } from '@/ui/icons/InlineGlyphs';
import { Text } from '@/components/ui/AppText';
import type { Memo, MemoVersion } from '@/types/models';
import { AppPlug } from '@/ui/icons/BoardGlyphs';
import { Chev12, FeedKindIcon, NudgeArrow, NudgeCross, NudgeSpark, RevIcon } from '@/ui/icons/MemoGlyphs';
import { Collapse } from '@/ui/motion/Collapse';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { PaperBox } from '@/ui/shared/PaperBox';
import { mmdd } from '@/ui/shared/memoFormat';
import { Toggle } from '@/ui/shared/Toggle';
import { appColor, ft } from '@/ui/theme';
import type { AiTrackItem, MemoFeedItem } from '../MemoDetail.types';
import { buildTimeline } from '../memoTimeline';
import { usePaper } from '@/ui/shared/Dark';
import { useCoachRef } from '@/ui/shared/Coach';
import { useNudge } from '@/store/nudge';

/* 원본 FK: 소식 종류별 [카드 바탕, 그림 색] */
const FK = { 뉴스: ['#E4ECFF', '#3D73F0'], 공시: ['#EEE8FF', '#7046F5'], 주가: ['#FFF1D6', '#C98A00'] } as const;
/* 원본 추적 항목 칩: 가격 조건 초록 · 공시·뉴스 파랑 */
export const CHIP = { price: { bg: '#E3F5EA', ink: '#1B7A45', label: '가격 조건' }, fact: { bg: '#E4ECFF', ink: '#2F6BDB', label: '공시·뉴스' }, ask: { bg: '#F1EEFB', ink: '#6B4FD8', label: '질문' } } as const;

export interface AppAiTabProps {
  memo: Memo;
  versions: MemoVersion[];
  feed: MemoFeedItem[];
  trackItems: AiTrackItem[];
  lastChecked?: string;
  /** ⋯ → '수정 이력 보기': 가장 최근 메모 기록 줄을 펼침 (바뀔 때마다) */
  openLatestRev: number;
  onToggleAi: () => void;
  /** 크레딧을 다 써서 멈춤(끄기 대기): 스위치를 꺼진 모양으로 (2026-11-24) */
  aiPaused?: boolean;
  onOpenSource?: (f: MemoFeedItem) => void;
  onOpenEvidence?: (f: MemoFeedItem) => void;
  onNudge?: () => void;
}

/**
 * 앱 AI 업데이트 탭 (원본 memo.html renderAI · 11.12 2차): 소식 + 메모 기록을 한 줄 시간순으로.
 * 연결 안 됨: 안내 + AI 연결 스위치 + '메모 기록' / 연결됐고 소식 없음: 지켜보는 중 + 확인 중인 항목 + '기록' / 소식 있음: '도착한 소식 N'.
 * 아래: (소식 2개 이상이면) 주간보고서 넛지 · 출처 안내 · AI 연결 스위치 · 투자 권유 아님 안내.
 */
export function AppAiTab({ memo, versions, feed, trackItems, lastChecked, openLatestRev, aiPaused, onToggleAi, onOpenSource, onOpenEvidence, onNudge }: AppAiTabProps) {
  const rows = buildTimeline(memo, versions, feed);
  const feeds = rows.filter((r) => r.t === 'feed');
  const firstUnread = feeds.find((r) => r.t === 'feed' && r.item.unread);
  const [open, setOpen] = useState<Set<string>>(() => new Set(firstUnread && firstUnread.t === 'feed' ? [firstUnread.item.id] : []));
  /* 넛지 닫은 상태는 한 곳(store/nudge)에 — 다시 들어와도 안 뜸 · 사용법 안내 중엔 숨김 */
  const memoNudge = useNudge('memo');
  const nudge = memoNudge.show;
  const setNudge = (v: boolean) => {
    if (!v) memoNudge.hide();
  };
  /* 사용법 안내 ② AI 연결 칸 (원본 .aic) · ③ 첫 소식 카드 (원본 .uc) */
  const aiRef = useCoachRef('ai');
  const feedRef = useCoachRef('feed');
  const firstFeedId = feeds[0]?.t === 'feed' ? feeds[0].item.id : null;
  /* ⋯ → 수정 이력 보기: 가장 최근 메모 기록 줄 펼침 (원본 showHistInTab) */
  const latestRev = rows.find((r) => r.t === 'rev');
  const latestKey = latestRev && latestRev.t === 'rev' ? `v${latestRev.v.version}` : '';
  /* 0 부터: 탭이 이 신호와 함께 처음 그려져도 펼침 */
  const [seenSignal, setSeenSignal] = useState(0);
  if (openLatestRev !== seenSignal) {
    setSeenSignal(openLatestRev);
    if (latestKey) setOpen((s) => new Set(s).add(latestKey));
  }
  const tog = (k: string) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });
  const verOf = (n: number) => versions.find((v) => v.version === n);
  const sw = (
    <View ref={aiRef} collapsable={false} style={[st.aic, { marginTop: 6 }]}>
      <View style={st.flex}>
        <Text style={st.aicB}>AI 연결</Text>
        <Text style={st.aicS}>{aiPaused ? 'AI 사용량을 다 써서 멈췄어요 · 충전하지 않으면 꺼져요' : memo.ai_linked ? '이 메모를 AI가 지켜보고 있어요' : '켜면 관련 소식을 모아 드려요'}</Text>
      </View>
      <Toggle variant="app" on={memo.ai_linked && !aiPaused} onChange={onToggleAi} label="AI 연결" />
    </View>
  );
  return (
    <View>
      {!memo.ai_linked ? (
        <>
          <Text style={st.off}>{'AI 연결을 켜면 이 메모와 관련된\n공시·뉴스·주가 변화를 여기서 모아 볼 수 있어요.'}</Text>
          {sw}
          <Text style={st.hsec}>메모 기록</Text>
        </>
      ) : feeds.length ? (
        <View style={st.uhd}>
          <Text style={st.uhdT}>도착한 소식 {feeds.length}</Text>
          <Text style={st.uhdS}>최신순 · 메모 기록 함께</Text>
        </View>
      ) : (
        <WatchBlock items={trackItems} since={memo.ai_linked_at ? mmdd(memo.ai_linked_at) : ''} lastChecked={lastChecked} />
      )}
      {rows.map((r) => {
        if (r.t === 'rev') {
          const key = `v${r.v.version}`;
          return <RevRow key={key} v={r.v} first={r.first} color={memo.color} open={open.has(key)} onToggle={() => tog(key)} />;
        }
        if (r.t === 'ai')
          return (
            <View key="ai" style={st.hrw}>
              <View style={[st.mic, { backgroundColor: '#F4F4F6' }]}>
                <AppPlug size={14} />
              </View>
              <Text style={st.hrwT}>{mmdd(r.at)} · AI 연결을 시작했어요</Text>
            </View>
          );
        if (r.item.id === firstFeedId)
          return (
            <View key={r.item.id} ref={feedRef} collapsable={false}>
              <FeedCard f={r.item} ver={verOf(r.item.memo_version)} open={open.has(r.item.id)} onToggle={() => tog(r.item.id)} onOpenSource={onOpenSource} onOpenEvidence={onOpenEvidence} />
            </View>
          );
        return <FeedCard key={r.item.id} f={r.item} ver={verOf(r.item.memo_version)} open={open.has(r.item.id)} onToggle={() => tog(r.item.id)} onOpenSource={onOpenSource} onOpenEvidence={onOpenEvidence} />;
      })}
      {memo.ai_linked && feed.length >= 2 && nudge && onNudge ? (
        <View style={st.nudge}>
          <Pressable onPress={onNudge} accessibilityRole="button" style={st.nGo}>
            <NudgeSpark />
            <Text style={st.nGoT} numberOfLines={2}>
              이 메모에 붙은 소식, 한 번에 정리해 드릴까요?
            </Text>
            <NudgeArrow />
          </Pressable>
          <View style={st.nSep} />
          <Pressable onPress={() => setNudge(false)} accessibilityRole="button" accessibilityLabel="제안 닫기" style={st.nX}>
            <NudgeCross />
          </Pressable>
        </View>
      ) : null}
      {memo.ai_linked ? (
        <>
          <Text style={st.fn}><InlineSpark color={appColor.ink3} /> 뉴스는 원문 링크로 볼 수 있어요. 공시는 원문 일부를 짚어 보여 줘요. 주가는 전일 확정 종가 기준이에요.</Text>
          {sw}
        </>
      ) : null}
      {/* 원본 #dbody::after (AI 업데이트 탭) */}
      <Text style={st.disc}>투자 권유가 아닌 참고 정보예요 · AI는 틀릴 수 있어 원문을 꼭 확인해 주세요</Text>
    </View>
  );
}

/** 처음 AI 업데이트 탭을 열 때 1.2초 뼈대 (원본 renderAISkel: 머리 110×16 · 카드 150 · 74 · 74) */
export function AiTabSkeleton() {
  return (
    <View style={st.skel}>
      <SkBar w={110} h={16} />
      <View style={[st.skCard, { height: 150 }]}>
        <SkBar w={120} h={10} />
        <SkBar w={240} h={16} />
        <SkBar w={290} h={10} />
        <SkBar w={250} h={10} />
      </View>
      <View style={[st.skCard, { height: 74 }]}>
        <SkBar w={220} h={14} />
      </View>
      <View style={[st.skCard, { height: 74 }]}>
        <SkBar w={220} h={14} />
      </View>
    </View>
  );
}
function SkBar({ w, h }: { w: number; h: number }) {
  return <View style={{ width: w, maxWidth: '100%', height: h, borderRadius: 6, backgroundColor: '#E2E5EA' }} />;
}

/** 소식 카드 — 메모 상세 AI 탭 (원본 .uc: 라운드 18 · 안쪽 14·16 · 아래 10 · 종류별 바탕) */
export function FeedCard({ f, ver, open, onToggle, onOpenSource, onOpenEvidence }: { f: MemoFeedItem; ver?: MemoVersion; open: boolean; onToggle: () => void; onOpenSource?: (f: MemoFeedItem) => void; onOpenEvidence?: (f: MemoFeedItem) => void }) {
  const [bg, ic] = FK[f.kind];
  const [cite, setCite] = useState(false);
  const srcName = f.source.split(' · ')[0];
  return (
    <View style={[st.uc, { backgroundColor: bg }]}>
      <Pressable onPress={onToggle} accessibilityRole="button" accessibilityState={{ expanded: open }} style={st.uh}>
        <View style={st.ui}>
          <FeedKindIcon kind={f.kind} color={ic} />
        </View>
        <View style={st.flex}>
          <View style={st.umRow}>
            <Text style={st.um}>
              {f.kind} · {mmdd(f.arrived ?? f.at)}
            </Text>
            {f.unread ? (
              <View style={st.new}>
                <Text style={st.newT}>새</Text>
              </View>
            ) : null}
          </View>
          <Text style={st.ut}>{f.headline}</Text>
        </View>
        <View style={st.more}>
          <Text style={st.moreT}>{open ? '접기' : '자세히'}</Text>
          <Turn on={open}>
            <Chev12 />
          </Turn>
        </View>
      </Pressable>
      <Collapse open={open} duration={420}>
        <View style={st.ux}>
          <Text style={st.usum}>
            <Text style={cite ? st.sOn : null}>{f.summary}</Text>
            {f.kind === '주가' ? <Text style={{ color: '#6B7079' }}> (코드 계산)</Text> : null}
            {f.kind === '공시' && f.quote ? (
              <Text onPress={() => setCite((c) => !c)} accessibilityRole="button" accessibilityLabel="출처 1" style={[st.cite, cite && st.citeOn]}>
                {' 1 '}
              </Text>
            ) : null}
          </Text>
          {f.kind === '공시' && f.quote ? (
            <Collapse open={cite} duration={400}>
              <View style={st.quote}>
                <Text style={st.quoteT}>
                  {splitMark(f.quote, f.quote_mark).map((p, i) => (
                    <Text key={i} style={p.mark && cite ? st.mark : null}>
                      {p.t}
                    </Text>
                  ))}
                </Text>
                <View style={st.from}>
                  <Text style={st.fromT}>DART · {mmdd(f.at)} · 원문 일부</Text>
                  <Pressable onPress={() => onOpenSource?.(f)} accessibilityRole="link" hitSlop={8}>
                    <Text style={st.fromB}>원문 열기 ↗</Text>
                  </Pressable>
                </View>
              </View>
            </Collapse>
          ) : null}
          {f.kind === '뉴스' ? (
            <View style={st.nlink}>
              <Text style={st.nsrc}>{srcName}</Text>
              <Text style={st.nlinkB}>{f.article_title}</Text>
              <Pressable onPress={() => onOpenSource?.(f)} accessibilityRole="link" style={st.selfStart}>
                <Text style={st.nlinkBtn}>원문 기사 열기 ↗</Text>
              </Pressable>
            </View>
          ) : null}
          {ver ? (
            <View style={st.lm}>
              <Text style={st.lmB}>
                연결된 내 메모 · 버전 {ver.version} ({mmdd(ver.saved_at)})
              </Text>
              <Text style={st.lmT} numberOfLines={2}>
                {ver.title}
              </Text>
            </View>
          ) : null}
          <Text style={st.ufrom}>{f.kind === '뉴스' ? '기사 내용은 원문 링크에서 볼 수 있어요' : f.kind === '공시' ? `출처 · ${f.source}` : `시세 · ${f.source}`}</Text>
          <Pressable onPress={() => onOpenEvidence?.(f)} accessibilityRole="button" style={st.evlink}>
            <Text style={st.evlinkT}>근거 자세히 보기 ›</Text>
          </Pressable>
        </View>
      </Collapse>
    </View>
  );
}

/* 공시 원문에서 밑줄 칠 부분을 나눔 */
export function splitMark(q: string, mark?: string) {
  if (!mark || !q.includes(mark)) return [{ t: q, mark: false }];
  const i = q.indexOf(mark);
  return [
    { t: q.slice(0, i), mark: false },
    { t: mark, mark: true },
    { t: q.slice(i + mark.length), mark: false },
  ];
}

/** 메모 기록 줄 (원본 .mrw: 라운드 16 · 펼치면 #F7F5FD · 그림 30 #F1EEFB · 14px 600 #3F2C7A · '펼치기' 12.5px 700 #6A42AB) */
function RevRow({ v, first, color, open, onToggle }: { v: MemoVersion; first: boolean; color: Memo['color']; open: boolean; onToggle: () => void }) {
  const paper = usePaper();
  const p = paper[color];
  return (
    <View style={[st.mrw, open && { backgroundColor: '#F7F5FD' }]}>
      <Pressable onPress={onToggle} accessibilityRole="button" accessibilityState={{ expanded: open }} style={st.mrh}>
        <View style={st.mic}>
          <RevIcon first={first} />
        </View>
        <Text style={st.mtx}>
          {mmdd(v.saved_at)} · {first ? '첫 메모를 남겼어요' : '메모를 수정했어요'}
        </Text>
        <View style={st.mmore}>
          <Text style={st.mmoreT}>{open ? '접기' : '펼치기'}</Text>
          <Turn on={open}>
            <Chev12 color={appColor.deepPurple} />
          </Turn>
        </View>
      </Pressable>
      <Collapse open={open} duration={420}>
        <PaperBox bg={p.bg} accent={p.accent} radius={14} cut={18} style={st.mver}>
          <Text style={st.mverB}>{v.title}</Text>
          {v.body ? <Text style={st.mverP}>{v.body}</Text> : null}
        </PaperBox>
      </Collapse>
    </View>
  );
}

/** 펼침 화살 돌기 (원본 .35s) */
export function Turn({ on, children }: { on: boolean; children: React.ReactNode }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(on ? 1 : 0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: on ? 1 : 0, duration: 350 * k, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: NATIVE });
    a.start();
    return () => a.stop();
  }, [on, v, k]);
  return <Animated.View style={{ transform: [{ rotate: v.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '180deg'] }) }] }}>{children}</Animated.View>;
}

/** 연결됐지만 소식 없음 (원본 waitBlock: 지켜보는 중 · 확인 중인 항목 · '기록') */
function WatchBlock({ items, since, lastChecked }: { items: AiTrackItem[]; since: string; lastChecked?: string }) {
  return (
    <>
      <View style={st.watch}>
        <View style={st.wico}>
          <Pulse delay={0} />
          <Pulse delay={1200} />
          <View style={st.wc}>
            <AppPlug size={22} />
          </View>
        </View>
        <Text style={st.watchB}>AI가 이 메모를 지켜보고 있어요</Text>
        <Text style={st.watchP}>{'아직 관련된 새 소식이 없어요.\n소식은 바로 오지 않을 수 있어요.'}</Text>
        <Text style={st.wmeta}>
          {since} 연결{lastChecked ? ` · 마지막 확인 ${lastChecked}` : ''}
        </Text>
      </View>
      <Text style={st.wh}>확인 중인 항목 {items.length}</Text>
      {items.map((x, i) => {
        const c = CHIP[x.kind];
        return (
          <View key={i} style={st.wit}>
            <View style={[st.chp, { backgroundColor: c.bg }]}>
              <Text style={[st.chpT, { color: c.ink }]}>{c.label}</Text>
            </View>
            <Text style={st.witB}>{x.label}</Text>
            <View style={st.wst}>
              <View style={st.wstDot} />
              <Text style={st.wstT}>{x.kind === 'price' ? '아직 조건에 닿지 않았어요 · 장 마감 후 종가로 확인' : '아직 관련 공시·뉴스가 없어요 · 새로 나오면 확인'}</Text>
            </View>
          </View>
        );
      })}
      <Text style={st.wnote}>소식이 오면 메모 카드에 빨간 숫자가 붙고, 여기에 날짜순으로 쌓여요.</Text>
      <Text style={st.hsec}>기록</Text>
    </>
  );
}

/** 원본 .wr: 테두리 2 #CDBDF0 원이 1 → 1.9 배로 퍼지며 사라짐 (2.4s · 두 번째는 1.2s 늦게) */
function Pulse({ delay }: { delay: number }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (k < 1) return;
    const a = Animated.sequence([Animated.delay(delay), Animated.loop(Animated.timing(v, { toValue: 1, duration: 2400, easing: Easing.out(Easing.quad), useNativeDriver: NATIVE }))]);
    a.start();
    return () => a.stop();
  }, [v, k, delay]);
  return <Animated.View style={[st.wr, { opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0.9, 0] }), transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [1, 1.9] }) }] }]} />;
}

const st = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  selfStart: { alignSelf: 'flex-start' },
  off: { ...ft(15, 1.7), color: appColor.ink2, textAlign: 'center', paddingTop: 26, paddingHorizontal: 10, paddingBottom: 18 },
  aic: { backgroundColor: '#F6F6F8', borderRadius: 16, padding: 16, flexDirection: 'row', alignItems: 'center', gap: 10 },
  aicB: { ...ft(15.5), fontWeight: '700', color: appColor.ink },
  aicS: { ...ft(13.5), color: '#6B7079' },
  hsec: { ...ft(14), fontWeight: '800', color: appColor.ink2, marginTop: 20, marginHorizontal: 4, marginBottom: 4 },
  uhd: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 2, marginHorizontal: 2, marginBottom: 12 },
  uhdT: { ...ft(15.5), fontWeight: '800', color: appColor.ink },
  uhdS: { ...ft(14), fontWeight: '500', color: appColor.ink2 },
  hrw: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, paddingHorizontal: 6 },
  hrwT: { ...ft(15), color: '#3F434A', flexShrink: 1 },
  mic: { width: 30, height: 30, borderRadius: 9, backgroundColor: '#F1EEFB', alignItems: 'center', justifyContent: 'center' },
  /* 소식 카드 */
  uc: { borderRadius: 18, paddingVertical: 14, paddingHorizontal: 16, marginBottom: 10 },
  uh: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  ui: { width: 34, height: 34, borderRadius: 10, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  umRow: { flexDirection: 'row', alignItems: 'center' },
  um: { ...ft(13.5), color: appColor.ink2 },
  new: { backgroundColor: appColor.red, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1, marginLeft: 4 },
  newT: { ...ft(11.5), fontWeight: '700', color: '#FFFFFF' },
  ut: { ...ft(16, 1.4), fontWeight: '800', color: appColor.ink, marginTop: 2 },
  more: { flexDirection: 'row', alignItems: 'center', gap: 2, paddingTop: 2 },
  moreT: { ...ft(14), color: appColor.ink2 },
  ux: { paddingBottom: 0 },
  usum: { ...ft(15.5, 1.8), color: '#25262B', marginTop: 10, marginLeft: 44 },
  sOn: { backgroundColor: 'rgba(133,105,227,0.28)' },
  cite: { ...ft(11.5), fontWeight: '800', color: appColor.deepPurple, backgroundColor: 'rgba(133,105,227,0.16)' },
  citeOn: { color: '#FFFFFF', backgroundColor: appColor.accent },
  quote: { marginTop: 10, marginBottom: 2, marginLeft: 44, backgroundColor: '#FFFFFF', borderRadius: 12, paddingVertical: 12, paddingHorizontal: 14, borderLeftWidth: 3, borderLeftColor: appColor.accent },
  quoteT: { ...ft(14.5, 1.75), color: '#3F434A' },
  mark: { backgroundColor: 'rgba(255,211,0,0.5)' },
  from: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 },
  fromT: { ...ft(13), color: '#6B7079', flexShrink: 1 },
  fromB: { ...ft(13), fontWeight: '700', color: appColor.deepPurple },
  nlink: { marginTop: 10, marginLeft: 44, backgroundColor: '#FFFFFF', borderRadius: 12, paddingVertical: 12, paddingHorizontal: 14 },
  nsrc: { ...ft(13), color: '#6B7079' },
  nlinkB: { ...ft(15.5, 1.45), fontWeight: '700', color: appColor.ink, marginTop: 4, marginBottom: 8 },
  nlinkBtn: { ...ft(14), fontWeight: '700', color: appColor.deepPurple },
  lm: { marginTop: 10, marginLeft: 44, backgroundColor: 'rgba(255,255,255,0.65)', borderLeftWidth: 3, borderLeftColor: '#C9CDD4', paddingVertical: 8, paddingHorizontal: 12, borderTopRightRadius: 8, borderBottomRightRadius: 8 },
  lmB: { ...ft(13), fontWeight: '600', color: appColor.ink2 },
  lmT: { ...ft(14.5), color: appColor.ink },
  ufrom: { ...ft(13), color: '#6B7079', marginTop: 10, marginBottom: 2, marginLeft: 44 },
  evlink: { alignSelf: 'flex-start', marginTop: 10, marginLeft: 44 },
  evlinkT: { ...ft(14.5), fontWeight: '700', color: appColor.deepPurple },
  /* 메모 기록 */
  mrw: { borderRadius: 16, marginTop: 2, marginBottom: 6 },
  mrh: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 11, paddingHorizontal: 8 },
  mtx: { flex: 1, minWidth: 0, ...ft(15, 1.4), fontWeight: '600', color: '#3F2C7A', paddingTop: 5 },
  mmore: { flexDirection: 'row', alignItems: 'center', gap: 2, paddingTop: 6 },
  mmoreT: { ...ft(13.5), fontWeight: '700', color: appColor.deepPurple },
  mver: { marginLeft: 48, marginRight: 8, marginBottom: 6, paddingTop: 12, paddingHorizontal: 14, paddingBottom: 18 },
  mverB: { ...ft(15.5), fontWeight: '700', color: appColor.ink, marginBottom: 4 },
  mverP: { ...ft(14.5, 1.7), color: '#2E2E38' },
  /* 지켜보는 중 */
  watch: { alignItems: 'center', paddingTop: 22, paddingHorizontal: 14, paddingBottom: 18, backgroundColor: '#FBF8FF', borderRadius: 20, marginTop: 2, marginBottom: 14 },
  wico: { width: 56, height: 56 },
  wr: { position: 'absolute', left: 0, top: 0, width: 56, height: 56, borderRadius: 28, borderWidth: 2, borderColor: '#CDBDF0' },
  wc: { position: 'absolute', left: 0, top: 0, width: 56, height: 56, borderRadius: 28, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center', shadowColor: '#6A42AB', shadowOpacity: 0.15, shadowRadius: 10, shadowOffset: { width: 0, height: 2 }, elevation: 3 },
  watchB: { ...ft(16), fontWeight: '800', color: appColor.ink, marginTop: 12 },
  watchP: { ...ft(14, 1.55), color: '#6B7079', marginTop: 6, textAlign: 'center' },
  wmeta: { ...ft(11.5), color: '#6B7079', marginTop: 12 },
  wh: { ...ft(14), fontWeight: '700', color: appColor.ink, marginTop: 4, marginHorizontal: 4, marginBottom: 8 },
  wit: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#EEEFF2', borderRadius: 16, paddingVertical: 12, paddingHorizontal: 14, marginBottom: 8 },
  chp: { alignSelf: 'flex-start', borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 },
  chpT: { ...ft(11.5), fontWeight: '800' },
  witB: { ...ft(15), fontWeight: '700', color: appColor.ink, marginTop: 7, marginBottom: 6 },
  wst: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  wstDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#C9CCD2' },
  wstT: { ...ft(13, 1.4), color: '#6B7079', flexShrink: 1 },
  wnote: { ...ft(13, 1.5), color: '#6B7079', marginTop: 6, marginHorizontal: 4, marginBottom: 4 },
  /* 넛지 · 안내 */
  nudge: { flexDirection: 'row', alignItems: 'center', minHeight: 48, marginTop: 6, marginBottom: 10, borderRadius: 14, backgroundColor: appColor.nudge, overflow: 'hidden' },
  nGo: { flex: 1, minWidth: 0, minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: 8, paddingLeft: 14, paddingRight: 10, paddingVertical: 6 },
  nGoT: { flex: 1, minWidth: 0, ...ft(15.5), fontWeight: '700', color: '#FFFFFF' },
  nSep: { width: 1, height: 20, backgroundColor: 'rgba(255,255,255,0.2)' },
  nX: { width: 44, minHeight: 48, alignSelf: 'stretch', alignItems: 'center', justifyContent: 'center' },
  fn: { ...ft(13), color: '#6B7079', marginTop: 6, marginHorizontal: 4, marginBottom: 14 },
  disc: { ...ft(13, 1.6), color: '#6B7079', textAlign: 'center', paddingTop: 14, paddingHorizontal: 20, paddingBottom: 26 },
  /* 뼈대 */
  skel: { gap: 12, paddingTop: 2 },
  skCard: { borderRadius: 18, backgroundColor: '#ECEEF2', padding: 16, gap: 10 },
});
