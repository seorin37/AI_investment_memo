import React, { useEffect, useState } from 'react';
import { Animated, Easing, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import type { LegalKey } from '@/ui/screens/auth/Auth.types';
import { LegalDocumentView } from '@/ui/screens/auth/LegalDocumentView';
import { useMotionK } from '@/ui/motion/useMotion';
import { Sheet } from '@/ui/shared/Sheet';
import { StockLogo } from '@/ui/shared/StockLogo';
import type { PlanInfo, TrackedStock } from '../My.mock';
import type { InfoDoc, NotiSettings, WithdrawProps } from '../My.types';
import { Chev, CloseX, Row, SBtn, Switch, ws, type Hover } from './parts';

/** 웹 설정 창 ⑨-3b 탭 본문 (원본 overlays.tsx TabNoti · TabUsage · PlanView · TabData · TabInfo) — 값은 host 가 My.mock 에서 넘김 */
export interface WebSettingsExtra {
  noti: NotiSettings;
  onNoti: (n: NotiSettings) => void;
  /** credits_*: 이번 기간 쓴·남은 크레딧, tracking_cap: 요금제 추적 항목 상한 (2026-11-25, 모르면 null) */
  usage: { usage_pct: number; usage_renew: string; plan_name: string; credits_used?: number | null; credits_left?: number | null; tracking_cap?: number | null };
  tracked: TrackedStock[];
  onOpenMemo: (stock_code: string, title: string) => void;
  plans: PlanInfo[];
  compare: [string, (string | true)[]][];
  notes: string[];
  plan_default: string;
  /** 지금 쓰는 플랜 카드 key (planKey(user.plan)) */
  current_plan_key: string;
  onStartPlan: (plan_key: string) => void;
  counts: WithdrawProps['counts'];
  onExport: () => void;
  onWipe: () => void;
  /** app.json version '0.1.0' */
  version: string;
  sources: [string, string][];
  oss: [string, string, string][];
  docs: Record<LegalKey, { title: string; html: string }>;
  onFeedback: () => void;
  onReplayGuide: () => void;
}

/* 8-4 알림 */
export function NotiTab({ noti, onNoti }: Pick<WebSettingsExtra, 'noti' | 'onNoti'>) {
  return (
    <View style={{ width: 718, gap: 20 }}>
      <Text style={ws.h16}>받을 알림</Text>
      <Row t="업데이트 알림" d="내 메모에 새 소식이 도착하면 알려줘요." w={654}><Switch on={noti.ai} onChange={(v) => onNoti({ ...noti, ai: v })} label="업데이트 알림" /></Row>
      <View style={ws.hr} />
      <Row t="스튜디오 알림" d="스튜디오에서 만든 항목이 완성되면 알려줘요." w={654}><Switch on={noti.studio} onChange={(v) => onNoti({ ...noti, studio: v })} label="스튜디오 알림" /></Row>
      <Text keepAll style={ws.note}>여기서 켠 알림만 사이드바 종(알림함)에 쌓여요. 알림을 꺼 두면 휴대폰 알림도 오지 않아요.</Text>
    </View>
  );
}

/* 8-8 사용량 */
export function UsageTab({ usage, tracked, onOpenMemo, onPlan }: Pick<WebSettingsExtra, 'usage' | 'tracked' | 'onOpenMemo'> & { onPlan: () => void }) {
  const pct = usage.usage_pct;
  const [open, setOpen] = useState<string | null>(null);
  const total = tracked.reduce((a, r) => a + r.memos.length, 0);
  return (
    <>
      <View style={[ws.card, { padding: 24, gap: 0 }]}>
        <Text style={tb.planName}>{usage.plan_name}</Text>
        <Text style={tb.big}>{pct}% 사용</Text>
        <Bar pct={pct} />
        <View style={tb.useM}>
          <Text style={[ws.d14, { color: '#575B63' }]}>{usage.credits_left != null ? `남은 크레딧 ${usage.credits_left}개 · 이번 기간 ${usage.credits_used ?? 0}개 씀` : `남은 사용량 ${Math.max(0, 100 - pct)}%`}</Text>
          <Text style={ws.d14}>다음 갱신 {usage.usage_renew}</Text>
        </View>
      </View>
      {pct >= 90 ? (
        <View style={[tb.warn, { backgroundColor: pct >= 100 ? '#FDF0F1' : '#FFF4E5' }]}>
          <Text style={[tb.warnB, { color: pct >= 100 ? '#C0392B' : '#7A4A00' }]}>{pct >= 100 ? 'AI 업데이트가 일시 중단되었어요' : '사용량이 거의 다 찼어요'}</Text>
          <Text style={[ws.d14, { color: pct >= 100 ? '#A8433A' : '#8A5A00' }]}>{pct >= 100 ? '사용량을 모두 썼어요. 메모 작성과 기존 기록 확인은 그대로 할 수 있어요.' : `이번 기간 사용량의 ${pct}%를 썼어요. ${usage.usage_renew}에 다시 채워져요.`}</Text>
        </View>
      ) : null}
      <View style={{ width: 718, gap: 12 }}>
        <View style={tb.trkH}><Text style={ws.d14}>종목별 추적 현황</Text><Text style={ws.d14}>추적 항목 {total}개{usage.tracking_cap ? ` / 최대 ${usage.tracking_cap}개` : ''}</Text></View>
        <View style={tb.trk}>
          {tracked.map((s, i) => {
            const on = open === s.stock_code;
            return (
              <View key={s.stock_code} style={i < tracked.length - 1 && tb.trkLine}>
                <Pressable onPress={() => setOpen(on ? null : s.stock_code)} accessibilityRole="button" accessibilityState={{ expanded: on }} style={({ hovered }: Hover) => [tb.trkRow, (on || hovered) && { backgroundColor: '#F8F7F5' }]}>
                  <StockLogo logo={s.logo} bg={s.logo_bg} size={32} radius={8} variant="web" />
                  <Text style={tb.trkName}>{s.name}</Text>
                  <Text style={ws.d14}>{s.memos.length}개 추적 중</Text>
                  <Chev dir={on ? 'up' : 'down'} />
                </Pressable>
                {on ? (
                  <View style={tb.trkBody}>
                    {!s.memos.length ? (
                      <Pressable onPress={() => onOpenMemo(s.stock_code, '')} style={({ hovered }: Hover) => [tb.trkItem, hovered && { backgroundColor: '#F8F7F5' }]}>
                        <Text style={[ws.d14, { flex: 1 }]}>AI 연결한 메모가 없어요 · 보드에서 메모의 플러그를 눌러 켤 수 있어요</Text>
                        <Chev dir="right" />
                      </Pressable>
                    ) : null}
                    {s.memos.map((m) => (
                      <Pressable key={m.title} onPress={() => onOpenMemo(s.stock_code, m.title)} style={({ hovered }: Hover) => [tb.trkItem, hovered && { backgroundColor: '#F8F7F5' }]}>
                        <View style={{ flex: 1, minWidth: 0 }}>
                          <Text style={tb.itemT} numberOfLines={1}>{m.title}</Text>
                          <Text style={tb.itemS} numberOfLines={1}>{m.chips.join(', ')}</Text>
                        </View>
                        <View style={tb.itemR}>
                          <View style={[tb.dot, { backgroundColor: pct >= 100 ? '#C9CCD2' : '#15171A' }]} />
                          <Text style={tb.itemRT}>{pct >= 100 ? '추적 일시 중단' : '추적 중'}</Text>
                          <Chev dir="right" />
                        </View>
                      </Pressable>
                    ))}
                  </View>
                ) : null}
              </View>
            );
          })}
        </View>
        <Text style={[ws.note, { paddingHorizontal: 4 }]}>AI 연결을 켠 메모만 분석하고, 연결하지 않은 메모는 분석하지 않아요. 항목을 누르면 그 메모가 열려요.</Text>
      </View>
      <Pressable onPress={onPlan} accessibilityRole="button" style={({ hovered }: Hover) => [tb.planBtn, hovered && { backgroundColor: '#F8F7F5' }]}>
        <View style={{ gap: 4 }}><Text style={tb.planBtnT}>플랜 살펴보기</Text><Text style={ws.d14}>무료 · PLUS · PRO 비교</Text></View>
        <Chev dir="right" />
      </Pressable>
      <Text style={[ws.note, { paddingHorizontal: 4 }]}>메모 작성과 기존 기록 확인은 사용량과 관계없이 이용할 수 있어요.</Text>
    </>
  );
}

/* 막대 8 · #ECEEF1 · 채움 #15171A (100% 빨강) · .6s */
function Bar({ pct }: { pct: number }) {
  const k = useMotionK();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const a = Animated.timing(v, { toValue: (Math.min(pct, 100) / 100) * 670, duration: 600 * k, easing: Easing.out(Easing.ease), useNativeDriver: false });
    a.start();
    return () => a.stop();
  }, [pct, k, v]);
  return <View style={tb.bar}><Animated.View style={[tb.barI, { width: v, backgroundColor: pct >= 100 ? '#E5484D' : '#15171A' }]} /></View>;
}

