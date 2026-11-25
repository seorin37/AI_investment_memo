import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { Sheet } from '@/ui/shared/Sheet';
import type { CreditPack } from '../../my/My.mock';
import { CloseX } from '../../my/web/parts';

type Hover = { hovered?: boolean; pressed?: boolean };
const SCRIM = 'rgba(21,23,26,0.4)';
const Bolt = ({ s, c }: { s: number; c: string }) => <Svg width={s} height={s} viewBox="0 0 24 24" fill="none"><Path d="M13 3L5 13H11L10 21L18 11H12L13 3Z" stroke={c} strokeWidth={1.8 * 24 / s} strokeLinejoin="round" /></Svg>;
const ChevR = () => <Svg width={18} height={18} viewBox="0 0 18 18" fill="none"><Path d="M6.75 4.5L11.25 9L6.75 13.5" stroke="#9AA0AA" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" /></Svg>;

/** 원본 studio.tsx GBtn (높이 46/48 · 라운드 14 · 17 bold · dark 검정) */
export function GBtn({ children, dark, h = 46, flex, disabled, onPress }: { children: string; dark?: boolean; h?: number; flex?: boolean; disabled?: boolean; onPress: () => void }) {
  return (
    <Pressable disabled={disabled} onPress={onPress} accessibilityRole="button" style={({ hovered }: Hover) => [st.g, { height: h }, flex && { flex: 1, minWidth: 0 }, disabled ? { backgroundColor: '#E8ECF3' } : dark ? { backgroundColor: hovered ? '#2A2C31' : '#15171A' } : { backgroundColor: hovered ? '#ECEEF1' : '#F5F6F8' }]}>
      <Text style={[st.gT, { color: disabled ? '#8E8A97' : dark ? '#FFFFFF' : '#15171A' }]}>{children}</Text>
    </Pressable>
  );
}

/** 웹 AI 사용량 창 = 원본 x.tsx UsageSheet (400 · 라운드 28 · 28/27) */
export function WebUsageSheet({ open, pct, refill, onClose, onBuyCredit, onChangePlan }: { open: boolean; pct: number; refill: string; onClose: () => void; onBuyCredit: () => void; onChangePlan: () => void }) {
  const full = pct >= 100;
  return (
    <Sheet open={open} onClose={onClose} width={400} label="AI 사용량">
      <View style={st.us}>
        <View style={{ gap: 4 }}>
          <Text style={st.usH}>AI 사용량</Text>
          <Text keepAll style={st.usD}>{full ? `이번 달 AI 사용량을 다 썼어요 · ${refill}에 새로 채워져요` : `이번 달 ${pct}% 사용 · ${refill}에 새로 채워져요`}</Text>
        </View>
        <View style={st.bar}><View style={[st.barI, { width: `${Math.min(100, pct)}%`, backgroundColor: full ? '#E5484D' : '#15171A' }]} /></View>
        <View style={{ gap: 8 }}>
          {([['크레딧 구매', '이번 달에 필요한 만큼만 더 써요', onBuyCredit], ['플랜 변경', '매달 받는 사용량을 늘려요', onChangePlan]] as const).map(([t, s, f]) => (
            <Pressable key={t} onPress={() => { onClose(); f(); }} accessibilityRole="button" style={({ hovered }: Hover) => [st.uc, hovered && { backgroundColor: '#EEF0F3' }]}>
              <View style={{ flex: 1, minWidth: 0 }}><Text style={st.ucT}>{t}</Text><Text style={st.ucS}>{s}</Text></View>
              <ChevR />
            </Pressable>
          ))}
        </View>
      </View>
    </Sheet>
  );
}

