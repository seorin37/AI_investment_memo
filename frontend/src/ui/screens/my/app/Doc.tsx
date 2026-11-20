import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { LegalDocumentView } from '@/ui/screens/auth/LegalDocumentView';
import { Grp, MC, Page } from './parts';

/**
 * 앱 정보의 문서 보기 — 약관·개인정보는 ⑨-1 약관 전문(LegalDocumentView · AuthLegal)을 그대로 씀.
 * 오픈소스 라이선스는 이름 · 라이선스 · 만든 곳 목록.
 */
export function AppDoc({ title, html, oss, onBack }: { title: string; html?: string; oss?: [string, string, string][]; onBack: () => void }) {
  return (
    <Page title={title} onBack={onBack}>
      {html ? (
        <Grp style={st.doc}><LegalDocumentView html={html} variant="app" /></Grp>
      ) : (
        <Grp>
          {(oss ?? []).map(([n, l, u], i, all) => (
            <View key={n} style={[st.row, i === all.length - 1 && { borderBottomWidth: 0 }]}>
              <Text style={st.n}>{n}</Text>
              <Text style={st.l}>{l} · {u}</Text>
            </View>
          ))}
        </Grp>
      )}
    </Page>
  );
}

const st = StyleSheet.create({
  doc: { paddingVertical: 4 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, minHeight: 52, paddingHorizontal: 16, borderBottomWidth: 1, borderBottomColor: '#F1F2F4' },
  n: { flexShrink: 1, fontSize: 15, lineHeight: 22, color: MC.ink },
  l: { fontSize: 13, lineHeight: 19, color: MC.ink3 },
});
