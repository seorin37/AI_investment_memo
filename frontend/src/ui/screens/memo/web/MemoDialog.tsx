import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { joinMemo, splitMemo } from '@/lib/memoText';
import type { MemoColor } from '@/types/models';
import { Dots } from '@/ui/icons/BoardGlyphs';
import { FadeIn } from '@/ui/motion/Reveal';
import { ContextMenu, type MenuItem } from '@/ui/shared/ContextMenu';
import { MemoEditor } from '@/ui/shared/MemoEditor';
import { Sheet } from '@/ui/shared/Sheet';
import { SpentBox } from '@/ui/shared/SpentBox';
import { fpx, paper } from '@/ui/theme';
import type { MemoDetailProps } from '../MemoDetail.types';
import { dotDate } from '../memoTimeline';
import { AI_OFF, Actions, AiFooter, CloseBtn, INK, Swatches, Tabs2, panel } from './parts';
import { WebFeed } from './WebFeed';

type Hover = { pressed: boolean; hovered?: boolean };

/**
 * 웹 메모 창 (원본 board.tsx MemoDialog: 680 가운데 창 · 막 rgba(14,15,20,.32))
 * 머리 96: '종목 · YYYY. MM. DD 작성' 13/20 #747D8D · '내 메모' 26/35 700 · ⋯ · ×
 * [메모 | AI 업데이트] · 메모: 종이 277 (라운드 16 · 안쪽 20 · 첫 줄 = 제목 편집기) + 메모 색상 / AI 업데이트: 소식 타임라인
 * AI 연결 칸 · [취소] [메모 저장]. 색·AI 연결·글은 [메모 저장] 때 한 번에 (원본과 같음). AI 연결을 새로 켜면 AI 연결 창.
 */
export function WebMemoDialog(p: MemoDetailProps & { open: boolean }) {
  const { height: H } = useWindowDimensions();
  const m = p.memo;
  const [tab, setTab] = useState<0 | 1>(p.initialTab === 'ai' ? 1 : 0);
  const [color, setColor] = useState<MemoColor>(m.color);
  const [ai, setAi] = useState(m.ai_linked);
  const [text, setText] = useState(joinMemo(m.title, m.body));
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  /* AI 연결 창에서 켜고 돌아오면 같이 켜짐 (원본 useEffect [memo.ai]) */
  const [linked, setLinked] = useState(m.ai_linked);
  if (linked !== m.ai_linked) {
    setLinked(m.ai_linked);
    setAi(m.ai_linked);
  }
  const close = () => p.onBack();
  const save = () => {
    const r = splitMemo(text);
    if (text.trim() && (r.title !== m.title || r.body !== m.body)) p.onSave(r);
    if (color !== m.color) p.onChangeColor(color);
    if (!ai && m.ai_linked) p.onDisconnectAi();
    p.onBack();
  };
  const pickTab = (i: 0 | 1) => {
    setTab(i);
    if (i === 1) p.onSeenUpdates?.();
  };
  const items: MenuItem[] = [
    { label: m.pinned ? '테이프 떼기' : '테이프 붙여 맨 위로', icon: 'pin', run: () => p.onTogglePin(!m.pinned) },
    { label: '내용 복사', icon: 'copy', run: p.onCopy },
    '-',
    { label: '휴지통으로 이동', icon: 'trash', danger: true, run: p.onDelete },
  ];
  const view = { ...m, ai_linked: ai, color };
  const tracks = p.trackItems.map((t) => t.label).join(' · ');
  return (
    <Sheet open={p.open} onClose={close} width={680} label="내 메모" scrim="rgba(14,15,20,0.32)">
      <View style={[panel.box, { maxHeight: H - 32 }]}>
        <View style={st.head}>
          <View style={st.headL}>
            <Text style={st.sub}>
              {p.stockName} · {dotDate(m.created_at)} 작성
            </Text>
            <Text style={st.title}>내 메모</Text>
          </View>
          <Pressable
            /* 창이 transform 을 가진 상자 안이라 메뉴 좌표도 창 기준: ⋯ 오른쪽 끝(680-24-32-12+4=616) - 220 · 아래 52 + 6 (원본 r.right - 220 · r.bottom + 6) */
            onPress={() => setMenu({ x: 396, y: 58 })}
            accessibilityRole="button"
            accessibilityLabel="메모 메뉴"
            style={({ hovered }: Hover) => [st.dots, hovered && { backgroundColor: '#F2F3F4' }]}
          >
            <Dots color={INK} />
          </Pressable>
          <CloseBtn onPress={close} />
        </View>
        <Tabs2 a="메모" b="AI 업데이트" v={tab} set={pickTab} />
        {tab === 0 ? (
          <View style={st.memoArea}>
            <View style={[st.paper, { backgroundColor: paper[color].bg }]}>
              <ScrollView showsVerticalScrollIndicator={false}>
                <MemoEditor key={m.id} variant="web" value={text} onChangeText={setText} editable />
              </ScrollView>
            </View>
            <Swatches v={color} set={setColor} />
          </View>
        ) : (
          <ScrollView style={st.aiArea} contentContainerStyle={st.aiIn}>
            <FadeIn style={st.aiGap}>
              {p.aiSpent && m.ai_linked ? <SpentBox variant="web" title="AI 연결이 잠시 멈췄어요" body={'이번 달 AI 사용량을 다 썼어요. 다음 달 1일에 다시 찾아요.\n메모는 계속 쓸 수 있어요.'} onCredit={() => p.onSpentAction?.('credit')} onPlan={() => p.onSpentAction?.('plan')} /> : null}
              <WebFeed memo={view} versions={p.versions} feed={p.feed} trackItems={p.trackItems} onOpenSource={p.onOpenSource} onNudge={p.onNudge} />
            </FadeIn>
          </ScrollView>
        )}
        <AiFooter
          on={ai}
          set={(v) => {
            /* 꺼진 메모를 켜면 AI 연결 창 (원본 onConnect) */
            if (v && !m.ai_linked) return p.onConnectAi();
            setAi(v);
          }}
          sub={ai ? (tab === 1 ? `이 메모를 AI가 지켜보고 있어요${tracks ? ` · ${tracks}` : ''}` : `이 메모에서 ${p.trackItems.length || 1}개 항목을 지켜봐요.`) : AI_OFF}
        />
        <Actions note="연결하지 않아도 메모는 그대로 남아요" ok="메모 저장" onCancel={close} onOk={save} />
      </View>
      <ContextMenu at={menu} items={items} onClose={() => setMenu(null)} />
    </Sheet>
  );
}

const st = StyleSheet.create({
  head: { minHeight: 96, flexDirection: 'row', alignItems: 'flex-start', gap: 12, paddingTop: 20, paddingHorizontal: 24, paddingBottom: 13 },
  headL: { flex: 1, minWidth: 0, gap: 13 },
  sub: { ...fpx(13, 20), fontWeight: '500', color: '#747D8D' },
  title: { ...fpx(26, 35), fontWeight: '700', color: INK },
  dots: { width: 32, height: 32, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginRight: -4 },
  memoArea: { height: 348, paddingTop: 8, paddingHorizontal: 24, paddingBottom: 16, gap: 13 },
  paper: { height: 277, borderRadius: 16, padding: 20 },
  aiArea: { flexShrink: 1, minHeight: 0 },
  aiIn: { paddingTop: 8, paddingHorizontal: 24, paddingBottom: 16 },
  aiGap: { gap: 16 },
});
