import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import type { InfoProps } from '../My.types';
import { Grp, Item, Lb, MC, Page, Rv } from './parts';

/**
 * 앱 정보 = 원본 app/my.html openInfo()
 * 버전(앱 설정 값 · '최신 버전이에요') · 이용약관 · 개인정보 처리방침 · 오픈소스 라이선스 · 피드백 보내기 · 문의하기
 * 데이터 출처 · 투자 권유 아님 안내 · SIG · Saram Is Good
 */
export function AppInfo({ version, sources, onBack, onDoc, onFeedback }: InfoProps) {
  return (
    <Page title="정보" onBack={onBack}>
      <Rv i={0}>
        <Grp>
          <Item two last title="버전" sub={`memo's v${version} (베타)`} right={<Text style={st.v}>최신 버전이에요</Text>} />
        </Grp>
      </Rv>
      <Rv i={1}>
        <Grp style={{ marginTop: 10 }}>
          <Item title="이용약관" onPress={() => onDoc('terms')} />
          <Item title="개인정보 처리방침" onPress={() => onDoc('privacy')} />
          <Item title="오픈소스 라이선스" onPress={() => onDoc('oss')} />
          <Item title="피드백 보내기" onPress={onFeedback} />
          <Item title="문의하기" last onPress={onFeedback} />
        </Grp>
      </Rv>
      <Rv i={2}><Lb>데이터 출처</Lb></Rv>
      <Rv i={3}>
        <Grp style={st.src}>
          {sources.map(([k, v], i) => (
            <View key={k} style={[st.r, i === sources.length - 1 && { borderBottomWidth: 0 }]}>
              <Text style={st.rK}>{k}</Text>
              <Text keepAll style={st.rV}>{v}</Text>
            </View>
          ))}
        </Grp>
      </Rv>
      <Rv i={4}>
        <View style={st.disc}><Text keepAll style={st.discT}>memo&apos;s는 투자 권유를 하지 않으며, 제공되는 모든 정보는 참고용이에요. 투자 판단과 그 결과에 대한 책임은 투자자 본인에게 있어요.</Text></View>
      </Rv>
      <Rv i={5}><Text style={st.sig}>SIG · Saram Is Good</Text></Rv>
    </Page>
  );
}

const st = StyleSheet.create({
  v: { fontSize: 13, lineHeight: 19, color: MC.ink3 },
  src: { paddingVertical: 6, paddingHorizontal: 16 },
  r: { flexDirection: 'row', gap: 10, paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: '#F1F2F4' },
  rK: { width: 34, fontSize: 13, lineHeight: 16, color: MC.ink3 },
  rV: { flex: 1, fontSize: 14, lineHeight: 16, color: MC.ink },
  disc: { backgroundColor: '#ECEDF1', borderRadius: 16, paddingVertical: 14, paddingHorizontal: 16, marginTop: 10 },
  discT: { fontSize: 12.5, lineHeight: 20.6, color: MC.ink2 },
  sig: { textAlign: 'center', fontSize: 11.5, lineHeight: 16, color: MC.ink3, marginTop: 12 },
});
