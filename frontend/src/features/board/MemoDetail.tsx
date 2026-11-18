/**
 * 메모 상세 — [메모 | AI 업데이트] 두 탭. 체험판 memo.html 의 상세 화면.
 *  - 메모 탭: 메모지(색 · 고정 테이프 · 접힌 모서리). 누르면 바로 수정(첫 줄 = 제목)
 *  - AI 업데이트 탭: 도착한 소식(뉴스 한 줄 + 기사 제목 · 공시 요약 · 가격 조건) → 근거 자세히 보기
 *    소식이 없으면 추적 중인 항목 + 기록 줄. 맨 아래 "투자 권유가 아닌 참고 정보" 한 줄
 * 상단 바(‹ 메모 보드 · ⋯ / 수정 중이면 완료)는 TopBar 로 따로.
 * 움직임: 탭 알약(#039) · 탭 내용 바뀜(ft .21s) · 메모지 줄이 옆에서 차례로(pin) · 소식 카드가 차례로 떠오름(rvin 60ms)
 *         · 요약 끝 [출처] 칩을 누르면 출처가 펼쳐짐(#224 · .42s) · AI 연결 스위치(.4s spring)
 */
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import Svg, { Polygon } from 'react-native-svg';
import { MobileIcon, type MobileIconName } from '@/components/icons/MobileIcons';
import { Appear, PopWhen } from '@/components/motion/Appear';
import { Chevron, Collapse } from '@/components/motion/Collapse';
import { SlidingPill } from '@/components/motion/SlidingPill';
import { Toggle } from '@/components/motion/Toggle';
import { BOARD_C as C, MEMO_PAPER } from '@/features/board/boardTokens';
import type { DetailUpdate, MemoDetailProps } from '@/features/board/MemoDetail.types';

const PAD = 16;
const R = { paper: 22, tabs: 15, tab: 12, card: 18 };
const KIND: Record<DetailUpdate['kind'], { label: string; bg: string; fg: string; icon: MobileIconName }> = {
  news: { label: '뉴스', bg: C.blueSoft, fg: C.blue, icon: 'news' },
  disclosure: { label: '공시', bg: C.accentSoft, fg: C.accentDeep, icon: 'journal' },
  price: { label: '가격 조건', bg: C.greenSoft, fg: C.green, icon: 'chart' },
};
const won = (n: number) => `${n.toLocaleString('ko-KR')}원`;

export function MemoDetail(p: MemoDetailProps) {
  const { memo, updates, tab, onChangeTab } = p;
  const newCount = updates.filter((u) => u.is_new).length;
  return (
    <View style={st.root}>
      <Text style={st.date}>{memo.date_full}</Text>
      {!p.editing && (
        <SlidingPill<'memo' | 'ai'> value={tab} onChange={onChangeTab} equal style={st.tabs} itemStyle={st.tab} pillStyle={st.tabOn}
          items={[
            { key: 'memo', label: '메모' },
            { key: 'ai', label: 'AI 업데이트', render: (on: boolean) => (
              <><Text style={[st.tabText, on && st.tabTextOn]}>AI 업데이트</Text>
                <PopWhen show={newCount > 0} replay={newCount} style={st.cnt}><Text style={st.cntText}>{newCount}</Text></PopWhen></>
            ) },
          ]} textStyle={st.tabText} textOnStyle={st.tabTextOn} />
      )}
      {p.ai_paused && (
        <Appear kind="up" style={st.paused}>
          <Text style={st.pausedTitle}>AI 연결이 잠시 멈췄어요</Text>
          <Text style={st.pausedText}>이번 달 AI 사용량을 다 썼어요.{'\n'}12월 1일에 다시 찾아요. 메모는 계속 쓸 수 있어요.</Text>
          <View style={st.pausedBtns}>
            <Pressable style={[st.pBtn, st.pBuy]} onPress={p.onBuyCredit}><Text style={st.pBuyText}>크레딧 구매</Text></Pressable>
            <Pressable style={[st.pBtn, st.pPlan]} onPress={p.onChangePlan}><Text style={st.pPlanText}>플랜 변경</Text></Pressable>
          </View>
        </Appear>
      )}
      <ScrollView contentContainerStyle={st.body} keyboardShouldPersistTaps="handled">
        <Appear kind="tab" replay={p.editing ? 'edit' : tab}>
          {tab === 'memo' || p.editing ? <MemoPaper {...p} /> : <AiTab {...p} />}
        </Appear>
      </ScrollView>
    </View>
  );
}