/* 플랜 살펴보기 (앱 화면 그대로 · 보라 → 검정) */
const Tick = () => <Svg width={16} height={16} viewBox="0 0 16 16" fill="none"><Path d="M3 8.4L6.4 11.6L13 4.8" stroke="#15171A" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" /></Svg>;
export function PlanView({ plans, compare, notes, pick, setPick }: Pick<WebSettingsExtra, 'plans' | 'compare' | 'notes'> & { pick: string; setPick: (k: string) => void }) {
  return (
    <View style={tb.pv}>
      {plans.map((p) => {
        const on = pick === p.key;
        return (
          <Pressable key={p.key} onPress={() => setPick(p.key)} accessibilityRole="radio" accessibilityState={{ checked: on }} style={({ hovered }: Hover) => [tb.pc, on ? tb.pcOn : hovered && { borderColor: '#C9CCD2' }]}>
            <View style={tb.pcH}>
              <Text style={tb.pcN}>{p.key}</Text>
              {p.tag ? <View style={[tb.chip, p.tag === '추천' && { backgroundColor: '#EFEFEF' }]}><Text style={[tb.chipT, p.tag === '추천' && { color: '#15171A' }]}>{p.tag}</Text></View> : null}
            </View>
            {p.first_price ? (
              <View style={{ gap: 6 }}>
                <View style={tb.saleBadge}><Text style={tb.saleBadgeT}>첫 달 {p.first_pct}% 할인</Text></View>
                <View style={tb.pcP}>
                  <Text style={tb.pcPr}>{p.first_price}</Text>
                  <Text style={tb.strike}>{p.price}</Text>
                </View>
                <Text style={ws.d14}>둘째 달부터 {p.price} / 월</Text>
              </View>
            ) : (
              <View style={tb.pcP}><Text style={tb.pcPr}>{p.price}</Text>{p.price === '0원' ? null : <Text style={ws.d14}>/ 월</Text>}</View>
            )}
            <View style={{ gap: 8 }}>{p.features.map((f) => <View key={f} style={tb.feat}><Tick /><Text style={tb.featT}>{f}</Text></View>)}</View>
            <View style={tb.radio}>
              <Svg width={28} height={28} viewBox="0 0 28 28" fill="none">
                {on ? <><Circle cx={14} cy={14} r={13} fill="#15171A" /><Circle cx={14} cy={14} r={5} fill="#FFFFFF" /></> : <Circle cx={14} cy={14} r={12.2} stroke="#C9CCD2" strokeWidth={1.6} />}
              </Svg>
            </View>
          </Pressable>
        );
      })}
      <View style={{ width: 718, gap: 12 }}>
        <Text style={[ws.d14, { paddingHorizontal: 4 }]}>한눈에 비교</Text>
        <View style={tb.cmp}>
          <View style={[tb.cmpRow, { height: 48 }, tb.cmpLine]}>
            <View style={{ width: 250 }} />
            {plans.map((p) => <Text key={p.key} style={tb.cmpH}>{p.key}</Text>)}
          </View>
          {compare.map(([l, vals], i) => (
            <View key={l} style={[tb.cmpRow, i < compare.length - 1 && tb.cmpLine]}>
              <Text style={tb.cmpL}>{l}</Text>
              {vals.map((v, j) => <View key={j} style={tb.cmpV}>{v === true ? <Tick /> : <Text style={tb.cmpVT}>{v}</Text>}</View>)}
            </View>
          ))}
        </View>
        <View style={{ gap: 4, paddingHorizontal: 4 }}>{notes.map((n) => <Text key={n} style={ws.note}>· {n}</Text>)}</View>
      </View>
    </View>
  );
}
/* 아래 고정: [PLUS 시작하기] 52 · 라운드 14 · 무료면 '현재 플랜' 회색 · 안내 */
export function PlanBar({ pick, free, label, onStart }: { pick: string; free: boolean; label?: string; onStart: () => void }) {
  return (
    <View style={tb.pbar}>
      <Pressable disabled={free} onPress={onStart} accessibilityRole="button" style={({ hovered }: Hover) => [tb.pbtn, { backgroundColor: free ? '#C9CCD2' : hovered ? '#2A2C30' : '#15171A' }]}>
        <Text style={tb.pbtnT}>{free ? '현재 플랜' : label ?? `${pick} 시작하기`}</Text>
      </Pressable>
      <Text style={ws.note}>결제는 스토어 결제 창에서 진행돼요</Text>
    </View>
  );
}

