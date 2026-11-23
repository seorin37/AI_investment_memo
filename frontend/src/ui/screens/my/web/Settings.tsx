import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text, TextInput } from '@/components/ui/AppText';
import type { AuthProvider } from '@/types/models';
import { GoogleGlyph, KakaoGlyph, NaverGlyph } from '@/ui/screens/auth/AuthGlyphs';
import { Avatar } from '@/ui/shared/Avatar';
import { ConfirmDialog } from '@/ui/shared/ConfirmDialog';
import { DARK_SUPPORTED } from '@/ui/shared/Dark';
import { Sheet } from '@/ui/shared/Sheet';
import { SkySwitch } from '@/ui/shared/SkySwitch';
import { WITHDRAW_REASONS, type InfoDoc, type MyProfile, type WithdrawProps } from '../My.types';
import { SBtn } from './parts';
import { DataTab, DocModal, InfoTab, NotiTab, PlanBar, PlanView, UsageTab, type WebSettingsExtra } from './SettingsTabs';

/**
 * 웹 설정 창 = 원본 web/src/screens/overlays.tsx Settings (1040×780 가운데 · 막 rgba(0,0,0,.32) · 라운드 20)
 * 왼쪽 250 (아바타 36 · 이름 · '설정' / 계정: 내 프로필·알림 / 서비스: 사용량 / 기타: 데이터·정보) · 오른쪽 790 (머리 112 · 본문 36/24)
 * ⑨-3a: 내 프로필 탭(TabProfile) · 회원 탈퇴 창(Withdraw) · 로그아웃·탈퇴 확인(ConfirmDanger). 나머지 탭 본문은 ⑨-3b.
 */
export type SettingsTab = '내 프로필' | '알림' | '사용량' | '데이터' | '정보';
const NAV: [string, SettingsTab[]][] = [['계정', ['내 프로필', '알림']], ['서비스', ['사용량']], ['기타', ['데이터', '정보']]];
const HEAD: Partial<Record<SettingsTab, string>> = { 알림: '내 메모와 연결된 새 소식을 어떻게 받을지 정해요.', 사용량: 'AI 업데이트에 쓰인 사용량을 확인해요.' };
type Hover = { hovered?: boolean; pressed?: boolean };

export interface WebSettingsProps extends WebSettingsExtra {
  open: boolean;
  tab: SettingsTab;
  profile: MyProfile;
  counts: WithdrawProps['counts'];
  onTab: (t: SettingsTab) => void;
  onClose: () => void;
  onChangeProfile: (p: Pick<MyProfile, 'name' | 'intro'>) => void;
  onPhoto: () => void;
  onPhotoDelete: () => void;
  /** 다크 모드 (사이드바에서 옮겨 옴 · 내 프로필 › 로그아웃 위) */
  dark: boolean;
  onToggleDark: () => void;
  /** 확인창에서 [로그아웃] 까지 누른 뒤 */
  onLogout: () => void;
  /** 탈퇴 마지막 확인까지 누른 뒤 (mock: 실제 삭제 없음) */
  onWithdraw: (reasons: string[]) => void;
}

