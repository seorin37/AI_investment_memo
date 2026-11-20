import React, { useEffect, useRef, useState } from 'react';
import { BackHandler, KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { joinMemo, splitMemo } from '@/lib/memoText';
import { BackChevron, DotsH } from '@/ui/icons/MemoGlyphs';
import { FadeIn } from '@/ui/motion/Reveal';
import { AiOffSheet } from '@/ui/shared/AiOffSheet';
import { MemoEditor } from '@/ui/shared/MemoEditor';
import { AppTape } from '@/ui/shared/MemoPaper';
import { PaperBox } from '@/ui/shared/PaperBox';
import { Seg } from '@/ui/shared/Seg';
import { AppSnackbar } from '@/ui/shared/Snackbar';
import { SpentBox } from '@/ui/shared/SpentBox';
import { appColor, ft } from '@/ui/theme';
import type { MemoDetailProps } from '../MemoDetail.types';
import { koDate } from '../memoTimeline';
import { AiTabSkeleton, AppAiTab } from './MemoFeed';
import { MemoMoreSheet, type MoreAction } from './MemoMoreSheet';
import { usePaper } from '@/ui/shared/Dark';

type Snack = { id: number; msg: string };

/**
 * 앱 메모 상세 (원본 memo.html #detail: 밀려 들어오는 전체 화면)
 * 머리 56 (뒤로 + '메모 보드' 17px 600 · 편집 중이면 [완료] 16px 800 #6A42AB · 아니면 ⋯) · 날짜 13px #575B63 가운데 (아래 12)
 * [메모 | AI 업데이트 N] 알약 탭 (좌우 16 · 48) · 내용 (안쪽 16 · 아래 40, 편집 중 아래 300)
 * 메모 탭: 종이 (라운드 22 22 0 22 · 접힌 28 · 안쪽 26·20·34 · 최소 320 · 고정이면 테이프) — 글을 누르면 바로 편집 (첫 줄 = 제목)
 * 안드로이드 뒤로: (시트) → 편집 취소 → 화면
 */
export function AppMemoDetail(p: MemoDetailProps) {
  const paper = usePaper();
  const insets = useSafeAreaInsets();
  const m = p.memo;
  const pc = paper[m.color];
  const joined = joinMemo(m.title, m.body);
  const [tab, setTab] = useState<'memo' | 'ai'>(p.initialTab ?? 'memo');
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(joined);
  const [more, setMore] = useState(false);
  const [off, setOff] = useState(false);
  const [aiReady, setAiReady] = useState(!m.ai_linked || p.initialTab !== 'ai');
  const [histSignal, setHistSignal] = useState(0);
  const [snack, setSnack] = useState<Snack | null>(null);
  const [editorKey, setEditorKey] = useState(0);
  const ed = useRef<{ focus: () => void; blur: () => void }>(null);
  const seen = useRef(false);
  const unread = p.feed.filter((f) => f.unread).length;
  /* 근거 상세 [메모 보기] → 메모 탭 (원본 popOv → setDTab('memo')) */
  const [reqKey, setReqKey] = useState(p.tabRequest?.key);
  if (p.tabRequest && p.tabRequest.key !== reqKey) {
    setReqKey(p.tabRequest.key);
    setTab(p.tabRequest.tab);
  }

  const toast = (msg: string) => setSnack((s) => ({ id: (s?.id ?? 0) + 1, msg }));
  useEffect(() => {
    if (!snack) return;
    const t = setTimeout(() => setSnack((s) => (s && s.id === snack.id ? null : s)), 2400);
    return () => clearTimeout(t);
  }, [snack]);

  /* 원본: AI 업데이트 탭을 처음 열면 1.2초 뼈대 */
  useEffect(() => {
    if (tab !== 'ai' || aiReady) return;
    const t = setTimeout(() => setAiReady(true), 1200);
    return () => clearTimeout(t);
  }, [tab, aiReady]);
  /* AI 업데이트 탭을 보면 읽음 (원본 seenAI → 나갈 때 배지 지움) */
  const onSeen = p.onSeenUpdates;
  useEffect(() => {
    if (tab === 'ai' && !seen.current) {
      seen.current = true;
      onSeen?.();
    }
  }, [tab, onSeen]);

  const startEdit = () => {
    if (editing) return;
    setDraft(joined);
    setEditing(true);
    setTimeout(() => ed.current?.focus(), 60);
  };
  const cancelEdit = () => {
    ed.current?.blur();
    setEditing(false);
    setDraft(joined);
    setEditorKey((n) => n + 1);
  };
  /* 원본 finishEdit: 글이 바뀐 경우에만 저장 · 빈 메모는 저장 안 함 */
  const finishEdit = () => {
    ed.current?.blur();
    setEditing(false);
    const r = splitMemo(draft);
    const empty = !draft.trim();
    if (empty) {
      toast('빈 메모로는 저장하지 않았어요');
      setEditorKey((n) => n + 1);
      return;
    }
    if (r.title === m.title && r.body === m.body) return;
    p.onSave(r);
    setTimeout(() => toast('저장했어요 · 수정 이력에 1개 추가'), 150);
  };

  /* 안드로이드 뒤로: 편집 중이면 편집 취소가 먼저 (시트는 Modal 이 먼저 받음) */
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (editing) {
        cancelEdit();
        return true;
      }
      return false;
    });
    return () => sub.remove();
  });

  const onMore = (a: MoreAction) => {
    setMore(false);
    if (a === 'hist')
      setTimeout(() => {
        setTab('ai');
        setHistSignal((n) => n + 1);
      }, 200);
    else if (a === 'copy') {
      p.onCopy();
      setTimeout(() => toast('내용을 복사했어요'), 200);
    } else if (a === 'pin') {
      p.onTogglePin(!m.pinned);
      setTimeout(() => toast(m.pinned ? '고정을 풀었어요' : '메모를 고정했어요'), 200);
    } else if (a === 'ai') setTimeout(() => (m.ai_linked ? setOff(true) : p.onConnectAi()), 200);
    else p.onDelete();
  };
  const toggleAi = () => (m.ai_linked ? setOff(true) : p.onConnectAi());
  const changed = m.updated_at.slice(0, 10) !== m.created_at.slice(0, 10);

  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <View style={st.dh}>
        <Pressable
          onPress={() => {
            if (editing) finishEdit();
            p.onBack();
          }}
          accessibilityRole="button"
          accessibilityLabel="뒤로"
          style={st.iconbtn}
        >
          <BackChevron />
        </Pressable>
        <Text style={st.dhT} numberOfLines={1}>
          {p.backLabel ?? '메모 보드'}
        </Text>
        {editing ? (
          <Pressable onPress={finishEdit} accessibilityRole="button" style={st.done}>
            <Text style={st.doneT}>완료</Text>
          </Pressable>
        ) : (
          <Pressable onPress={() => setMore(true)} accessibilityRole="button" accessibilityLabel="메모 메뉴" style={st.iconbtn}>
            <DotsH />
          </Pressable>
        )}
      </View>
      <Text style={st.ddate}>
        {koDate(changed ? m.updated_at : m.created_at)} {changed ? '수정' : '작성'}
      </Text>
      {!editing ? (
        <View style={st.ptabs}>
          <Seg
            variant="appDetail"
            value={tab}
            onChange={(t) => setTab(t)}
            options={[
              { key: 'memo', label: '메모' },
              { key: 'ai', label: 'AI 업데이트', count: unread || undefined },
            ]}
          />
        </View>
      ) : null}
      {p.aiSpent && !editing ? (
        <View style={st.spb}>
          <SpentBox variant="app" title="AI 연결이 잠시 멈췄어요" body={'이번 달 AI 사용량을 다 썼어요.\n12월 1일에 다시 찾아요. 메모는 계속 쓸 수 있어요.'} onCredit={() => p.onSpentAction?.('credit')} onPlan={() => p.onSpentAction?.('plan')} />
        </View>
      ) : null}
      <KeyboardAvoidingView style={st.flex} behavior="padding">
        <ScrollView style={st.flex} contentContainerStyle={[st.dbody, editing && { paddingBottom: 300 }]} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          {tab === 'memo' ? (
            <FadeIn key="memo">
              <View style={st.paperwrap}>
                <PaperBox bg={pc.bg} accent={pc.accent} radius={22} cut={28} style={st.paper}>
                  <Pressable onPress={startEdit} disabled={editing} accessibilityRole="button" accessibilityLabel={editing ? undefined : '눌러서 수정'}>
                    <MemoEditor key={editorKey} variant="app" value={editing ? draft : joined} onChangeText={setDraft} editable={editing} focusRef={ed} />
                  </Pressable>
                </PaperBox>
                {m.pinned ? <AppTape color={pc.accent} /> : null}
              </View>
              <Text style={st.ecap}>{editing ? '편집 중 · 완료를 누르면 저장돼요' : '글을 누르면 바로 수정할 수 있어요'}</Text>
            </FadeIn>
          ) : (
            <FadeIn key={aiReady ? 'ai' : 'sk'}>
              {aiReady ? (
                <AppAiTab memo={m} versions={p.versions} feed={p.feed} trackItems={p.trackItems} lastChecked={p.lastChecked} openLatestRev={histSignal} onToggleAi={toggleAi} onOpenSource={p.onOpenSource} onOpenEvidence={p.onOpenEvidence} onNudge={p.onNudge} />
              ) : (
                <AiTabSkeleton />
              )}
            </FadeIn>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
      <AppSnackbar visible={!!snack} message={snack?.msg ?? ''} style={[st.snack, { bottom: 16 + insets.bottom }]} />
      <MemoMoreSheet open={more} title={m.title} color={m.color} pinned={m.pinned} aiLinked={m.ai_linked} onColor={p.onChangeColor} onAction={onMore} onClose={() => setMore(false)} />
      <AiOffSheet
        open={off}
        stockName={p.stockName}
        title={m.title}
        itemCount={p.trackItems.length || 2}
        onClose={() => setOff(false)}
        onConfirm={() => {
          setOff(false);
          p.onDisconnectAi();
          setTimeout(() => toast('AI 연결을 해제했어요'), 380);
        }}
      />
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: appColor.surface },
  flex: { flex: 1 },
  dh: { height: 56, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 6 },
  iconbtn: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  dhT: { flex: 1, ...ft(17), fontWeight: '600', color: appColor.ink },
  done: { minHeight: 42, paddingHorizontal: 12, justifyContent: 'center' },
  doneT: { ...ft(16), fontWeight: '800', color: appColor.deepPurple },
  ddate: { textAlign: 'center', ...ft(13), color: appColor.ink2, marginBottom: 12 },
  ptabs: { marginHorizontal: 16 },
  spb: { marginTop: 10, marginHorizontal: 16 },
  dbody: { paddingTop: 16, paddingHorizontal: 16, paddingBottom: 40 },
  paperwrap: { position: 'relative' },
  paper: { minHeight: 320, paddingTop: 26, paddingHorizontal: 20, paddingBottom: 34 },
  ecap: { textAlign: 'center', ...ft(12.5), color: appColor.ink3, marginTop: 12 },
  snack: { position: 'absolute', left: 14, right: 14 },
});