/* 8-6 데이터 */
export function DataTab({ counts, onExport, onAskWipe }: Pick<WebSettingsExtra, 'counts' | 'onExport'> & { onAskWipe: () => void }) {
  const stats: [string, number][] = [['메모', counts.memo], ['투자 기록', counts.journal], ['종목', counts.stock]];
  return (
    <>
      <View style={ws.card}>
        <View style={tb.stats}>{stats.map(([l, n]) => <View key={l} style={tb.stat}><Text style={tb.statL}>{l}</Text><Text style={tb.statV}>{n}개</Text></View>)}</View>
      </View>
      <Row t="내 데이터 내보내기" d="메모·체크리스트·투자 기록·종목을 JSON 파일 하나로 내려받아요." w={558}><SBtn w={120} label="내보내기" onPress={onExport} /></Row>
      <View style={ws.card}>
        <Text style={[ws.t15, { color: '#E45D6A' }]}>위험 구역</Text>
        <View style={tb.dz}>
          <View style={{ width: 554, gap: 4 }}><Text style={ws.t15}>모든 데이터 삭제</Text><Text style={ws.d14}>모든 메모, 기록, 종목이 영구 삭제돼요. 되돌릴 수 없어요.</Text></View>
          <SBtn w={100} red label="전체 삭제" onPress={onAskWipe} />
        </View>
      </View>
    </>
  );
}