export function WebSettings(p: WebSettingsProps) {
  const { height } = useWindowDimensions();
  const [danger, setDanger] = useState<'logout' | 'withdraw' | 'wipe' | null>(null);
  const [wd, setWd] = useState(false);
  const [why, setWhy] = useState<string[]>([]);
  /* 사용량 › 플랜 살펴보기 (탭을 바꾸면 닫힘) · 정보 › 문서 창 */
  const [planFor, setPlanFor] = useState<SettingsTab | null>(null);
  const plan = planFor === '사용량' && p.tab === '사용량';
  const [pick, setPick] = useState(p.plan_default);
  const [doc, setDoc] = useState<InfoDoc | null>(null);
  const DANGER = {
    logout: ['로그아웃할까요?', '이 기기에서 로그아웃해요.', '로그아웃'],
    withdraw: ['정말 탈퇴할까요?', '계정과 모든 데이터가 바로 삭제되고 되돌릴 수 없어요.', '탈퇴'],
    wipe: ['모든 데이터를 삭제할까요?', '모든 메모, 기록, 종목이 영구 삭제돼요. 되돌릴 수 없어요.', '전체 삭제'],
  } as const;
  const dt = DANGER[danger ?? 'logout'];
  return (
    <Sheet open={p.open} onClose={p.onClose} width={1040} scrim="rgba(0,0,0,0.32)" label="설정">
      <View style={[st.frame, { height: Math.min(780, height - 32) }]}>
        <View style={st.nav}>
          <View style={st.me}>
            <Avatar name={p.profile.name} photoUrl={p.profile.photoUrl} size={36} variant="web" />
            <View style={st.meText}>
              <Text style={st.meName} numberOfLines={1}>{p.profile.name}</Text>
              <Text style={st.meSub}>설정</Text>
            </View>
          </View>
          {NAV.map(([g, items]) => (
            <View key={g} style={st.navGroup}>
              <View style={st.navLabel}><Text style={st.navLabelT}>{g}</Text></View>
              {items.map((it) => {
                const on = p.tab === it;
                return (
                  <Pressable key={it} onPress={() => p.onTab(it)} accessibilityRole="tab" accessibilityState={{ selected: on }} style={({ hovered }: Hover) => [st.navItem, on ? st.navOn : hovered && st.navHover]}>
                    <NavIcon n={it} c={on ? '#6A42AB' : '#333333'} />
                    <Text style={[st.navT, on && st.navTOn]}>{it}</Text>
                  </Pressable>
                );
              })}
            </View>
          ))}
        </View>
        <View style={st.sec}>
          <View style={st.head}>
            <View style={st.headL}>
              <View style={st.titleRow}>
                {plan ? (
                  <Pressable onPress={() => setPlanFor(null)} accessibilityRole="button" accessibilityLabel="사용량으로 돌아가기" style={({ hovered }: Hover) => [st.planBack, hovered && { backgroundColor: '#F8F7F5' }]}>
                    <Svg width={20} height={20} viewBox="0 0 20 20" fill="none"><Path d="M12.5 4.5L7 10L12.5 15.5" stroke="#15171A" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" /></Svg>
                  </Pressable>
                ) : null}
                <Text style={st.title}>{plan ? '플랜 살펴보기' : p.tab}</Text>
              </View>
              {plan ? <Text style={st.sub}>필요한 만큼 AI 업데이트와 스튜디오를 쓸 수 있게 골라요. 가격·한도는 아직 정해지지 않았어요.</Text> : HEAD[p.tab] ? <Text style={st.sub}>{HEAD[p.tab]}</Text> : null}
            </View>
            <Pressable onPress={p.onClose} accessibilityRole="button" accessibilityLabel="닫기" style={({ hovered }: Hover) => [st.x, hovered && { backgroundColor: '#F8F7F5' }]}>
              <Svg width={36} height={36} viewBox="0 0 36 36" fill="none"><Path d="M13 13L23 23" stroke="#333333" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" /><Path d="M23 13L13 23" stroke="#333333" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" /></Svg>
            </Pressable>
          </View>
          <ScrollView key={p.tab + (plan ? '-plan' : '')} style={st.flex} contentContainerStyle={st.body}>
            {p.tab === '내 프로필' ? <ProfileTab {...p} onAskLogout={() => setDanger('logout')} onAskWithdraw={() => { setWhy([]); setWd(true); }} /> : null}
            {p.tab === '알림' ? <NotiTab noti={p.noti} onNoti={p.onNoti} /> : null}
            {p.tab === '사용량' && !plan ? <UsageTab usage={p.usage} tracked={p.tracked} onOpenMemo={p.onOpenMemo} onPlan={() => { setPick(p.plan_default); setPlanFor('사용량'); }} /> : null}
            {plan ? <PlanView plans={p.plans} compare={p.compare} notes={p.notes} pick={pick} setPick={setPick} /> : null}
            {p.tab === '데이터' ? <DataTab counts={p.counts} onExport={p.onExport} onAskWipe={() => setDanger('wipe')} /> : null}
            {p.tab === '정보' ? <InfoTab version={p.version} sources={p.sources} onDoc={setDoc} onFeedback={p.onFeedback} onReplayGuide={p.onReplayGuide} /> : null}
          </ScrollView>
          {plan ? <PlanBar pick={pick} free={pick === p.current_plan_key} onStart={() => p.onStartPlan(pick)} /> : null}
        </View>
      </View>
      <Withdraw open={wd} counts={p.counts} why={why} setWhy={setWhy} onClose={() => setWd(false)} onGo={() => { setWd(false); setDanger('withdraw'); }} />
      <ConfirmDialog
        variant="web"
        danger
        open={!!danger}
        title={dt[0]}
        body={dt[1]}
        confirmLabel={dt[2]}
        onCancel={() => setDanger(null)}
        onConfirm={() => {
          const d = danger;
          setDanger(null);
          if (d === 'withdraw') p.onWithdraw(why);
          else if (d === 'wipe') p.onWipe();
          else p.onLogout();
        }}
      />
      <DocModal doc={doc} docs={p.docs} oss={p.oss} onClose={() => setDoc(null)} />
    </Sheet>
  );
}