/** 웹 'PLUS예요' 창 = 원본 studio.tsx CreditPopup (사용량을 다 쓴 뒤 만들기를 누르면) */
export function WebCreditPopup({ open, onClose, onPlan, onCharge }: { open: boolean; onClose: () => void; onPlan: () => void; onCharge: () => void }) {
  return (
    <Sheet open={open} onClose={onClose} width={400} scrim={SCRIM} label="이 기능부터는 PLUS예요">
      <View style={[st.pop, { width: 400, gap: 14 }]}>
        <View style={[st.ic, { width: 52, height: 52, borderRadius: 16 }]}><Bolt s={26} c="#FFFFFF" /></View>
        <Text style={st.popH}>이 기능부터는 PLUS예요</Text>
        <Text keepAll style={st.popP}>이번 달 무료 크레딧을 다 썼어요. PLUS에서는 매달 더 많이 만들 수 있어요. 이미 만든 항목과 오늘의 퀴즈는 계속 쓸 수 있어요.</Text>
        <View style={st.btns}><GBtn h={48} flex onPress={onClose}>닫기</GBtn><GBtn h={48} flex dark onPress={onPlan}>PLUS 살펴보기</GBtn></View>
        <Pressable onPress={onCharge} accessibilityRole="button" style={{ alignSelf: 'stretch' }}>
          {({ hovered }: Hover) => <Text style={[st.link, hovered && { color: '#15171A' }]}>이번만 크레딧 충전하기</Text>}
        </Pressable>
      </View>
    </Sheet>
  );
}

/**
 * 웹 'AI 사용량을 다 썼어요' 선택 창 (2026-11-24 서린 님 결정). 크레딧이 0이고 AI 연결 메모가 남아 있으면 뜬다.
 * 충전하거나 플랜을 업그레이드하지 않으면 AI 연결 메모를 모두 끈다. 닫으면 다음에 다시 묻는다 (그동안 매일 확인은 멈춤).
 */
export function WebAiOffChoice({ open, count, busy, onClose, onCharge, onPlan, onOff }: { open: boolean; count: number; busy?: boolean; onClose: () => void; onCharge: () => void; onPlan: () => void; onOff: () => void }) {
  return (
    <Sheet open={open} onClose={onClose} width={420} scrim={SCRIM} label="AI 사용량을 다 썼어요">
      <View style={[st.pop, { width: 420, gap: 14 }]}>
        <View style={[st.ic, { width: 52, height: 52, borderRadius: 16 }]}><Bolt s={26} c="#FFFFFF" /></View>
        <Text style={st.popH}>AI 사용량을 다 썼어요</Text>
        <Text keepAll style={st.popP}>{`크레딧을 충전하거나 플랜을 업그레이드하지 않으면 AI 연결 메모 ${count}개가 모두 꺼져요.\n메모는 그대로 남고, 꺼진 메모는 나중에 하나씩 다시 켤 수 있어요.`}</Text>
        <View style={st.btns}><GBtn h={48} flex onPress={onCharge}>크레딧 충전</GBtn><GBtn h={48} flex dark onPress={onPlan}>플랜 업그레이드</GBtn></View>
        <Pressable disabled={busy} onPress={onOff} accessibilityRole="button" style={{ alignSelf: 'stretch' }}>
          {({ hovered }: Hover) => <Text style={[st.link, hovered && { color: '#15171A' }]}>{busy ? '끄는 중…' : 'AI 연결 모두 끄기'}</Text>}
        </Pressable>
      </View>
    </Sheet>
  );
}

/** 웹 '지난 기간 사용량을 다 써서 꺼졌어요' 안내 (0026 memos.ai_auto_off_at). 확인하거나 닫으면 다시 뜨지 않는다 */
export function WebAiOffNotice({ open, count, onClose }: { open: boolean; count: number; onClose: () => void }) {
  return (
    <Sheet open={open} onClose={onClose} width={400} scrim={SCRIM} label="AI 연결이 꺼졌어요">
      <View style={[st.pop, { width: 400, gap: 14 }]}>
        <View style={[st.ic, { width: 52, height: 52, borderRadius: 16 }]}><Bolt s={26} c="#FFFFFF" /></View>
        <Text style={st.popH}>AI 연결이 꺼졌어요</Text>
        <Text keepAll style={st.popP}>{`지난 기간 AI 사용량을 다 써서 AI 연결 메모 ${count}개가 꺼졌어요.\n메모는 그대로 남아 있어요. 다시 켤 메모를 골라 AI 연결을 켜 주세요.`}</Text>
        <View style={st.btns}><GBtn h={48} flex dark onPress={onClose}>확인</GBtn></View>
      </View>
    </Sheet>
  );
}