/* 8-7 정보 */
export function InfoTab({ version, sources, onDoc, onFeedback, onReplayGuide }: Pick<WebSettingsExtra, 'version' | 'sources' | 'onFeedback' | 'onReplayGuide'> & { onDoc: (d: InfoDoc) => void }) {
  const items: [string, () => void][] = [['사용법 다시 보기', onReplayGuide], ['이용약관', () => onDoc('terms')], ['개인정보 처리방침', () => onDoc('privacy')], ['오픈소스 라이선스', () => onDoc('oss')], ['피드백 보내기', onFeedback], ['문의하기', onFeedback]];
  return (
    <>
      <Row t="버전" d={`MEMO'S v${version} (베타)`} w={558}><View style={{ width: 136, height: 28, justifyContent: 'center' }}><Text style={tb.latest}>최신 버전이에요</Text></View></Row>
      <View style={ws.hr} />
      <View style={{ width: 718 }}>
        {items.map(([t, run]) => (
          <React.Fragment key={t}>
            <Pressable onPress={run} accessibilityRole="button" style={({ hovered }: Hover) => [tb.infoRow, hovered && { backgroundColor: '#F8F7F5' }]}>
              <Text style={tb.infoT}>{t}</Text>
              <Chev dir="right" />
            </Pressable>
            <View style={ws.hr} />
          </React.Fragment>
        ))}
      </View>
      <View style={{ width: 718, gap: 20 }}>
        <Text style={ws.h16}>데이터 출처</Text>
        <Text style={ws.d14}>{sources.map(([k, v]) => `${k} · ${v.replace(/ · /g, ', ')}`).join('   ')}</Text>
      </View>
      <View style={tb.disc}><Text keepAll style={ws.d14}>MEMO&apos;S는 투자 권유를 하지 않으며, 제공되는 모든 정보는 참고용이에요. 투자 판단과 그 결과에 대한 책임은 투자자 본인에게 있어요.</Text></View>
      <Text style={[ws.note, { fontWeight: '500' }]}>SIG · Saram Is Good</Text>
    </>
  );
}

