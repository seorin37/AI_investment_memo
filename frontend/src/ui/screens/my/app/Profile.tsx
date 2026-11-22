import React, { useEffect, useState } from 'react';
import { BackHandler, KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Text, TextInput } from '@/components/ui/AppText';
import type { AuthProvider } from '@/types/models';
import { Avatar } from '@/ui/shared/Avatar';
import type { ProfileProps } from '../My.types';
import { ConfirmSheet, Grp, Head, Item, Lb, MC, Rv } from './parts';

/**
 * 앱 내 프로필 = 원본 app/my.html openProfile()
 * 큰 아바타 84 + [사진 변경] [삭제] · 이름 / 한 줄 소개 입력 · 연결된 로그인(카카오 사용 중 · 네이버·구글 [연결]) · 로그아웃 · 회원 탈퇴(빨강)
 * 로그아웃은 아래 확인 시트 ('로그아웃할까요?')
 */
const PROV: [AuthProvider, string][] = [['kakao', '카카오'], ['naver', '네이버'], ['google', '구글']];

export function AppProfile(p: ProfileProps) {
  const insets = useSafeAreaInsets();
  const [name, setName] = useState(p.profile.name);
  const [intro, setIntro] = useState(p.profile.intro);
  const [linked, setLinked] = useState<AuthProvider[]>([p.profile.provider]);
  const [ask, setAsk] = useState(false);
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (ask) setAsk(false);
      else p.onBack();
      return true;
    });
    return () => sub.remove();
  }, [ask, p]);
  const commit = () => {
    const n = name.trim();
    if (!n) setName(p.profile.name);
    p.onChange({ name: n, intro: intro.trim() });
  };
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Head title="내 프로필" onBack={p.onBack} />
      <KeyboardAvoidingView style={st.flex} behavior="padding">
        <ScrollView contentContainerStyle={[st.w, { paddingBottom: 28 + insets.bottom }]} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          <Rv i={0}>
            <Grp style={st.top}>
              <Avatar name={name.trim() || p.profile.name} photoUrl={p.profile.photoUrl} size={84} variant="app" boxStyle={st.avbig} textStyle={st.avbigT} />
              <View style={st.pbtn}>
                <Pressable onPress={p.onPhoto} style={({ pressed }) => [st.pb, pressed && { backgroundColor: '#F7F7F9' }]} accessibilityRole="button"><Text style={st.pbT}>사진 변경</Text></Pressable>
                <Pressable onPress={p.onPhotoDelete} style={({ pressed }) => [st.pb, pressed && { backgroundColor: '#F7F7F9' }]} accessibilityRole="button"><Text style={st.pbT}>삭제</Text></Pressable>
              </View>
            </Grp>
          </Rv>
          <Rv i={1}>
            <Grp style={st.fields}>
              <Text style={[st.fl, { marginTop: 0 }]}>이름</Text>
              <TextInput value={name} onChangeText={setName} onBlur={commit} maxLength={20} returnKeyType="done" style={st.inp} accessibilityLabel="이름" selectionColor={MC.a2} cursorColor={MC.a2} />
              <Text style={st.fl}>한 줄 소개</Text>
              <TextInput value={intro} onChangeText={setIntro} onBlur={commit} maxLength={20} returnKeyType="done" style={st.inp} accessibilityLabel="한 줄 소개" selectionColor={MC.a2} cursorColor={MC.a2} />
            </Grp>
          </Rv>
          <Rv i={2}><Lb>연결된 로그인 · 연결한 계정으로 memo&apos;s에 로그인할 수 있어요</Lb></Rv>
          <Rv i={3}>
            <Grp>
              {PROV.map(([k, label], i) => {
                const cur = k === p.profile.provider;
                const on = linked.includes(k);
                return (
                  <Item
                    key={k}
                    two
                    last={i === PROV.length - 1}
                    title={label}
                    sub={cur ? `${p.profile.email} · 현재 로그인 중` : on ? '연결됨' : '연결되지 않음'}
                    right={
                      cur || on ? (
                        <Text style={st.lnkOn}>{cur ? '사용 중' : '연결됨'}</Text>
                      ) : (
                        <Pressable onPress={() => { setLinked((l) => [...l, k]); p.onLink(k); }} style={({ pressed }) => [st.lnk, pressed && { backgroundColor: '#F7F7F9' }]} accessibilityRole="button" accessibilityLabel={`${label} 연결`}>
                          <Text style={st.lnkT}>연결</Text>
                        </Pressable>
                      )
                    }
                  />
                );
              })}
            </Grp>
          </Rv>
          <Rv i={4}>
            <Grp style={{ marginTop: 10 }}>
              <Item two title="로그아웃" sub="이 기기에서 로그아웃해요" onPress={() => setAsk(true)} />
              <Item two red last title="회원 탈퇴" sub="모든 메모와 기록이 삭제돼요. 확인 창을 한 번 더 거쳐요." onPress={p.onWithdraw} />
            </Grp>
          </Rv>
        </ScrollView>
      </KeyboardAvoidingView>
      <ConfirmSheet
        open={ask}
        title="로그아웃할까요?"
        body="이 기기에서만 로그아웃돼요. 메모와 기록은 그대로 남아 있어요."
        ok="로그아웃"
        onCancel={() => setAsk(false)}
        onOk={() => { setAsk(false); p.onLogout(); }}
      />
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: MC.bg },
  flex: { flex: 1 },
  w: { paddingHorizontal: 16 },
  top: { padding: 20 },
  avbig: { width: 84, height: 84, borderRadius: 42, backgroundColor: MC.aSoft, alignItems: 'center', justifyContent: 'center', alignSelf: 'center', marginBottom: 14 },
  avbigT: { fontSize: 30, lineHeight: 38, fontWeight: '800', color: MC.a2 },
  pbtn: { flexDirection: 'row', gap: 8, justifyContent: 'center' },
  pb: { borderWidth: 1, borderColor: '#E2E4E8', backgroundColor: '#FFFFFF', borderRadius: 12, paddingVertical: 9, paddingHorizontal: 14, minHeight: 40, justifyContent: 'center' },
  pbT: { fontSize: 13.5, lineHeight: 20, fontWeight: '700', color: MC.ink },
  fields: { marginTop: 10, paddingVertical: 14, paddingHorizontal: 16 },
  fl: { fontSize: 12.5, lineHeight: 18, color: MC.ink3, marginTop: 12, marginBottom: 6 },
  inp: { borderWidth: 1, borderColor: '#E2E4E8', borderRadius: 14, paddingVertical: 13, paddingHorizontal: 14, fontSize: 15, lineHeight: 21, color: MC.ink, backgroundColor: '#FFFFFF' },
  lnk: { borderWidth: 1, borderColor: '#E2E4E8', borderRadius: 10, paddingVertical: 6, paddingHorizontal: 12, minHeight: 32, justifyContent: 'center' },
  lnkT: { fontSize: 12.5, lineHeight: 18, fontWeight: '700', color: MC.ink },
  lnkOn: { fontSize: 12.5, lineHeight: 18, fontWeight: '700', color: MC.a2, paddingHorizontal: 12 },
});
