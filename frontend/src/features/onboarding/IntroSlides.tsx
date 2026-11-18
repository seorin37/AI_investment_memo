/**
 * 서비스 소개 3장 (로그인 전) — 옆으로 밀어 넘기기(ScrollView paging) · 점 · [이전] [다음/시작하기] · [건너뛰기].
 * 체험판 login.html 소개 — 움직임 (Lucian #042):
 *  - [다음]/[이전]: 새 장의 그림 · 제목 · 본문이 나아가는 방향으로 폭의 40% 에서 밀려 들어옴 (.55s · 투명도 .35s)
 *  - 손가락으로 넘길 때는 기본 가로 넘기기 위에 같은 방향으로 살짝 더 밀려 들어옴
 *  - 현재 점이 18px 로 늘어남 · 버튼 누름 spring
 * 이 화면은 상단 바·탭바가 없음 (안전 영역은 직접 처리).
 */
import { useRef, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, View, useWindowDimensions, type NativeScrollEvent, type NativeSyntheticEvent, type ScrollViewInstance } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MobileIcon } from '@/components/icons/MobileIcons';
import { Appear } from '@/components/motion/Appear';
import { SPRING, useTweenNumber } from '@/components/motion/motion';
import { usePressScale } from '@/components/motion/StateMotion';
import type { IntroSlide, IntroSlidesProps } from '@/features/onboarding/IntroSlides.types';

const C = {
  bg: '#FFFFFF',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  accent: '#8569E3',
  accentDeep: '#6A42AB',
  accentSoft: '#EEE9FB',
  dot: '#D5D8DD',
  white: '#FFFFFF',
  gray: '#F2F2F5',
  memo: '#FCEAAA',
  card: '#F6F7F9',
  tagDisc: '#FFE9E9', tagDiscText: '#B42318',
  tagNews: '#E4ECFF', tagNewsText: '#2F6BDB',
  tagRep: '#EEE8FF', tagRepText: '#7046F5',
  tagPrice: '#E3F5EA', tagPriceText: '#1B7A45',
  audio: '#DCE7FF', audioText: '#3D73F0',
  report: '#FFE1E1', reportText: '#E5484D',
} as const;
const PAD = 24;

export function IntroSlides({ slides, onDone }: IntroSlidesProps) {
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const ref = useRef<ScrollViewInstance>(null);
  const [page, setPage] = useState(0);
  /** 넘어간 방향과 거리 (버튼 = 폭의 40% · 손가락 = 40px) */
  const [push, setPush] = useState({ dx: 0, n: 0 });
  const last = page === slides.length - 1;
  const go = (i: number) => {
    ref.current?.scrollTo({ x: i * width, animated: false });
    setPush((p) => ({ dx: (i > page ? 1 : -1) * width * 0.4, n: p.n + 1 }));
    setPage(i);
  };
  const onEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const i = Math.round(e.nativeEvent.contentOffset.x / width);
    if (i === page) return;
    setPush((p) => ({ dx: (i > page ? 1 : -1) * 40, n: p.n + 1 }));
    setPage(i);
  };

  return (
    <View style={[st.root, { paddingTop: insets.top, paddingBottom: insets.bottom + 12 }]}>
      <View style={st.top}>
        <Pressable style={st.skip} onPress={onDone} accessibilityRole="button"><Text style={st.skipText}>건너뛰기</Text></Pressable>
      </View>
      <ScrollView ref={ref} horizontal pagingEnabled showsHorizontalScrollIndicator={false} onMomentumScrollEnd={onEnd} style={st.flex}>
        {slides.map((s, i) => (
          <View key={s.key} style={[st.page, { width }]}>
            <Appear kind="step" dx={i === page ? push.dx || 0.001 : 0.001} replay={i === page ? push.n : -1} style={st.pageIn}>
              <View style={st.art}><Art k={s.key} /></View>
              <Text style={st.title}>{s.title}</Text>
              <Text style={st.body}>{s.body}</Text>
            </Appear>
          </View>
        ))}
      </ScrollView>
      <View style={st.dots}>
        {slides.map((s, i) => <Dot key={s.key} on={i === page} />)}
      </View>
      <View style={st.btns}>
        {page > 0 && <Btn label="이전" gray onPress={() => go(page - 1)} />}
        <Btn label={last ? '시작하기' : '다음'} onPress={() => (last ? onDone() : go(page + 1))} />
      </View>
    </View>
  );
}

function Dot({ on }: { on: boolean }) {
  const w = useTweenNumber(on ? 18 : 6, 300, SPRING);
  return <View style={[st.dot, { width: w }, on && st.dotOn]} />;
}

