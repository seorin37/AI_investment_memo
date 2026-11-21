import React from 'react';
import { View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { ft, fpx, webKindTag } from '@/ui/theme';

export type KindLabel = '공시' | '뉴스' | '주가';

/* 원본 앱 update.html .tg (.t1 공시 · .t2 뉴스 · .t3 주가): 위아래 3 · 좌우 7 · 라운드 7 · 11.5px 700 */
const APP: Record<KindLabel, { bg: string; ink: string }> = {
  공시: { bg: '#FFECEC', ink: '#D33A3A' },
  뉴스: { bg: '#E8F0FF', ink: '#2F6BDB' },
  주가: { bg: '#E4F5EA', ink: '#1B7A45' },
};

/**
 * 소식 종류 태그
 * app: 원본 update.html .tg · web: 원본 kit.tsx KindTag (높이 20 · 라운드 4 · 좌우 6 · 13px bold · red/sky/emerald-50·600·700)
 */
export function KindTag({ kind, variant }: { kind: KindLabel | string; variant: 'app' | 'web' }) {
  if (variant === 'app') {
    const c = APP[kind as KindLabel] ?? { bg: '#F1F2F4', ink: '#575B63' };
    return (
      <View style={{ alignSelf: 'flex-start', paddingVertical: 3, paddingHorizontal: 7, borderRadius: 7, backgroundColor: c.bg }}>
        <Text style={[ft(11.5), { fontWeight: '700', color: c.ink }]}>{kind}</Text>
      </View>
    );
  }
  const c = webKindTag[kind as KindLabel] ?? webKindTag.기타;
  return (
    <View style={{ alignSelf: 'flex-start', minHeight: 20, justifyContent: 'center', paddingHorizontal: 6, borderRadius: 4, backgroundColor: c.bg }}>
      <Text style={[fpx(13, 20), { fontWeight: '700', color: c.ink }]}>{kind}</Text>
    </View>
  );
}
