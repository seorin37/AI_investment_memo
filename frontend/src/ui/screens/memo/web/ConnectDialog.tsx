import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { TickSmall } from '@/ui/icons/MemoGlyphs';
import { FadeIn } from '@/ui/motion/Reveal';
import { NATIVE, useMotionK } from '@/ui/motion/useMotion';
import { Sheet } from '@/ui/shared/Sheet';
import { fpx, paper } from '@/ui/theme';
import type { AiLinkProps, AiTrackItem } from '../MemoDetail.types';
import { won } from '../memoTimeline';
import { INK } from './parts';

type Hover = { pressed: boolean; hovered?: boolean };

/**
 * 웹 AI 연결 창 (원본 memox.tsx ConnectDialog: 680 · 라운드 28 · 안쪽 32·28 · 사이 20)
 * 단계 알약 (메모 확인 ✓ · 항목 확인 · 연결 시작) · 질문 22/31 · 설명 15/23 · 노란 메모 · 항목 (64 · 라운드 14)
 * 항목은 서버가 정함 (읽기 전용 — 원본의 고르기는 뺌). 분석 중 · 항목 없음 · 분석 실패 상태.
 * [일반 메모로 두기] [N개 항목으로 AI 연결]
 */
export function WebConnectDialog({ open, memo, state, items, onConfirm, onCancel, onEditMemo, onRetry }: AiLinkProps & { open: boolean }) {
  const pick = state === 'items';
  const steps = ['메모 확인', '항목 확인', '연결 시작'];
  const primary =
    state === 'items'
      ? { label: `${items.length}개 항목으로 AI 연결`, run: onConfirm, dis: false }
      : state === 'empty'
        ? { label: '메모 수정', run: () => onEditMemo?.(), dis: false }
        : state === 'error'
          ? { label: '다시 시도', run: () => onRetry?.(), dis: false }
          : { label: '항목을 찾고 있어요', run: () => {}, dis: true };
  return (
    <Sheet open={open} onClose={onCancel} width={680} label="AI 연결">
      <View style={st.box}>
        <View style={st.steps}>
          {steps.map((s, i) => {
            const on = i === 0 || (i === 1 && pick);
            return (
              <View key={s} style={st.stepRow}>
                {i > 0 ? <View style={st.sep} /> : null}
                <View style={[st.step, on ? st.stepOn : st.stepOff]}>
                  {i === 0 ? <TickSmall color="#FFFFFF" /> : null}
                  <Text style={[st.stepT, { color: on ? '#FFFFFF' : '#8B95A1' }]}>{s}</Text>
                </View>
              </View>
            );
          })}
        </View>
        <View style={st.q}>
          <Text style={st.qT}>무엇을 계속 확인할까요?</Text>
          <Text style={st.qD}>메모에서 찾은 항목이에요. 이 항목과 관련된 공시·뉴스·종가 변화만 모아 드려요.</Text>
        </View>
        <View style={[st.memo, { backgroundColor: paper.yellow.bg }]}>
          <Text style={st.memoT} numberOfLines={1}>
            {memo.title}
          </Text>
          {memo.body ? (
            <Text style={st.memoB} numberOfLines={2}>
              {memo.body.replace(/\n/g, ' ')}
            </Text>
          ) : null}
        </View>
        {state === 'loading' ? (
          <View style={st.find}>
            <PulseDot />
            <Text style={st.findT}>메모에서 계속 확인할 항목을 찾고 있어요</Text>
          </View>
        ) : state === 'items' ? (
          <FadeIn style={st.items}>
            {items.map((it, i) => (
              <View key={i} style={st.item}>
                <View style={st.check}>
                  <TickSmall color="#FFFFFF" />
                </View>
                <View style={st.flex}>
                  <Text style={st.itemT}>{it.label}</Text>
                  <Text style={st.itemD} numberOfLines={1}>
                    {detail(it)}
                  </Text>
                </View>
              </View>
            ))}
            <Text style={st.note}>AI는 메모를 고치지 않아요 · 실시간 알림이 아닌 전일 확정 종가와 정기보고서·뉴스 기준이에요</Text>
          </FadeIn>
        ) : (
          <FadeIn style={st.empty}>
            <Text style={st.emptyT}>{state === 'error' ? '메모를 확인하지 못했어요' : '추적할 항목을 찾지 못했어요'}</Text>
            <Text style={st.emptyP}>{state === 'error' ? '잠시 뒤 다시 시도해 주세요. 메모는 일반 메모로 그대로 저장돼요.' : '메모는 일반 메모로 그대로 저장돼요. 확인할 사실이나 가격 조건을 구체적으로 적고 다시 확인해 보세요.'}</Text>
            {state === 'empty' ? (
              <View style={st.exRow}>
                <Text style={st.ex}>&quot;다음 정기보고서에서 HBM 매출 확인하기&quot;</Text>
                <Text style={st.ex}>&quot;20만원 아래로 내려오면 다시 보기&quot;</Text>
              </View>
            ) : null}
          </FadeIn>
        )}
        <View style={st.btns}>
          <Pressable onPress={onCancel} accessibilityRole="button" style={({ hovered }: Hover) => [st.btn, st.btnGray, hovered && { backgroundColor: '#E9EAEC' }]}>
            <Text style={[st.btnT, { color: INK }]}>일반 메모로 두기</Text>
          </Pressable>
          <Pressable onPress={primary.run} disabled={primary.dis} accessibilityRole="button" accessibilityState={{ disabled: primary.dis }} style={[st.btn, { backgroundColor: primary.dis ? '#C9CCD2' : '#14171C' }]}>
            <Text style={st.btnT}>{primary.label}</Text>
          </Pressable>
        </View>
      </View>
    </Sheet>
  );
}