/**
 * 웹 크레딧 충전 창 = 원본 studio.tsx ChargePopup (468 · 라운드 28 · 24/22)
 * 상품 고르기 · 결제 수단 · 약관 동의 · [N 크레딧 결제하기] · 'Google Play' 안내
 * 원본 '상품 구성·가격은 팀 확정 전 임시예요.' 는 미정 안내라 뺌. 결제는 연결 안 됨 → onPay 에서 안내만
 */
export function WebChargePopup({ open, packs, default_credits, methods, onClose, onPay }: { open: boolean; packs: CreditPack[]; default_credits: number; methods: string[]; onClose: () => void; onPay: (credits: number) => void }) {
  const [n, setN] = useState(default_credits);
  const [pay, setPay] = useState(methods[0]);
  const [agree, setAgree] = useState(true);
  const [prev, setPrev] = useState(open);
  if (open !== prev) {
    setPrev(open);
    if (open) { setN(default_credits); setPay(methods[0]); setAgree(true); }
  }
  const cur = packs.find((x) => x.credits === n);
  return (
    <Sheet open={open} onClose={onClose} width={468} scrim={SCRIM} label="크레딧 충전">
      <View style={[st.pop, { width: 468, gap: 14 }]}>
        <View style={st.ph}>
          <View style={st.ic}><Bolt s={22} c="#FFFFFF" /></View>
          <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
            <Text style={st.popH}>크레딧 충전</Text>
            <Text style={st.phS}>충전한 크레딧은 바로 쓸 수 있어요</Text>
          </View>
          <CloseX onPress={onClose} />
        </View>
        <View style={{ gap: 8, alignSelf: 'stretch' }}>
          {packs.map((p) => {
            const on = p.credits === n;
            return (
              <Pressable key={p.credits} onPress={() => setN(p.credits)} accessibilityRole="radio" accessibilityState={{ selected: on }} style={({ hovered }: Hover) => [st.pk, on ? st.pkOn : hovered && { backgroundColor: '#F9F9F9' }]}>
                <View style={[st.rd, on && { borderWidth: 6, borderColor: '#15171A' }]} />
                <View style={{ flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Text style={st.pkT}>{p.label}</Text>
                  {p.tag ? <View style={st.tag}><Text style={st.tagT}>{p.tag}</Text></View> : null}
                </View>
                <Text style={st.pkT}>{p.price}</Text>
              </Pressable>
            );
          })}
        </View>
        <Text style={[st.popP, { fontWeight: '700', fontSize: 14 }]}>결제 수단</Text>
        <View style={st.btns}>
          {methods.map((m) => (
            <Pressable key={m} onPress={() => setPay(m)} accessibilityRole="radio" accessibilityState={{ selected: pay === m }} style={({ hovered }: Hover) => [st.pm, pay === m ? { backgroundColor: '#15171A', borderColor: '#15171A' } : hovered && { backgroundColor: '#F9F9F9' }]}>
              <Text style={[st.pmT, pay === m && { color: '#FFFFFF' }]}>{m}</Text>
            </Pressable>
          ))}
        </View>
        <Pressable onPress={() => setAgree(!agree)} accessibilityRole="checkbox" accessibilityState={{ checked: agree }} style={st.agree}>
          {agree ? (
            <Svg width={18} height={18} viewBox="0 0 18 18" fill="none"><Path d="M11.25 3H6.75C4.67893 3 3 4.67893 3 6.75V11.25C3 13.3211 4.67893 15 6.75 15H11.25C13.3211 15 15 13.3211 15 11.25V6.75C15 4.67893 13.3211 3 11.25 3Z" fill="#15171A" /><Path d="M6 9L8.25 11.25L12 6.75" stroke="white" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" /></Svg>
          ) : (
            <Svg width={18} height={18} viewBox="0 0 18 18" fill="none"><Path d="M11.25 3.75H6.75C5.09315 3.75 3.75 5.09315 3.75 6.75V11.25C3.75 12.9069 5.09315 14.25 6.75 14.25H11.25C12.9069 14.25 14.25 12.9069 14.25 11.25V6.75C14.25 5.09315 12.9069 3.75 11.25 3.75Z" stroke="#d9d9d9" strokeWidth={1.5} fill="white" /></Svg>
          )}
          <Text keepAll style={st.agreeT}>구매한 크레딧 중 쓰지 않은 만큼만 환불돼요. 다른 사람에게 넘기거나 현금으로 바꿀 수 없어요. (약관 동의)</Text>
        </Pressable>
        <View style={{ alignSelf: 'stretch' }}><GBtn h={48} dark disabled={!agree} onPress={() => onPay(n)}>{`${cur?.label ?? ''} 결제하기`}</GBtn></View>
        <Text style={[st.popP, { textAlign: 'center' }]}>앱에서는 Google Play 결제로 진행돼요.</Text>
      </View>
    </Sheet>
  );
}

const st = StyleSheet.create({
  g: { borderRadius: 14, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center' },
  gT: { fontSize: 17, lineHeight: 20, fontWeight: '700', letterSpacing: -0.2 },
  us: { width: 400, maxWidth: '100%', gap: 16, borderRadius: 28, backgroundColor: '#FFFFFF', paddingHorizontal: 28, paddingVertical: 27 },
  usH: { fontSize: 22, lineHeight: 31, fontWeight: '700', color: '#15171A' },
  usD: { fontSize: 15, lineHeight: 23, color: '#747D8D' },
  bar: { height: 8, borderRadius: 999, backgroundColor: '#ECEEF1', overflow: 'hidden' },
  barI: { height: 8, borderRadius: 999 },
  uc: { height: 68, flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 16, backgroundColor: '#F5F6F8', paddingHorizontal: 16 },
  ucT: { fontSize: 17, lineHeight: 26, fontWeight: '700', color: '#15171A' },
  ucS: { fontSize: 14, lineHeight: 21, color: '#747D8D' },
  pop: { maxWidth: '100%', alignItems: 'flex-start', overflow: 'hidden', borderRadius: 28, backgroundColor: '#FFFFFF', paddingHorizontal: 24, paddingTop: 24, paddingBottom: 22, shadowColor: '#14171A', shadowOpacity: 0.22, shadowRadius: 80, shadowOffset: { width: 0, height: 30 } },
  ph: { alignSelf: 'stretch', flexDirection: 'row', alignItems: 'center', gap: 12 },
  ic: { width: 44, height: 44, borderRadius: 14, backgroundColor: '#15171A', alignItems: 'center', justifyContent: 'center' },
  popH: { fontSize: 22, lineHeight: 29, fontWeight: '700', letterSpacing: -0.4, color: '#15171A' },
  phS: { fontSize: 14, lineHeight: 18, letterSpacing: -0.2, color: '#8E8A97' },
  popP: { alignSelf: 'stretch', fontSize: 15, lineHeight: 23, letterSpacing: -0.2, color: '#8E8A97' },
  btns: { alignSelf: 'stretch', flexDirection: 'row', gap: 8 },
  link: { textAlign: 'center', fontSize: 14, lineHeight: 21, fontWeight: '700', color: '#8E8A97', textDecorationLine: 'underline' },
  pk: { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 16, paddingHorizontal: 16, paddingVertical: 14, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF' },
  pkOn: { borderWidth: 1.5, borderColor: '#15171A', backgroundColor: '#F5F6F8' },
  rd: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: '#D9D9D9' },
  pkT: { fontSize: 17, lineHeight: 20, fontWeight: '700', letterSpacing: -0.2, color: '#15171A' },
  tag: { height: 22, borderRadius: 999, backgroundColor: '#15171A', paddingHorizontal: 9, justifyContent: 'center' },
  tagT: { fontSize: 13, lineHeight: 16, fontWeight: '700', color: '#FFFFFF' },
  pm: { flex: 1, minWidth: 0, height: 44, borderRadius: 12, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  pmT: { fontSize: 15, lineHeight: 18, fontWeight: '700', color: '#15171A' },
  agree: { alignSelf: 'stretch', flexDirection: 'row', alignItems: 'flex-start', gap: 8, borderRadius: 12, backgroundColor: '#F5F6F8', paddingHorizontal: 14, paddingVertical: 12 },
  agreeT: { flex: 1, minWidth: 0, fontSize: 14, lineHeight: 22, letterSpacing: -0.2, color: '#404752' },
});