function MemoPaper({ memo, editing, draft, onStartEdit, onChangeDraft }: MemoDetailProps) {
  const paper = MEMO_PAPER[memo.color];
  return (
    <View>
      <Pressable onPress={editing ? undefined : onStartEdit} style={[st.paper, { backgroundColor: paper.bg }]} accessibilityHint="누르면 바로 수정할 수 있어요">
        {editing ? (
          <TextInput style={st.editor} value={draft} onChangeText={onChangeDraft} multiline autoFocus textAlignVertical="top" accessibilityLabel="메모 내용 (첫 줄은 제목)" />
        ) : (
          <>
            <Appear kind="pin" index={0}><Text style={st.pTitle}>{memo.title}</Text></Appear>
            <Appear kind="pin" index={1}><Text style={st.pBody}>{memo.body}</Text></Appear>
          </>
        )}
        <Svg width={28} height={28} style={st.fold}>
          <Polygon points="28,0 28,28 0,28" fill={C.card} />
          <Polygon points="0,0 28,0 0,28" fill={paper.fold} />
        </Svg>
      </Pressable>
      {memo.pinned && <View style={[st.tape, { backgroundColor: paper.fold }]} />}
      <Text style={st.caption}>{editing ? '첫 줄은 제목이 돼요 · 나갈 때 한 번씩 저장돼요' : '글을 누르면 바로 수정할 수 있어요'}</Text>
    </View>
  );
}

function AiTab({ memo, updates, onOpenEvidence, onOpenOriginal, onToggleAi, onOpenHistory }: MemoDetailProps) {
  if (!memo.ai_linked) {
    return (
      <View>
        <Text style={st.offText}>AI 연결을 켜면 이 메모와 관련된{'\n'}공시·뉴스·주가 변화를 여기서 모아 볼 수 있어요.</Text>
        <AiSwitch on={false} text="켜면 관련 소식을 모아 드려요" onPress={onToggleAi} />
        <Pressable style={st.histLink} onPress={onOpenHistory}><Text style={st.histText}>수정 이력 보기 ›</Text></Pressable>
      </View>
    );
  }
  return (
    <View>
      <View style={st.uhd}><Text style={st.uhdText}>도착한 소식 {updates.length}</Text><Text style={st.uhdSub}>최신순</Text></View>
      {updates.length === 0 ? (
        <>
          <View style={st.emptyCard}>
            <Text style={st.emptyTitle}>아직 도착한 소식이 없어요</Text>
            <Text style={st.emptyText}>추적 중인 항목과 관련된 공시·뉴스·종가 변화가{'\n'}생기면 여기에 모아 드려요.</Text>
          </View>
          <Text style={st.trkHead}>추적 중인 항목 {memo.tracking_items.length}</Text>
          {memo.tracking_items.map((t, i) => (
            <Appear key={t.id} kind="up" index={i + 1} style={st.hrw}>
              <View style={[st.kTag, { backgroundColor: t.kind === 'price' ? C.greenSoft : C.blueSoft }]}>
                <Text style={[st.kTagText, { color: t.kind === 'price' ? C.green : C.blue }]}>{t.kind === 'price' ? '가격 조건' : '공시·뉴스'}</Text>
              </View>
              <Text style={st.hrwText} numberOfLines={2}>{t.label}</Text>
            </Appear>
          ))}
          {!!memo.ai_linked_on && <View style={st.hrw}><MobileIcon name="plug" size={16} color={C.text} /><Text style={st.hrwText}>{memo.ai_linked_on} · AI 연결을 시작했어요</Text></View>}
          <View style={st.hrw}><MobileIcon name="memo" size={18} color={C.text} /><Text style={st.hrwText}>{memo.created_on} · 첫 메모를 남겼어요</Text></View>
        </>
      ) : (
        updates.map((u, i) => (
          <Appear key={u.id} kind="up" index={i}>
            <UpdateCard u={u} onEvidence={() => onOpenEvidence(u.id)} onOriginal={() => onOpenOriginal(u.id)} />
          </Appear>
        ))
      )}
      <Text style={st.fn}>✦ 뉴스는 원문 링크로 볼 수 있어요. 공시는 AI가 요약해요. 주가는 전일 확정 종가 기준이에요.</Text>
      <AiSwitch on text="이 메모를 AI가 지켜보고 있어요" onPress={onToggleAi} />
      <Text style={st.disclaimer}>투자 권유가 아닌 참고 정보예요 · AI는 틀릴 수 있어 원문을 꼭 확인해 주세요</Text>
    </View>
  );
}