const PROV: [AuthProvider, string][] = [['google', '구글'], ['kakao', '카카오'], ['naver', '네이버']];

/* 8-3 내 프로필 (TabProfile) */
function ProfileTab(p: WebSettingsProps & { onAskLogout: () => void; onAskWithdraw: () => void }) {
  const [name, setName] = useState(p.profile.name);
  const [intro, setIntro] = useState(p.profile.intro);
  const commit = () => {
    const n = name.trim();
    if (!n) setName(p.profile.name);
    p.onChangeProfile({ name: n, intro: intro.trim() });
  };
  const field = (l: string, v: string, set: (s: string) => void) => (
    <View style={st.field}>
      <Text style={st.fieldL}>{l}</Text>
      <TextInput value={v} onChangeText={set} onBlur={commit} onSubmitEditing={commit} maxLength={20} accessibilityLabel={l} style={st.input} />
    </View>
  );
  return (
    <>
      <View style={st.photoRow}>
        <Avatar name={p.profile.name} photoUrl={p.profile.photoUrl} size={72} fontSize={26} variant="web" />
        <View style={st.photoCol}>
          <Text style={st.t15}>프로필 사진</Text>
          <View style={st.photoBtns}>
            <SBtn w={94} label="사진 변경" onPress={p.onPhoto} />
            <SBtn w={64} label="삭제" onPress={p.onPhotoDelete} />
          </View>
        </View>
      </View>
      <View style={st.fields}>{field('이름', name, setName)}{field('한 줄 소개', intro, setIntro)}</View>
      <View style={st.block}>
        <Text style={st.h16}>연결된 로그인</Text>
        <Text style={st.d14}>로그인한 소셜 계정이에요. 다른 계정으로 들어오면 새 계정으로 시작해요.</Text>
        <View style={st.card}>
          {PROV.map(([k, n], i) => {
            const cur = p.profile.provider === k;
            return (
              <React.Fragment key={k}>
                {i > 0 ? <View style={st.hr} /> : null}
                <View style={st.lrow}>
                  <View style={[st.badge, k === 'google' ? st.bGoogle : k === 'kakao' ? st.bKakao : st.bNaver]}>
                    {k === 'google' ? <GoogleGlyph size={20} /> : k === 'kakao' ? <KakaoGlyph size={20} /> : <NaverGlyph size={16} />}
                  </View>
                  <View style={{ width: 534, gap: 4 }}>
                    <Text style={st.t15}>{n}</Text>
                    <Text style={st.lsub} numberOfLines={1}>{cur ? `${p.profile.email} · 현재 로그인 중` : '연결되지 않음'}</Text>
                  </View>
                  <Text style={[st.lsub, { color: cur ? '#15171A' : '#C0C4CC' }]}>{cur ? '사용 중' : '—'}</Text>
                </View>
              </React.Fragment>
            );
          })}
        </View>
      </View>
      <View style={st.hr} />
      {DARK_SUPPORTED ? (
        <>
          <View style={st.row}>
            <View style={[st.rowText, { width: 598 }]}>
              <Text style={st.t15}>다크 모드</Text>
              <Text style={st.d14}>화면을 어둡게 바꿔요.</Text>
            </View>
            <View style={st.darkSw}><SkySwitch on={p.dark} onToggle={p.onToggleDark} width={48} /></View>
          </View>
          <View style={st.hr} />
        </>
      ) : null}
      <View style={st.row}>
        <View style={[st.rowText, { width: 598 }]}>
          <Text style={st.t15}>로그아웃</Text>
          <Text style={st.d14}>이 기기에서 로그아웃해요.</Text>
        </View>
        <SBtn w={96} label="로그아웃" onPress={p.onAskLogout} />
      </View>
      <View style={st.card}>
        <View style={st.row2}>
          <View style={[st.rowText, { flex: 1 }]}>
            <Text style={st.t15}>회원 탈퇴</Text>
            <Text style={st.d14}>탈퇴하면 모든 메모와 기록이 삭제되며 되돌릴 수 없어요.</Text>
          </View>
          <SBtn w={100} red label="회원 탈퇴" onPress={p.onAskWithdraw} />
        </View>
      </View>
    </>
  );
}