/* 항목 둘째 줄: 가격 조건은 판정 기준 · 조건 · 확인 시점, 공시·뉴스는 메모 속 문장 */
const detail = (x: AiTrackItem) => (x.kind === 'price' ? `전일 종가 · ${won(x.price)}원 ${x.direction} · 매 거래일 장 마감 후` : `메모 속 문장 · "${x.quote}"`);

/** 원본 animate-pulse 점 (8 · #15171A) */
function PulseDot() {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(1));
  useEffect(() => {
    if (k < 1) return;
    const a = Animated.loop(Animated.sequence([Animated.timing(v, { toValue: 0.5, duration: 1000, easing: Easing.bezier(0.4, 0, 0.6, 1), useNativeDriver: NATIVE }), Animated.timing(v, { toValue: 1, duration: 1000, easing: Easing.bezier(0.4, 0, 0.6, 1), useNativeDriver: NATIVE })]));
    a.start();
    return () => a.stop();
  }, [v, k]);
  return <Animated.View style={[st.pdot, { opacity: v }]} />;
}

const st = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  box: { width: 680, maxWidth: '100%', gap: 20, borderRadius: 28, backgroundColor: '#FFFFFF', paddingHorizontal: 32, paddingTop: 28, paddingBottom: 28 },
  steps: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  stepRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sep: { width: 24, height: 1, backgroundColor: '#E5E7EB' },
  step: { height: 28, flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 999, paddingHorizontal: 12 },
  stepOn: { backgroundColor: INK },
  stepOff: { backgroundColor: '#F2F3F4' },
  stepT: { ...fpx(13, 20), fontWeight: '700' },
  q: { gap: 4 },
  qT: { ...fpx(22, 31), fontWeight: '700', color: INK },
  qD: { ...fpx(15, 23), color: '#747D8D' },
  memo: { borderRadius: 16, paddingHorizontal: 20, paddingVertical: 16 },
  memoT: { ...fpx(17, 26), fontWeight: '700', color: '#16161C' },
  memoB: { ...fpx(14, 21), color: '#2E2E38' },
  find: { height: 132, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  findT: { ...fpx(15, 23), fontWeight: '500', color: '#747D8D' },
  pdot: { width: 8, height: 8, borderRadius: 4, backgroundColor: INK },
  items: { gap: 8 },
  item: { minHeight: 64, flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 14, paddingHorizontal: 16, paddingVertical: 8, backgroundColor: '#F7F7F7', borderWidth: 1.5, borderColor: '#111111' },
  check: { width: 22, height: 22, borderRadius: 11, backgroundColor: '#111111', alignItems: 'center', justifyContent: 'center' },
  itemT: { ...fpx(17, 26), fontWeight: '700', color: INK },
  itemD: { ...fpx(14, 21), color: '#747D8D' },
  note: { marginTop: 4, ...fpx(13, 20), color: '#8B95A1' },
  empty: { alignItems: 'center', gap: 8, borderRadius: 16, backgroundColor: '#F7F8FA', padding: 24 },
  emptyT: { ...fpx(17, 26), fontWeight: '700', color: INK },
  emptyP: { ...fpx(14, 21), color: '#747D8D', textAlign: 'center' },
  exRow: { gap: 6, marginTop: 4, alignItems: 'center' },
  ex: { ...fpx(13, 20), fontWeight: '700', color: '#333D4B', backgroundColor: '#FFFFFF', borderRadius: 999, paddingHorizontal: 12, paddingVertical: 4, borderWidth: 1, borderColor: '#E5E7EB', overflow: 'hidden' },
  btns: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8 },
  btn: { minHeight: 48, borderRadius: 12, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 24, paddingVertical: 12 },
  btnGray: { backgroundColor: '#F2F3F4', paddingHorizontal: 20 },
  btnT: { ...fpx(15, 23), fontWeight: '500', color: '#FFFFFF' },
});