function UpdateCard({ u, onEvidence, onOriginal }: { u: DetailUpdate; onEvidence: () => void; onOriginal: () => void }) {
  const k = KIND[u.kind];
  const [src, setSrc] = useState(false);
  return (
    <View style={st.uc}>
      <View style={st.ucHead}>
        <View style={[st.ui, { backgroundColor: k.bg }]}><MobileIcon name={k.icon} size={18} color={k.fg} /></View>
        <View style={st.flex}>
          <View style={st.metaRow}>
            <Text style={st.meta}>{k.label} · {u.date}</Text>
            {u.is_new && <View style={st.newTag}><Text style={st.newText}>새</Text></View>}
          </View>
          <Text style={st.headline}>{u.headline}</Text>
        </View>
      </View>
      <Text style={st.summary}>{u.summary}</Text>
      {/* #224 출처 칩: 요약이 어디서 왔는지 펼쳐 봄 */}
      <Pressable style={st.citeRow} onPress={() => setSrc((v) => !v)} hitSlop={8} accessibilityRole="button" accessibilityState={{ expanded: src }}>
        <Appear kind="scale" delay={300}><View style={st.cite}><Text style={st.citeText}>출처</Text></View></Appear>
        <Text style={st.citeLabel} numberOfLines={1}>{u.source}</Text>
        <Chevron open={src} color={C.muted} size={14} />
      </Pressable>
      <Collapse open={src}>
        <View style={st.srcBox}>
          <Text style={st.srcLine}>{k.label} · {u.source} · {u.date}</Text>
          <Text style={st.srcNote}>{u.kind === 'news' ? '기사 내용은 원문에서 확인해 주세요.' : u.kind === 'disclosure' ? '공시 원문을 AI가 요약했어요. 숫자는 원문과 함께 확인해 주세요.' : '전일 확정 종가로 계산했어요.'}</Text>
        </View>
      </Collapse>
      {u.kind === 'news' && !!u.article_title && (
        <Pressable style={st.article} onPress={onOriginal} accessibilityRole="link">
          <Text style={st.articleSrc}>{u.source}</Text>
          <Text style={st.articleTitle} numberOfLines={2}>{u.article_title}</Text>
          <Text style={st.articleLink}>원문 기사 열기 ↗</Text>
        </Pressable>
      )}
      {u.kind === 'price' && u.price && (
        <View style={st.priceBox}>
          <View style={st.kv}><Text style={st.kvK}>전일 종가</Text><Text style={st.kvV}>{won(u.price.close)}</Text></View>
          <View style={st.kv}><Text style={st.kvK}>조건가</Text><Text style={st.kvV}>{won(u.price.condition)} 이하</Text></View>
          <View style={st.kv}><Text style={st.kvK}>조건과의 차이</Text><Text style={[st.kvV, { color: u.price.tone === 'near' ? C.red : C.blue }]}>{u.price.gap_text}</Text></View>
        </View>
      )}
      <Pressable style={st.evLink} onPress={onEvidence} accessibilityRole="button"><Text style={st.evText}>근거 자세히 보기 ›</Text></Pressable>
    </View>
  );
}