/* 회원 탈퇴 창 (680 · 라운드 28 · 지워지는 것 4칸 → 떠나는 이유(선택) → 동의 체크 → 빨간 버튼 → 한 번 더 확인) */
function Withdraw({ open, counts, why, setWhy, onClose, onGo }: { open: boolean; counts: WithdrawProps['counts']; why: string[]; setWhy: (f: (w: string[]) => string[]) => void; onClose: () => void; onGo: () => void }) {
  const [ok, setOk] = useState(false);
  const [prev, setPrev] = useState(open);
  if (open !== prev) {
    setPrev(open);
    if (open) setOk(false);
  }
  const stats: [string, number][] = [['메모', counts.memo], ['투자 기록', counts.journal], ['내 종목', counts.stock], ['AI 연결', counts.ai]];
  return (
    <Sheet open={open} onClose={onClose} width={680} label="회원 탈퇴">
      <View style={st.wd}>
        <View style={{ gap: 4 }}>
          <Text style={st.wdT}>탈퇴하면 되돌릴 수 없어요</Text>
          <Text style={st.wdS}>계정과 함께 아래 내용이 모두 삭제돼요.</Text>
        </View>
        <View style={st.stats}>
          {stats.map(([l, n]) => (
            <View key={l} style={st.stat}><Text style={st.statL}>{l}</Text><Text style={st.statV}>{n}개</Text></View>
          ))}
        </View>
        <View style={{ gap: 8 }}>
          <Text style={st.why}>떠나는 이유 <Text style={st.whyOpt}>(선택)</Text></Text>
          <View style={st.chips}>
            {WITHDRAW_REASONS.map((r) => {
              const on = why.includes(r);
              return (
                <Pressable key={r} onPress={() => setWhy((w) => (on ? w.filter((x) => x !== r) : [...w, r]))} accessibilityRole="button" accessibilityState={{ selected: on }} style={({ hovered }: Hover) => [st.chip, on ? st.chipOn : hovered && { backgroundColor: '#F9F9F9' }]}>
                  <Text style={[st.chipT, on && { color: '#FFFFFF' }]}>{r}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>
        <Pressable onPress={() => setOk(!ok)} accessibilityRole="checkbox" accessibilityState={{ checked: ok }} style={st.agree}>
          <View style={[st.cb, ok && st.cbOn]}>
            {ok ? <Svg width={12} height={12} viewBox="0 0 12 12" fill="none"><Path d="M2.5 6L4.8 8.3L9.5 3.5" stroke="#FFFFFF" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" /></Svg> : null}
          </View>
          <Text style={st.agreeT}>안내를 모두 확인했고, 탈퇴에 동의해요</Text>
        </Pressable>
        <View style={st.wdBtns}>
          <Pressable onPress={onClose} accessibilityRole="button" style={[st.wdBtn, { backgroundColor: '#F2F3F4', paddingHorizontal: 20 }]}><Text style={st.wdBtnT}>취소</Text></Pressable>
          <Pressable disabled={!ok} onPress={onGo} accessibilityRole="button" style={[st.wdBtn, { paddingHorizontal: 24, backgroundColor: ok ? '#E45D6A' : '#C9CCD2' }]}><Text style={[st.wdBtnT, { color: '#FFFFFF' }]}>탈퇴하기</Text></Pressable>
        </View>
      </View>
    </Sheet>
  );
}

function NavIcon({ n, c }: { n: SettingsTab; c: string }) {
  const s = { stroke: c, strokeWidth: 1.42222, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return (
    <Svg width={18} height={18} viewBox="0 0 18 18" fill="none">
      {n === '내 프로필' ? (
        <>
          <Path d="M10.7731 5.96384L10.8442 5.33273L10.7731 4.70161L10.5597 4.09717L10.2219 3.55495L9.7775 3.1105L9.23527 2.77273L8.63083 2.55939L7.99972 2.48828L7.36861 2.55939L6.76416 2.77273L6.22194 3.1105L5.7775 3.55495L5.43972 4.09717L5.22638 4.70161L5.15527 5.33273L5.22638 5.96384L5.43972 6.56828L5.7775 7.1105L6.22194 7.55495L6.76416 7.89273L7.36861 8.10606L7.99972 8.17717L8.63083 8.10606L9.23527 7.89273L9.7775 7.55495L10.2219 7.1105L10.5597 6.56828L10.7731 5.96384Z" {...s} />
          <Path d="M2.66699 13.7784C2.66699 10.8155 4.44477 9.33398 8.00033 9.33398C11.5559 9.33398 13.3337 10.8155 13.3337 13.7784" {...s} />
        </>
      ) : n === '알림' ? (
        <>
          <Path d="M4.44455 10.6667L3.55566 12H12.4446L11.5557 10.6667V7.11111C11.5557 5.03704 10.3705 4 8.00011 4C5.62974 4 4.44455 5.03704 4.44455 7.11111V10.6667Z" {...s} />
          <Path d="M6.66699 13.7773C7.55588 14.6662 8.44477 14.6662 9.33366 13.7773" {...s} />
        </>
      ) : n === '사용량' ? (
        <Path d="M3 14V10M9 14V4M15 14V7" stroke={c} strokeWidth={1.5} strokeLinecap="round" />
      ) : n === '데이터' ? (
        <>
          <Path d="M13.3337 3.11068C9.7781 1.3329 6.22255 1.3329 2.66699 3.11068V10.2218C6.22255 11.9996 9.7781 11.9996 13.3337 10.2218V3.11068Z" {...s} />
          <Path d="M2.66699 8C6.22255 9.77778 9.7781 9.77778 13.3337 8" {...s} />
        </>
      ) : (
        <>
          <Path d="M14.0618 9.38623L14.2218 7.99957L14.0618 6.6129L13.6085 5.29734L12.8618 4.12401L11.8751 3.13734L10.7018 2.39068L9.38623 1.93734L7.99957 1.77734L6.6129 1.93734L5.29734 2.39068L4.12401 3.13734L3.13734 4.12401L2.39068 5.29734L1.93734 6.6129L1.77734 7.99957L1.93734 9.38623L2.39068 10.7018L3.13734 11.8751L4.12401 12.8618L5.29734 13.6085L6.6129 14.0618L7.99957 14.2218L9.38623 14.0618L10.7018 13.6085L11.8751 12.8618L12.8618 11.8751L13.6085 10.7018L14.0618 9.38623Z" {...s} />
          <Path d="M8 7.28906V11.378" {...s} />
          <Path d="M8 4.97852V5.15629" {...s} />
        </>
      )}
    </Svg>
  );
}

const st = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  frame: { width: 1040, maxWidth: '100%', flexDirection: 'row', overflow: 'hidden', borderRadius: 20, backgroundColor: '#FFFFFF', shadowColor: '#1C2940', shadowOpacity: 0.08, shadowRadius: 32, shadowOffset: { width: 0, height: 12 }, elevation: 10 },
  nav: { width: 250, borderRightWidth: 1, borderRightColor: '#E5E3E8', paddingHorizontal: 16, paddingVertical: 24, gap: 20 },
  me: { height: 52, flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 12 },
  meText: { width: 146, gap: 4 },
  meName: { fontSize: 17, lineHeight: 26, fontWeight: '500', color: '#15171A' },
  meSub: { fontSize: 14, lineHeight: 21, fontWeight: '500', color: '#8E8A97' },
  navGroup: { width: 218, gap: 4 },
  navLabel: { height: 26, paddingHorizontal: 12 },
  navLabelT: { fontSize: 14, lineHeight: 21, fontWeight: '500', color: '#8E8A97' },
  navItem: { height: 42, width: 218, flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8 },
  navOn: { backgroundColor: '#FBF8FF' },
  navHover: { backgroundColor: '#F9F9F9' },
  navT: { fontSize: 15, lineHeight: 21, color: '#15171A' },
  navTOn: { fontWeight: '700', lineHeight: 20, color: '#6A42AB' },
  sec: { flex: 1, minWidth: 0 },
  head: { height: 112, flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', paddingHorizontal: 36, paddingVertical: 28 },
  headL: { width: 620, gap: 8 },
  titleRow: { height: 34, flexDirection: 'row', alignItems: 'center', gap: 8 },
  planBack: { marginLeft: -8, width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 26, lineHeight: 35, fontWeight: '700', color: '#15171A' },
  sub: { fontSize: 15, lineHeight: 23, color: '#8E8A97' },
  x: { width: 36, height: 36, borderRadius: 8 },
  body: { paddingHorizontal: 36, paddingVertical: 24, gap: 24 },
  photoRow: { height: 72, flexDirection: 'row', alignItems: 'center', gap: 20 },
  photoCol: { width: 300, gap: 12 },
  photoBtns: { flexDirection: 'row', gap: 8 },
  t15: { fontSize: 17, lineHeight: 26, fontWeight: '500', color: '#15171A' },
  d14: { fontSize: 15, lineHeight: 23, color: '#8E8A97' },
  h16: { fontSize: 20, lineHeight: 29, fontWeight: '700', color: '#15171A' },
  fields: { flexDirection: 'row', gap: 16 },
  field: { width: 351, gap: 8 },
  fieldL: { fontSize: 14, lineHeight: 21, fontWeight: '500', color: '#8E8A97' },
  input: { height: 42, width: 351, borderRadius: 8, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, lineHeight: 23, color: '#15171A' },
  block: { width: 718, gap: 20 },
  card: { width: 718, borderRadius: 12, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', padding: 20, gap: 20 },
  hr: { height: 1, alignSelf: 'stretch', backgroundColor: '#E5E3E8' },
  lrow: { height: 48, flexDirection: 'row', alignItems: 'center', gap: 12 },
  badge: { width: 36, height: 36, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  bGoogle: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E8ECF3' },
  bKakao: { backgroundColor: '#FEE500' },
  bNaver: { backgroundColor: '#03A94D' },
  lsub: { fontSize: 14, lineHeight: 21, fontWeight: '500', color: '#8E8A97' },
  row: { width: 718, flexDirection: 'row', alignItems: 'center', gap: 24 },
  row2: { flexDirection: 'row', alignItems: 'center', gap: 24 },
  rowText: { gap: 4 },
  darkSw: { width: 96, alignItems: 'center' },
  wd: { width: 680, maxWidth: '100%', gap: 20, borderRadius: 28, backgroundColor: '#FFFFFF', paddingHorizontal: 32, paddingVertical: 28 },
  wdT: { fontSize: 22, lineHeight: 31, fontWeight: '700', color: '#15171A' },
  wdS: { fontSize: 17, lineHeight: 26, color: '#747D8D' },
  stats: { flexDirection: 'row', gap: 8 },
  stat: { flex: 1, borderRadius: 14, backgroundColor: '#F5F6F8', paddingHorizontal: 16, paddingVertical: 12 },
  statL: { fontSize: 14, lineHeight: 21, color: '#747D8D' },
  statV: { fontSize: 20, lineHeight: 28, fontWeight: '700', color: '#15171A' },
  why: { fontSize: 17, lineHeight: 26, fontWeight: '700', color: '#15171A' },
  whyOpt: { fontWeight: '500', color: '#8B95A1' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { height: 40, borderRadius: 999, paddingHorizontal: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E5E7EB' },
  chipOn: { backgroundColor: '#15171A', borderColor: '#15171A' },
  chipT: { fontSize: 15, lineHeight: 22, fontWeight: '700', color: '#575B63' },
  agree: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  cb: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.6, borderColor: '#C9CCD2', alignItems: 'center', justifyContent: 'center' },
  cbOn: { backgroundColor: '#E45D6A', borderColor: '#E45D6A' },
  agreeT: { fontSize: 17, lineHeight: 26, fontWeight: '500', color: '#15171A' },
  wdBtns: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8 },
  wdBtn: { height: 48, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  wdBtnT: { fontSize: 17, lineHeight: 26, fontWeight: '500', color: '#15171A' },
});