function Btn({ label, gray, onPress }: { label: string; gray?: boolean; onPress: () => void }) {
  const p = usePressScale(0.96);
  return (
    <Pressable style={gray ? st.hitPrev : st.hitNext} onPress={onPress} onPressIn={p.onPressIn} onPressOut={p.onPressOut} accessibilityRole="button">
      <Animated.View style={[st.btn, gray ? st.prev : st.next, { transform: [{ scale: p.scale }] }]}>
        <Text style={gray ? st.prevText : st.nextText}>{label}</Text>
      </Animated.View>
    </Pressable>
  );
}

function Tag({ label, bg, fg }: { label: string; bg: string; fg: string }) {
  return <View style={[st.tag, { backgroundColor: bg }]}><Text style={[st.tagText, { color: fg }]}>{label}</Text></View>;
}

function Art({ k }: { k: IntroSlide['key'] }) {
  if (k === 'flood') {
    const T = [['공시', C.tagDisc, C.tagDiscText], ['뉴스', C.tagNews, C.tagNewsText], ['리포트', C.tagRep, C.tagRepText], ['주가', C.tagPrice, C.tagPriceText]] as const;
    return (
      <View style={st.flood}>
        {Array.from({ length: 16 }, (_, i) => T[i % 4]).map(([l, b, f], i) => <Tag key={i} label={l} bg={b} fg={f} />)}
      </View>
    );
  }
  if (k === 'memo') {
    return (
      <View style={st.memoArt}>
        <View style={st.memoPaper}><Text style={st.memoTag}>내 메모</Text><Text style={st.memoText}>HBM 수요 계속 갈까?</Text></View>
        <View style={st.att}><Tag label="뉴스" bg={C.tagNews} fg={C.tagNewsText} /><Text style={st.attText} numberOfLines={1}>HBM4 공급 확대 소식이 나왔어요</Text></View>
        <View style={st.att}><Tag label="공시" bg={C.tagDisc} fg={C.tagDiscText} /><Text style={st.attText} numberOfLines={1}>3분기 실적 발표가 예정돼 있어요</Text></View>
        <Text style={st.attNote}>AI가 찾아 붙임</Text>
      </View>
    );
  }
  return (
    <View style={st.listenArt}>
      <View style={st.lCard}><View style={[st.lIc, { backgroundColor: C.audio }]}><MobileIcon name="audio" size={20} color={C.audioText} /></View><Text style={st.lTag}>AI 오디오</Text><Text style={st.lTitle}>내 종목 라디오</Text></View>
      <View style={st.lCard}><View style={[st.lIc, { backgroundColor: C.report }]}><MobileIcon name="report" size={20} color={C.reportText} /></View><Text style={st.lTag}>AI 주간보고서</Text><Text style={st.lTitle}>한 주를 한 장으로</Text></View>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  flex: { flex: 1 },
  top: { height: 52, alignItems: 'flex-end', justifyContent: 'center', paddingHorizontal: 10 },
  skip: { minHeight: 44, minWidth: 44, paddingHorizontal: 10, justifyContent: 'center' },
  skipText: { fontSize: 15, color: C.sub },
  page: { paddingHorizontal: PAD, justifyContent: 'center' },
  art: { height: 260, alignItems: 'center', justifyContent: 'center', marginBottom: 28 },
  title: { fontSize: 25, fontWeight: '800', color: C.text, lineHeight: 34 },
  body: { fontSize: 15.5, lineHeight: 24, color: C.sub, marginTop: 12 },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 6, marginVertical: 16 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: C.dot },
  dotOn: { backgroundColor: C.accentDeep },
  btns: { flexDirection: 'row', gap: 8, paddingHorizontal: PAD - 8 },
  btn: { height: 54, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  pageIn: { justifyContent: 'center' },
  hitPrev: { width: 96 },
  hitNext: { flex: 1 },
  prev: { backgroundColor: C.gray },
  prevText: { fontSize: 16, fontWeight: '700', color: C.text },
  next: { backgroundColor: C.accent },
  nextText: { fontSize: 16, fontWeight: '800', color: C.white },
  tag: { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5 },
  tagText: { fontSize: 13, fontWeight: '800' },
  flood: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 8, maxWidth: 300, opacity: 0.9 },
  memoArt: { width: '100%', maxWidth: 320, gap: 8 },
  memoPaper: { backgroundColor: C.memo, borderRadius: 16, padding: 16 },
  memoTag: { fontSize: 12, fontWeight: '700', color: C.sub },
  memoText: { fontSize: 17, fontWeight: '800', color: C.text, marginTop: 4 },
  att: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: C.card, borderRadius: 12, padding: 10 },
  attText: { flex: 1, fontSize: 13.5, fontWeight: '600', color: C.text },
  attNote: { fontSize: 12, color: C.muted, textAlign: 'right' },
  listenArt: { flexDirection: 'row', gap: 12 },
  lCard: { width: 140, backgroundColor: C.card, borderRadius: 18, padding: 14, gap: 6 },
  lIc: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  lTag: { fontSize: 12, color: C.sub },
  lTitle: { fontSize: 15, fontWeight: '800', color: C.text },
});