function AiSwitch({ on, text, onPress }: { on: boolean; text: string; onPress: () => void }) {
  return (
    <View style={st.aic}>
      <View style={st.flex}><Text style={st.aicTitle}>AI 연결</Text><Text style={st.aicSub}>{text}</Text></View>
      <Toggle value={on} onChange={onPress} onColor={C.accent} offColor={C.chipLine} accessibilityLabel="AI 연결" />
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.card },
  flex: { flex: 1, minWidth: 0 },
  date: { textAlign: 'center', fontSize: 13, color: C.sub, marginBottom: 12 },
  tabs: { flexDirection: 'row', marginHorizontal: PAD, backgroundColor: C.appBg, borderRadius: R.tabs, height: 48, padding: 4 },
  tab: { alignSelf: 'stretch', gap: 6 },
  tabOn: { backgroundColor: C.card, borderRadius: R.tab },
  tabText: { fontSize: 15, color: C.sub },
  tabTextOn: { fontWeight: '800', color: C.text },
  cnt: { minWidth: 19, height: 19, borderRadius: 10, backgroundColor: C.red, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5 },
  cntText: { fontSize: 11, fontWeight: '700', color: C.white },
  paused: { marginHorizontal: PAD, marginTop: 12, borderRadius: 14, padding: 14, backgroundColor: C.warnBg },
  pausedTitle: { fontSize: 14.5, fontWeight: '800', color: C.warnText },
  pausedText: { fontSize: 13, lineHeight: 20, color: C.warnText, marginTop: 4 },
  pausedBtns: { flexDirection: 'row', gap: 8, marginTop: 10 },
  pBtn: { flex: 1, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  pBuy: { backgroundColor: C.warnBtn },
  pBuyText: { color: C.white, fontWeight: '700', fontSize: 14 },
  pPlan: { backgroundColor: C.card, borderWidth: 1, borderColor: C.warnLine },
  pPlanText: { color: C.warnText, fontWeight: '700', fontSize: 14 },
  body: { padding: PAD, paddingBottom: 60 },
  paper: { borderRadius: R.paper, paddingHorizontal: 20, paddingTop: 26, paddingBottom: 34, minHeight: 320, overflow: 'hidden' },
  pTitle: { fontSize: 21, fontWeight: '800', color: C.text, lineHeight: 29, marginTop: 4, marginBottom: 8 },
  pBody: { fontSize: 15.5, lineHeight: 28, color: C.body },
  editor: { fontSize: 15.5, lineHeight: 28, color: C.body, minHeight: 240, padding: 0 },
  fold: { position: 'absolute', right: 0, bottom: 0 },
  tape: { position: 'absolute', top: -8, alignSelf: 'center', width: 57, height: 19, opacity: 0.82, transform: [{ rotate: '-3deg' }] },
  caption: { textAlign: 'center', fontSize: 12.5, color: C.muted, marginTop: 12 },
  offText: { textAlign: 'center', fontSize: 14, lineHeight: 22, color: C.sub, paddingVertical: 36 },
  histLink: { alignSelf: 'center', minHeight: 44, justifyContent: 'center', marginTop: 4 },
  histText: { fontSize: 13, fontWeight: '700', color: C.accentDeep },
  uhd: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 },
  uhdText: { fontSize: 16, fontWeight: '800', color: C.text },
  uhdSub: { fontSize: 12.5, color: C.muted },
  emptyCard: { borderRadius: R.card, backgroundColor: C.appBg, padding: 22, alignItems: 'center' },
  emptyTitle: { fontSize: 15, fontWeight: '800', color: C.text },
  emptyText: { fontSize: 13, lineHeight: 20, color: C.sub, textAlign: 'center', marginTop: 6 },
  trkHead: { fontSize: 13, fontWeight: '700', color: C.text, marginTop: 14, marginBottom: 4 },
  hrw: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: C.line },
  hrwText: { flex: 1, fontSize: 13.5, color: C.text },
  kTag: { borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 },
  kTagText: { fontSize: 11, fontWeight: '800' },
  uc: { borderRadius: R.card, backgroundColor: C.appBg, padding: 14, marginBottom: 12 },
  ucHead: { flexDirection: 'row', gap: 10 },
  ui: { width: 36, height: 36, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  meta: { fontSize: 12, color: C.sub },
  newTag: { backgroundColor: C.red, borderRadius: 6, paddingHorizontal: 5, paddingVertical: 1 },
  newText: { fontSize: 11, fontWeight: '700', color: C.white },
  headline: { fontSize: 15, fontWeight: '800', color: C.text, marginTop: 2 },
  summary: { fontSize: 13.5, lineHeight: 21, color: C.body, marginTop: 10 },
  article: { marginTop: 10, borderRadius: 14, backgroundColor: C.card, padding: 12 },
  articleSrc: { fontSize: 12, color: C.sub },
  articleTitle: { fontSize: 14.5, fontWeight: '800', color: C.text, marginTop: 4 },
  articleLink: { fontSize: 13, fontWeight: '700', color: C.accentDeep, marginTop: 6 },
  priceBox: { marginTop: 10, borderRadius: 14, backgroundColor: C.card, paddingHorizontal: 12, paddingVertical: 4 },
  kv: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 7 },
  kvK: { fontSize: 13, color: C.sub },
  kvV: { fontSize: 13, fontWeight: '700', color: C.text },
  evLink: { minHeight: 44, justifyContent: 'center' },
  evText: { fontSize: 13.5, fontWeight: '700', color: C.accentDeep },
  fn: { fontSize: 12, lineHeight: 18, color: C.muted, marginTop: 6 },
  aic: { flexDirection: 'row', alignItems: 'center', borderRadius: 16, backgroundColor: C.appBg, padding: 14, marginTop: 14, minHeight: 64 },
  aicTitle: { fontSize: 15, fontWeight: '800', color: C.text },
  aicSub: { fontSize: 12.5, color: C.sub, marginTop: 2 },
  citeRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10, minHeight: 28 },
  cite: { height: 19, paddingHorizontal: 6, borderRadius: 6, backgroundColor: C.accentSoft, justifyContent: 'center' },
  citeText: { fontSize: 11, fontWeight: '800', color: C.accentDeep },
  citeLabel: { flexShrink: 1, fontSize: 12, color: C.muted },
  srcBox: { marginTop: 6, borderRadius: 12, backgroundColor: C.card, padding: 10, gap: 4 },
  srcLine: { fontSize: 12.5, fontWeight: '700', color: C.text },
  srcNote: { fontSize: 12, lineHeight: 18, color: C.sub },
  disclaimer: { fontSize: 12, lineHeight: 19, color: C.muted, textAlign: 'center', marginTop: 18 },
});
