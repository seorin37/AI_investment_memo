import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { Logo } from '@/ui/icons/Icon';
import { IntroArtwork } from '@/ui/screens/auth/IntroArtwork';
import type { IntroProps } from '@/ui/screens/auth/Auth.types';
import { fpx, webTracking } from '@/ui/theme';

import { useIntroKeyboard } from './authKeyboard.web';

export function WebIntro({ pages, page, onPageChange, onDone }: IntroProps) {
  const current = pages[page];
  const last = page === pages.length - 1;
  useIntroKeyboard(page, pages.length, onPageChange);
  return (
    <View style={st.screen}>
      <View style={st.card}>
        <View style={st.header}>
          <Logo kind="web" size={102} height={34} color="#111111" />
          <View style={st.headerRight}>
            <View style={st.dots} accessibilityLabel={`${pages.length}장 중 ${page + 1}장`}>
              {pages.map((item, i) => <View key={item.key} style={[st.dot, i === page && st.dotOn]} />)}
            </View>
            <Pressable onPress={onDone} accessibilityRole="button"><Text style={st.skip}>건너뛰기</Text></Pressable>
          </View>
        </View>
        <View key={current.key} style={st.pane}>
          <View style={st.art}><IntroArtwork page={current.key} compact={false} /></View>
          <Text style={st.title}>{current.title}</Text>
          <Text style={st.description}>{current.description}</Text>
        </View>
        <View style={st.actions}>
          {page > 0 ? <Pressable onPress={() => onPageChange(page - 1)} style={({ hovered }: { hovered?: boolean }) => [st.prev, hovered && st.prevHover]}><Text style={st.prevText}>이전</Text></Pressable> : null}
          <Pressable onPress={() => last ? onDone() : onPageChange(page + 1)} style={({ hovered }: { hovered?: boolean }) => [st.next, hovered && st.nextHover]}>
            <Text style={st.nextText}>{last ? '시작하기' : '다음'}</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  screen: { flex: 1, minHeight: 600, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FDFDFD', paddingVertical: 32 },
  card: { width: 640, maxWidth: '100%', borderRadius: 24, borderWidth: 1, borderColor: '#E5E8EB', backgroundColor: '#FFFFFF', paddingHorizontal: 56, paddingTop: 24, paddingBottom: 32 },
  header: { height: 42, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 22 },
  dots: { height: 6, flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D5D8DD' },
  dotOn: { width: 18, backgroundColor: '#111111' },
  skip: { ...fpx(15, 23), color: '#667085', letterSpacing: webTracking(15) },
  pane: { marginTop: 20, height: 404 },
  art: { height: 236, overflow: 'hidden', borderRadius: 20, backgroundColor: '#F4F5F7' },
  title: { ...fpx(30, 40), marginTop: 28, color: '#18181C', fontWeight: '700', letterSpacing: webTracking(30) },
  description: { ...fpx(15, 23), marginTop: 8, color: '#8B919C', letterSpacing: webTracking(15) },
  actions: { marginTop: 24, flexDirection: 'row', gap: 8 },
  prev: { width: 96, minHeight: 56, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F2F2F5' },
  prevHover: { backgroundColor: '#E8E8EC' },
  prevText: { ...fpx(17, 26), color: '#18181C', fontWeight: '700' },
  next: { minHeight: 56, flex: 1, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: '#111111' },
  nextHover: { backgroundColor: '#2A2A2A' },
  nextText: { ...fpx(17, 26), color: '#FFFFFF', fontWeight: '700' },
});
