import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text } from '@/components/ui/AppText';
import { Logo } from '@/ui/icons/Icon';
import { IntroArtwork } from '@/ui/screens/auth/IntroArtwork';
import type { IntroProps } from '@/ui/screens/auth/Auth.types';
import { appColor, ft } from '@/ui/theme';

export function AppIntro({ pages, page, onPageChange, onDone }: IntroProps) {
  const insets = useSafeAreaInsets();
  const current = pages[page];
  const last = page === pages.length - 1;
  return (
    <View style={[st.screen, { paddingTop: Math.max(insets.top, 18), paddingBottom: Math.max(insets.bottom, 20) }]}>
      <View style={st.header}>
        <Logo kind="app" size={94} height={30} color="#16171A" />
        <View style={st.headerRight}>
          <View style={st.dots} accessibilityLabel={`${pages.length}장 중 ${page + 1}장`}>
            {pages.map((item, i) => <View key={item.key} style={[st.dot, i === page && st.dotOn]} />)}
          </View>
          <Pressable onPress={onDone} accessibilityRole="button" hitSlop={10}><Text style={st.skip}>건너뛰기</Text></Pressable>
        </View>
      </View>
      <View key={current.key} style={st.art}><IntroArtwork page={current.key} compact /></View>
      <View style={st.copy}>
        <Text style={st.title}>{current.title}</Text>
        <Text style={st.description}>{current.description}</Text>
      </View>
      <View style={st.actions}>
        {page > 0 ? (
          <Pressable onPress={() => onPageChange(page - 1)} style={st.prev} accessibilityRole="button"><Text style={st.prevText}>이전</Text></Pressable>
        ) : null}
        <Pressable onPress={() => last ? onDone() : onPageChange(page + 1)} style={st.next} accessibilityRole="button">
          <Text style={st.nextText}>{last ? '시작하기' : '다음'}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#FFFFFF', paddingHorizontal: 20 },
  header: { height: 64, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 22 },
  dots: { height: 6, flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D5D8DD' },
  dotOn: { width: 18, backgroundColor: appColor.accent },
  skip: { ...ft(15), color: '#667085' },
  art: { height: 340, overflow: 'hidden', borderRadius: 20, backgroundColor: '#F4F5F7' },
  copy: { marginTop: 27 },
  title: { ...ft(26, 1.48), color: '#18181C', fontWeight: '700' },
  description: { ...ft(15, 1.55), marginTop: 8, color: '#9AA0AA' },
  actions: { marginTop: 'auto', flexDirection: 'row', gap: 8 },
  prev: { width: 96, minHeight: 56, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F2F2F5', paddingVertical: 14 },
  prevText: { ...ft(17), color: '#18181C', fontWeight: '700' },
  next: { minHeight: 56, flex: 1, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: appColor.accent, paddingVertical: 14 },
  nextText: { ...ft(17), color: '#FFFFFF', fontWeight: '700' },
});