/* 문서 창 680 · 라운드 28 · 제목 22 + 닫기 · 본문 최대 min(560, 화면-200) 스크롤 */
export function DocModal({ doc, docs, oss, onClose }: { doc: InfoDoc | null; docs: WebSettingsExtra['docs']; oss: WebSettingsExtra['oss']; onClose: () => void }) {
  const { height } = useWindowDimensions();
  const title = doc === 'oss' ? '오픈소스 라이선스' : doc ? docs[doc].title : '문서';
  return (
    <Sheet open={!!doc} onClose={onClose} width={680} label={title}>
      <View style={tb.doc}>
        <View style={tb.docH}><Text style={tb.docT}>{title}</Text><CloseX onPress={onClose} /></View>
        <ScrollView style={{ maxHeight: Math.min(560, height - 200) }}>
          {doc === 'oss'
            ? oss.map(([n, l, u]) => <View key={n} style={tb.ossRow}><Text style={tb.ossN}>{n}</Text><Text style={ws.note}>{l} · {u}</Text></View>)
            : doc ? <LegalDocumentView html={docs[doc].html} variant="web" /> : null}
        </ScrollView>
      </View>
    </Sheet>
  );
}

const tb = StyleSheet.create({
  planName: { fontSize: 17, lineHeight: 26, fontWeight: '700', color: '#15171A' },
  big: { marginTop: 16, fontSize: 36, lineHeight: 40, fontWeight: '700', letterSpacing: -0.72, color: '#15171A' },
  bar: { marginTop: 20, height: 8, width: 670, borderRadius: 999, backgroundColor: '#ECEEF1' },
  barI: { height: 8, borderRadius: 999 },
  useM: { marginTop: 12, width: 670, flexDirection: 'row', justifyContent: 'space-between' },
  warn: { width: 718, gap: 4, borderRadius: 16, paddingHorizontal: 20, paddingVertical: 16 },
  warnB: { fontSize: 17, lineHeight: 26, fontWeight: '700' },
  trkH: { height: 20, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 4 },
  trk: { width: 718, borderRadius: 16, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', overflow: 'hidden' },
  trkLine: { borderBottomWidth: 1, borderBottomColor: '#EFEFF2' },
  trkRow: { height: 72, flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 24 },
  trkName: { flex: 1, fontSize: 17, lineHeight: 26, fontWeight: '700', color: '#15171A' },
  trkBody: { paddingHorizontal: 24, paddingTop: 4, paddingBottom: 12 },
  trkItem: { minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 8, paddingVertical: 4, paddingLeft: 44, paddingRight: 8 },
  itemT: { fontSize: 17, lineHeight: 26, color: '#15171A' },
  itemS: { fontSize: 14, lineHeight: 21, color: '#8E8A97' },
  itemR: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { width: 5, height: 5, borderRadius: 3 },
  itemRT: { fontSize: 14, lineHeight: 21, fontWeight: '500', color: '#8E8A97' },
  planBtn: { height: 84, width: 718, borderRadius: 16, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', paddingHorizontal: 24, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  planBtnT: { fontSize: 17, lineHeight: 26, fontWeight: '700', color: '#15171A' },
  pv: { alignItems: 'center', gap: 20 },
  seg: { width: 316, height: 48, flexDirection: 'row', alignItems: 'center', borderRadius: 14, backgroundColor: '#ECEEF1', padding: 4 },
  segSl: { position: 'absolute', left: 4, top: 4, width: 154, height: 40, borderRadius: 11, backgroundColor: '#FFFFFF', shadowColor: '#000000', shadowOpacity: 0.08, shadowRadius: 3, shadowOffset: { width: 0, height: 1 } },
  segB: { flex: 1, height: 40, alignItems: 'center', justifyContent: 'center' },
  segT: { fontSize: 17, lineHeight: 26, color: '#6B6F78' },
  segTOn: { fontWeight: '700', color: '#15171A' },
  pc: { width: 718, gap: 12, borderRadius: 20, backgroundColor: '#FFFFFF', padding: 24, borderWidth: 1, borderColor: '#E5E3E8' },
  pcOn: { borderWidth: 2, borderColor: '#15171A', padding: 23 },
  pcH: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pcN: { fontSize: 20, lineHeight: 29, fontWeight: '700', color: '#15171A' },
  chip: { height: 24, borderRadius: 6, paddingHorizontal: 8, justifyContent: 'center', backgroundColor: '#F3F4F6' },
  chipT: { fontSize: 14, lineHeight: 21, fontWeight: '500', color: '#6B6F78' },
  pcP: { flexDirection: 'row', alignItems: 'baseline', gap: 8 },
  pcPr: { fontSize: 26, lineHeight: 35, fontWeight: '700', color: '#15171A' },
  saleBadge: { alignSelf: 'flex-start', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3, backgroundColor: '#FDECEC' },
  saleBadgeT: { fontSize: 13, lineHeight: 18, fontWeight: '800', color: '#D33A3A' },
  strike: { fontSize: 16, lineHeight: 22, color: '#8E929B', textDecorationLine: 'line-through' },
  feat: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  featT: { fontSize: 17, lineHeight: 26, color: '#33363D' },
  radio: { position: 'absolute', right: 24, top: 24 },
  cmp: { width: 718, borderRadius: 20, borderWidth: 1, borderColor: '#E5E3E8', backgroundColor: '#FFFFFF', paddingHorizontal: 24, paddingVertical: 8 },
  cmpRow: { height: 52, flexDirection: 'row', alignItems: 'center' },
  cmpLine: { borderBottomWidth: 1, borderBottomColor: '#EFEFF2' },
  cmpH: { flex: 1, textAlign: 'center', fontSize: 17, lineHeight: 26, fontWeight: '700', color: '#15171A' },
  cmpL: { width: 250, fontSize: 15, lineHeight: 23, color: '#575B63' },
  cmpV: { flex: 1, alignItems: 'center' },
  cmpVT: { fontSize: 15, lineHeight: 23, color: '#15171A' },
  pbar: { alignItems: 'center', gap: 8, paddingHorizontal: 36, paddingTop: 16, paddingBottom: 20, backgroundColor: '#FFFFFF' },
  pbtn: { height: 52, width: 718, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  pbtnT: { fontSize: 17, lineHeight: 26, fontWeight: '700', color: '#FFFFFF' },
  stats: { height: 80, flexDirection: 'row', gap: 16 },
  stat: { flex: 1, gap: 8 },
  statL: { fontSize: 14, lineHeight: 21, fontWeight: '500', color: '#8E8A97' },
  statV: { fontSize: 26, lineHeight: 35, fontWeight: '700', color: '#15171A' },
  dz: { flexDirection: 'row', alignItems: 'center', gap: 24 },
  latest: { fontSize: 14, lineHeight: 21, fontWeight: '500', color: '#8E8A97' },
  infoRow: { height: 52, marginHorizontal: -12, paddingHorizontal: 12, borderRadius: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  infoT: { fontSize: 15, lineHeight: 23, color: '#15171A' },
  disc: { width: 718, borderRadius: 12, backgroundColor: '#F8F7F5', padding: 16 },
  doc: { width: 680, maxWidth: '100%', gap: 16, borderRadius: 28, backgroundColor: '#FFFFFF', paddingHorizontal: 32, paddingVertical: 28 },
  docH: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  docT: { fontSize: 22, lineHeight: 31, fontWeight: '700', color: '#15171A' },
  ossRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#EFEFF2' },
  ossN: { fontSize: 15, lineHeight: 23, fontWeight: '500', color: '#15171A' },
});
