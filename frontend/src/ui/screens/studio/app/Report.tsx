import React from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import { Head } from '../../my/app/parts';
import type { mockReport, ReportStock } from '../Studio.mock';
import { Spark, SparkWide, WeekChart, issueParas, marketParas, quarterLine, reportSummary, sign, stripRefs, valuationCells, won } from '../reportParts';
import { Keep } from '@/ui/shared/Dark';

/**
 * 앱 주간보고서 = 원본 studio.html #pgRp renderReport2 (16 · 회사 보고서 형식)
 * 검정 표지(종목 카드 · 공시/뉴스/메모 수) · 이번 주 한눈에 · (01 국내 증시 주간 요약) · 종목별 흐름(숫자 · 차트 · 사실 문장 · 이번 주 소식 · 내 메모 · 앞으로 지켜볼 것) · 출처
 * 원본 아래 줄의 '숫자는 시안용 예시'는 개발 상태 표현이라 뺌. 숫자·문장은 모두 Studio.mock
 */
type Rep = typeof mockReport;
const C = { a2: '#6A42AB', ink: '#16171A', ink2: '#575B63', ink3: '#9A9EA7' };
const up = (v: number) => (v >= 0 ? '#E5323B' : '#2F6BDB');

/** 만든 지 30일이 지났거나 아직 없는 보고서 (문구는 웹과 같음) */
export function AppReportMissing({ onBack }: { onBack: () => void }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Head title="주간보고서" onBack={onBack} />
      <View style={st.miss}>
        <Text style={st.missB}>보고서를 찾을 수 없어요</Text>
        <Text keepAll style={st.missS}>만든 지 30일이 지나 지워졌거나 아직 만들지 않았어요.</Text>
      </View>
    </View>
  );
}

export function AppReport({ title, rep, stocks, market, allDefault, onBack, onOpenMemo, onWatch }: {
  /** 만든 항목 제목 ('10월 다섯째 주 돌아보기') */
  title: string;
  rep: Rep; stocks: ReportStock[]; market: boolean; allDefault: boolean;
  onBack: () => void; onOpenMemo: (code: string, memoId?: string) => void; onWatch: (s: ReportStock, i: number) => void;
}) {
  const insets = useSafeAreaInsets();
  const g = stocks.reduce((a, r) => a + r.counts.공시, 0), nw = stocks.reduce((a, r) => a + r.counts.뉴스, 0), mc = stocks.reduce((a, r) => a + (r.memos ? r.memos.length : r.memo ? 1 : 0), 0);
  const one = stocks.length === 1 ? stocks[0] : null;
  const last = rep.days[rep.days.length - 1]?.split(' ')[0] ?? rep.range;
  const sum = reportSummary(stocks, allDefault, rep.summary_default, last);
  const marketText = marketParas(rep.market_summary);
  const codes = stocks.map((s) => s.stock_code);
  const no = (k: number) => String(market ? k : k - 1).padStart(2, '0');
  return (
    <View style={[st.root, { paddingTop: insets.top }]}>
      <Head title="주간보고서" onBack={onBack} />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 4, paddingBottom: 24 + insets.bottom }} showsVerticalScrollIndicator={false}>
        <View style={st.cover}>
          <Svg style={StyleSheet.absoluteFill} preserveAspectRatio="none" viewBox="0 0 10 10">
            <Defs><LinearGradient id="cv" x1="0.1" y1="0" x2="0.9" y2="1"><Stop offset="0" stopColor="#2B2140" /><Stop offset="1" stopColor="#16141F" /></LinearGradient></Defs>
            <Rect width="10" height="10" fill="url(#cv)" />
          </Svg>
          <View style={st.k}><Text style={st.kT}>MEMO&apos;S WEEKLY REPORT</Text><View style={st.kP}><Text style={st.kPT}>{rep.week}</Text></View></View>
          <Text style={st.h2}>{title}</Text>
          <Text style={st.pd}>{rep.range} · 거래일 {rep.days.length}일 · {stocks.length}종목 · {rep.made_at} 작성</Text>
          {one ? (
            <View style={st.one}>
              <View style={st.qn}><Logo s={one} size={22} /><Text style={st.oneN}>{one.name}</Text><View style={st.em}><Text style={st.emT}>{one.own}</Text></View></View>
              <View style={st.pr}><Text style={st.prB}>{won(one.close)}원</Text><Text style={[st.prS, { color: one.pct >= 0 ? '#FF6B6B' : '#5B9BFF' }]}>{sign(one.pct)}</Text><Text style={st.prSm}>이번 주</Text></View>
              <View style={{ marginTop: 8 }}><SparkWide c={one.closes} color={one.pct >= 0 ? '#FF6B6B' : '#5B9BFF'} /></View>
              <View style={st.dl}>{rep.days_short.slice(0, one.closes.length).map((d) => <Text key={d} style={st.dlT}>{d}</Text>)}</View>
              <View style={st.ost}>
                {[['주간 최고', one.hi], ['주간 최저', one.lo], ['이번 주 소식', one.items.length ? `공시 ${one.counts.공시} · 뉴스 ${one.counts.뉴스}` : '없음']].map(([l, v]) => (
                  <View key={l} style={{ flex: 1 }}><Text style={st.ostL}>{l}</Text><Text style={st.ostV} numberOfLines={1}>{v}</Text></View>
                ))}
              </View>
            </View>
          ) : (
            <MiniRow n={stocks.length}>
              {stocks.map((r) => (
                <View key={r.stock_code} style={[st.sm, stocks.length > 3 ? { width: 104 } : { flex: 1, minWidth: 0 }]}>
                  <View style={st.qn}><Logo s={r} size={16} /><Text style={[st.smN, { flexShrink: 1 }]} numberOfLines={1}>{r.name}</Text></View>
                  <Text style={[st.smV, { color: r.pct >= 0 ? '#FF6B6B' : '#5B9BFF' }]}>{sign(r.pct)}</Text>
                  <Spark c={r.closes} color={r.pct >= 0 ? '#FF6B6B' : '#5B9BFF'} />
                  <Text style={st.smS} numberOfLines={1}>{r.items.length ? [r.counts.공시 ? `공시 ${r.counts.공시}` : '', r.counts.뉴스 ? `뉴스 ${r.counts.뉴스}` : ''].filter(Boolean).join(' · ') : '새 소식 없음'}</Text>
                </View>
              ))}
            </MiniRow>
          )}
          <View style={st.tl}>
            {[['공시', `${g}건`], ['뉴스', `${nw}건`], ['메모와 연결', `${mc}개`]].map(([l, v]) => <Text key={l} style={st.tlT}>{l} <Text style={st.tlB}>{v}</Text></Text>)}
          </View>
        </View>
        <View style={[st.r3s, st.sum]}>
          <Text style={st.sumH}>이번 주 한눈에</Text>
          <Text keepAll style={st.sumP}>{sum}</Text>
        </View>
        {/* 요약: 증시 한 주 · 종목별 한 줄 (웹 주간보고서 요약과 같은 내용). 아래로 자세한 내용이 이어짐 */}
        <View style={st.r3s}>
          {market ? null : (
            <View style={{ flexDirection: 'row', gap: 8, marginBottom: 8 }}>
              {rep.market.map((m) => <View key={m.name} style={st.mk}><Text style={st.mkS}>{m.name}</Text><Text style={[st.mkP, { color: up(m.pct) }]}>{sign(m.pct)}</Text></View>)}
            </View>
          )}
          <Text style={st.blockLabel}>종목별 한눈에</Text>
          {stocks.map((r, i) => {
            const bits = [r.counts.공시 ? `공시 ${r.counts.공시}` : '', r.counts.뉴스 ? `뉴스 ${r.counts.뉴스}` : ''].filter(Boolean);
            const memo = r.memos ? (r.memos.length ? `메모 ${r.memos.length}개` : '') : r.memo ? '메모 1개와 연결' : '';
            return (
              <View key={r.stock_code} style={[st.gl, i === stocks.length - 1 && { borderBottomWidth: 0, paddingBottom: 0 }]}>
                <Logo s={r} size={28} />
                <View style={{ flex: 1, minWidth: 0 }}>
                  <Text style={st.glN} numberOfLines={1}>{r.name}</Text>
                  <Text style={st.glS} numberOfLines={2}>{[bits.length ? bits.join(' · ') : '새 소식 없음', memo || (bits.length ? '' : '연결된 메모 없음')].filter(Boolean).join(' · ')}</Text>
                </View>
                <Spark c={r.closes} color={up(r.pct)} />
                <Text style={[st.glP, { color: up(r.pct) }]}>{sign(r.pct)}</Text>
              </View>
            );
          })}
        </View>
        {market ? (
          <>
            <SecH n="01" t="국내 증시 현황" />
            <View style={st.r3s}>
              <Text style={st.marketBasis}>{rep.range} · 거래일 {rep.days.length}일 기준 지수와 한 주 시황이에요</Text>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                {rep.market.map((m) => (
                  <View key={m.name} style={st.mk}><Text style={st.mkS}>{m.name}</Text><Text style={st.mkB}>{m.value}</Text><Text style={[st.mkP, { color: up(m.pct) }]}>{sign(m.pct)}</Text></View>
                ))}
              </View>
              {marketText.length ? <View style={st.marketBrief}><Text style={st.blockLabel}>한 주 시황</Text>{marketText.map((p, i) => <Text key={i} keepAll style={st.txPlain}>{p}</Text>)}</View> : null}
              {rep.flow.length ? <View style={{ marginTop: 12 }}><Text style={st.blockLabel}>날짜별 흐름</Text>
                {rep.flow.map((f, i) => (
                  <View key={f.day} style={[st.nw, i === rep.flow.length - 1 && { borderBottomWidth: 0, paddingBottom: 0 }]}>
                    <Text style={st.nwD}>{f.day}</Text><Text keepAll style={st.nwB}>{f.text}</Text><Text style={st.nwR}>{f.src}</Text>
                  </View>
                ))}
              </View> : null}
            </View>
          </>
        ) : null}
        <SecH n={no(2)} t="종목별 리포트" />
        <Text style={st.secS}>숫자부터 소식과 메모까지 종목별로 정리했어요</Text>
        {stocks.map((r, si) => (
          <View key={r.stock_code} style={[st.sk, { borderTopColor: r.sc }]}>
            <View style={[st.top, { backgroundColor: r.st }]}>
              <Logo s={r} size={28} />
              <Text style={st.topB}>{r.name}</Text>
              <View style={st.tg}><Text style={st.tgT}>{r.own}</Text></View>
              <View style={{ marginLeft: 'auto', alignItems: 'flex-end' }}>
                <Text style={st.topO}>종목 {String(si + 1).padStart(2, '0')} · {last} 종가 기준</Text>
                <Text style={st.qpr}>{won(r.close)}원</Text>
                <Text style={[st.qprS, { color: up(r.pct) }]}>{sign(r.pct)}</Text>
              </View>
            </View>
            <View style={st.bd}>
              <View style={st.metricBlock}>
                <View style={st.blockHead}><Text style={st.blockLabel}>핵심 숫자</Text><Text style={st.blockMeta}>{r.valuation?.basis ?? rep.range}</Text></View>
                <View style={st.st4}>
                  {[['주간 등락', sign(r.pct), up(r.pct)], ['주간 최고', r.hi], ['주간 최저', r.lo], ['거래량', r.vol]].map(([l, v, c]) => (
                    <View key={l} style={st.st4C}><Text style={st.st4S}>{l}</Text><Text style={[st.st4B, c ? { color: c } : null]}>{v}</Text></View>
                  ))}
                </View>
                {valuationCells(r).length ? (
                  <View style={st.st4}>
                    {valuationCells(r).map(([l, v]) => <View key={l} style={st.st4C}><Text style={st.st4S}>{l}</Text><Text style={st.st4B}>{v}</Text></View>)}
                  </View>
                ) : null}
              </View>
              {quarterLine(r) ? <View style={st.quarterBox}><View style={st.blockHead}><Text style={st.blockLabel}>최근 분기 실적</Text><Text style={st.blockMeta}>{r.quarter?.label} · {r.quarter?.basis}</Text></View><Text keepAll style={st.quarterText}>{quarterLine(r)}</Text></View> : null}
              {r.memos?.length ? (
                <View style={st.dg}>
                  <Text style={st.dgH}>이번 주 내 메모 정리</Text>
                  {r.memo_digest ? <Text keepAll style={st.dgLead}>{stripRefs(r.memo_digest)}</Text> : null}
                  {r.memos.map((m) => (
                    <View key={m.memo_id} style={st.dgM}>
                      <Pressable onPress={() => onOpenMemo(r.stock_code, m.memo_id)} accessibilityRole="link"><Text style={st.dgT}>{m.title}  <Text style={st.dgS}>{m.meta} ›</Text></Text></Pressable>
                      {m.cards.map((c) => (
                        <View key={c.id} style={st.dgC}>
                          <Text style={st.dgS}>{c.date} · {c.kind}</Text>
                          <Text keepAll style={st.dgCT}>{c.title}{c.refs.length ? <Text style={st.dgS}>{'  '}{c.refs.map((x) => `[${x}]`).join('')}</Text> : null}</Text>
                          <Text keepAll style={st.dgCB} numberOfLines={2}>{c.text}</Text>
                        </View>
                      ))}
                      {m.status.map((x) => <Text key={x} keepAll style={st.dgSt}>· {x}</Text>)}
                      {!m.cards.length && !m.status.length ? <Text style={st.dgS}>이번 주 새 소식 없음 · 추적 중</Text> : null}
                      {m.more ? <Text style={st.dgS}>그 밖에 {m.more}건 · 메모에서 보기</Text> : null}
                    </View>
                  ))}
                </View>
              ) : null}
              <Text style={st.sub}>이번 주 흐름</Text>
              <View style={{ marginTop: 4 }}><WeekChart r={r} days={rep.days} id={r.stock_code} /></View>
              <View style={st.lg}>
                <Text style={st.lgT}><Text style={{ color: '#7C5CE0' }}>● </Text>공시</Text>
                <Text style={st.lgT}><Text style={{ color: '#3D73F0' }}>● </Text>뉴스</Text>
                <View style={st.lgI}><View style={st.dash} /><Text style={st.lgT}>지난주 종가</Text></View>
                <Text style={[st.lgT, { width: '100%' }]}>번호는 아래 소식·출처 번호예요</Text>
              </View>
              <Text keepAll style={st.tx}>{stripRefs(r.story)}</Text>
              {issueParas(r).length ? (
                <View style={st.issueBox}>
                  <Text style={[st.sub, { marginTop: 0 }]}>이번 주 이슈 정리</Text>
                  {issueParas(r).map((t, k) => <Text key={k} keepAll style={st.issueText}>{t}</Text>)}
                </View>
              ) : null}
              <Text style={st.sub}>이번 주 소식 <Text style={st.subMeta}>공시 {r.counts.공시} · 뉴스 {r.counts.뉴스}</Text></Text>
              {r.items.length ? (
                <>
                  {r.items.map((x, i) => (
                    <View key={x.no} style={[st.ev, i === r.items.length - 1 && { borderBottomWidth: 0 }]}>
                      <View style={[st.no, { backgroundColor: x.kind === '공시' ? '#7C5CE0' : '#3D73F0' }]}><Text style={st.noT}>{x.no}</Text></View>
                      <View style={[st.tg5, x.kind === '뉴스' && { backgroundColor: '#E4ECFF' }]}><Text style={[st.tg5T, x.kind === '뉴스' && { color: '#2F6BDB' }]}>{x.kind}</Text></View>
                      <Text style={st.evD}>{x.date}</Text>
                      <Text style={st.evB}>{x.title}</Text>
                      <Text style={st.evD}>{x.src}</Text>
                    </View>
                  ))}
                </>
              ) : <Text style={st.empty}>새로 나온 소식이 없어요</Text>}
              {r.memos ? null : r.memo ? (
                <View style={[st.mc, { backgroundColor: r.memo.bg }]}>
                  <View style={st.mcH}><Text style={[st.mcHT, { color: r.memo.ink }]}>내 메모와의 연결</Text><Pressable onPress={() => onOpenMemo(r.stock_code)} accessibilityRole="link"><Text style={[st.mcHT, { color: r.memo.ink, fontWeight: '700', opacity: 1 }]}>원본 메모 보기 ›</Text></Pressable></View>
                  <Text style={[st.mcB, { color: r.memo.ink }]}>{r.memo.title}  <Text style={st.mcS}>{r.memo.meta}</Text></Text>
                  <Text keepAll style={[st.mcP, { color: r.memo.ink }]}>{stripRefs(r.memo.body)}</Text>
                  <Text style={[st.mcS, { color: r.memo.ink, marginTop: 6 }]}>이번 주 연결된 소식 {r.memo.linked_count ?? r.counts.공시 + r.counts.뉴스}건</Text>
                </View>
              ) : <View style={st.mcEmpty}><View style={st.mcH}><Text style={st.mcEmptyH}>내 메모와의 연결</Text><Pressable onPress={() => onOpenMemo(r.stock_code)} accessibilityRole="link"><Text style={st.mcEmptyL}>메모 쓰기 ›</Text></Pressable></View><Text style={st.empty}>이번 주 소식과 연결된 메모가 없어요.</Text></View>}
              <View style={st.wt}>
                <View style={st.wtH}>
                  <Svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="#5B3BD1" strokeWidth={2}><Path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><Circle cx={12} cy={12} r={3} /></Svg>
                  <Text style={st.wtHT}>앞으로 지켜볼 것</Text>
                </View>
                {r.watch.map((w, i) => (
                  <View key={w.sid ?? w.text} style={st.it}>
                    <View style={{ flex: 1, minWidth: 0 }}><Text keepAll style={st.itB}>{w.text}</Text><Text style={st.itS}>근거 · {w.why}</Text></View>
                    {w.tracked || w.added ? (
                      <View style={st.itDone}><Text style={st.itDoneT}>{w.tracked ? '✓ 추적 중' : '✓ 추가됨'}</Text></View>
                    ) : (
                      <Pressable onPress={() => onWatch(r, i)} accessibilityRole="button" style={st.itBtn}><Text style={st.itBtnT}>메모에 추가</Text></Pressable>
                    )}
                  </View>
                ))}
              </View>
            </View>
          </View>
        ))}
        <SecH n={no(3)} t="출처" />
        <View style={st.r3s}>
          {rep.sources.filter((x) => (x.code ? codes.includes(x.code) : market)).map((x) => <Text key={x.text} style={st.src}>{x.text}</Text>)}
          <Text keepAll style={st.srcS}>{rep.source_note}</Text>
        </View>
        <Text keepAll style={st.disc}>공시·뉴스·시세에서 가져온 정보예요. 투자 권유나 주가 예측이 아니에요.</Text>
      </ScrollView>
    </View>
  );
}

/** 표지 종목 카드 줄: 3개까지 같은 폭으로 꽉 차게, 4개부터 가로 스크롤 */
function MiniRow({ n, children }: { n: number; children: React.ReactNode }) {
  if (n <= 3) return <View style={{ flexDirection: 'row', gap: 8, marginTop: 14 }}>{children}</View>;
  return <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }} style={{ marginTop: 14 }}>{children}</ScrollView>;
}

function SecH({ n, t }: { n: string; t: string }) {
  return <View style={st.r3h}><Text style={st.r3hE}>{n}</Text><Text style={st.r3hT}>{t}</Text><View style={st.r3hL} /></View>;
}

function Logo({ s, size }: { s: ReportStock; size: number }) {
  return <Keep style={{ width: size, height: size, borderRadius: size * 0.3, backgroundColor: s.logo_bg, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: size * 0.48, lineHeight: size * 0.62, fontWeight: '800', color: s.logo_ink ?? '#FFFFFF' }}>{s.logo}</Text></Keep>;
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F3F4F6' },
  cover: { borderRadius: 22, overflow: 'hidden', paddingTop: 18, paddingHorizontal: 16, paddingBottom: 16 },
  k: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  kT: { fontSize: 11, lineHeight: 15, letterSpacing: 0.8, fontWeight: '800', color: '#B9A8E6' },
  kP: { backgroundColor: 'rgba(255,255,255,0.12)', borderRadius: 999, paddingHorizontal: 9, paddingVertical: 3 },
  kPT: { fontSize: 11, lineHeight: 15, fontWeight: '600', color: '#FFFFFF' },
  h2: { fontSize: 24, lineHeight: 32, fontWeight: '800', color: '#FFFFFF', marginTop: 10, marginBottom: 4 },
  pd: { fontSize: 12, lineHeight: 17, color: '#C9C3D9' },
  sm: { backgroundColor: 'rgba(255,255,255,0.07)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)', borderRadius: 14, padding: 10 },
  qn: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  smN: { fontSize: 12, lineHeight: 17, fontWeight: '700', color: '#FFFFFF' },
  smV: { fontSize: 16, lineHeight: 24, fontWeight: '400', marginTop: 6 },
  smS: { marginTop: 4, fontSize: 11, lineHeight: 15, color: '#C9C3D9' },
  one: { marginTop: 14, backgroundColor: 'rgba(255,255,255,0.07)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)', borderRadius: 16, paddingTop: 14, paddingHorizontal: 14, paddingBottom: 12 },
  oneN: { fontSize: 14, lineHeight: 19, fontWeight: '700', color: '#FFFFFF', marginLeft: 2 },
  em: { backgroundColor: 'rgba(255,255,255,0.14)', borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  emT: { fontSize: 11, lineHeight: 15, fontWeight: '700', color: '#E6E0F5' },
  pr: { flexDirection: 'row', alignItems: 'baseline', gap: 8, marginTop: 10 },
  prB: { fontSize: 26, lineHeight: 32, fontWeight: '800', letterSpacing: -0.4, color: '#FFFFFF' },
  prS: { fontSize: 15, lineHeight: 20, fontWeight: '800' },
  prSm: { marginLeft: 'auto', fontSize: 11.5, lineHeight: 16, color: '#C9C3D9' },
  dl: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 2 },
  dlT: { fontSize: 10.5, lineHeight: 14, fontWeight: '600', color: '#9C94B3' },
  ost: { flexDirection: 'row', marginTop: 12, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.12)', paddingTop: 10 },
  ostL: { fontSize: 11, lineHeight: 15, fontWeight: '500', color: '#C9C3D9' },
  ostV: { fontSize: 14, lineHeight: 19, fontWeight: '700', color: '#FFFFFF', marginTop: 2 },
  tl: { flexDirection: 'row', gap: 14, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.12)', marginTop: 14, paddingTop: 12 },
  tlT: { fontSize: 12, lineHeight: 17, color: '#C9C3D9' },
  tlB: { color: '#FFFFFF', fontWeight: '700' },
  r3s: { backgroundColor: '#FFFFFF', borderRadius: 20, padding: 16, marginTop: 12 },
  sum: { borderLeftWidth: 3, borderLeftColor: '#8569E3' },
  sumH: { fontSize: 13, lineHeight: 18, fontWeight: '800', color: C.a2, marginBottom: 6 },
  sumP: { fontSize: 14, lineHeight: 24, color: '#2E2E38' },
  gl: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: '#F0F1F4' },
  glN: { fontSize: 14, lineHeight: 19, fontWeight: '700', color: C.ink },
  glS: { fontSize: 12, lineHeight: 17, color: C.ink3 },
  glP: { width: 52, textAlign: 'right', fontSize: 14, lineHeight: 19, fontWeight: '700' },
  topO: { fontSize: 11, lineHeight: 15, color: C.ink3 },
  r3h: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 22, marginHorizontal: 2 },
  r3hE: { fontSize: 12, lineHeight: 17, color: C.a2 },
  r3hT: { fontSize: 16, lineHeight: 22, fontWeight: '800', color: C.ink },
  miss: { alignItems: 'center', paddingTop: 96, paddingHorizontal: 24 },
  missB: { fontSize: 18, lineHeight: 25, fontWeight: '800', color: C.ink },
  missS: { fontSize: 13.5, lineHeight: 20, color: C.ink2, marginTop: 6, textAlign: 'center' },
  secS: { fontSize: 12, lineHeight: 17, color: C.ink3, marginTop: 4, marginHorizontal: 2 },
  r3hL: { flex: 1, height: 1, backgroundColor: '#E2E4E8' },
  mk: { flex: 1, minWidth: 0, backgroundColor: '#F6F6F8', borderRadius: 12, paddingVertical: 9, paddingHorizontal: 10 },
  mkS: { fontSize: 11.5, lineHeight: 16, color: C.ink3 },
  mkB: { fontSize: 14.5, lineHeight: 20, fontWeight: '700', color: C.ink },
  mkP: { fontSize: 12, lineHeight: 17, fontWeight: '700' },
  marketBasis: { fontSize: 11.5, lineHeight: 16, color: C.ink3, marginBottom: 9 },
  marketBrief: { borderTopWidth: 1, borderTopColor: '#ECEEF2', paddingTop: 12, marginTop: 12 },
  blockHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  blockLabel: { fontSize: 12.5, lineHeight: 18, fontWeight: '800', color: C.ink2 },
  blockMeta: { flexShrink: 1, textAlign: 'right', fontSize: 11.5, lineHeight: 16, color: C.ink3 },
  txPlain: { fontSize: 13.5, lineHeight: 22, color: '#2E2E38', marginTop: 6 },
  nw: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: '#F0F1F4' },
  nwD: { width: 46, fontSize: 12, lineHeight: 19, color: C.ink3 },
  nwB: { flex: 1, fontSize: 13.5, lineHeight: 20, fontWeight: '600', color: C.ink },
  nwR: { fontSize: 12, lineHeight: 19, color: C.ink3 },
  sk: { backgroundColor: '#FFFFFF', borderRadius: 20, marginTop: 12, overflow: 'hidden', borderTopWidth: 3 },
  top: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 14, paddingHorizontal: 16 },
  topB: { fontSize: 17, lineHeight: 23, fontWeight: '700', color: C.ink },
  tg: { backgroundColor: 'rgba(255,255,255,0.75)', borderRadius: 6, paddingHorizontal: 7, paddingVertical: 1 },
  tgT: { fontSize: 11.5, lineHeight: 16, fontWeight: '700', color: C.ink2 },
  qpr: { fontSize: 15, lineHeight: 20, fontWeight: '800', color: C.ink },
  qprS: { fontSize: 12.5, lineHeight: 17, fontWeight: '700' },
  bd: { paddingTop: 14, paddingHorizontal: 16, paddingBottom: 16 },
  metricBlock: { gap: 8, backgroundColor: '#F7F8FA', borderRadius: 14, padding: 12 },
  st4: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  st4C: { width: '48.5%', backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#ECEDF1', borderRadius: 12, paddingVertical: 8, paddingHorizontal: 10 },
  st4S: { fontSize: 11.5, lineHeight: 16, color: C.ink3 },
  st4B: { fontSize: 15, lineHeight: 21, fontWeight: '700', color: C.ink },
  quarterBox: { gap: 7, borderWidth: 1, borderColor: '#E5E7EC', borderRadius: 14, padding: 12, marginTop: 10 },
  quarterText: { fontSize: 13.5, lineHeight: 21, color: '#2E2E38' },
  lg: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 6 },
  lgT: { fontSize: 11.5, lineHeight: 16, color: C.ink3 },
  /* ┄ 기호 대신 점선 막대 (412 폭에서 글자 잘림 방지) */
  lgI: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  dash: { width: 12, height: 0, borderTopWidth: 1, borderColor: '#B5B9C0', borderStyle: 'dashed' },
  tx: { fontSize: 14, lineHeight: 23, color: '#2E2E38', marginTop: 10 },
  sub: { fontSize: 13, lineHeight: 18, fontWeight: '800', color: C.ink, marginTop: 14, marginBottom: 2 },
  subMeta: { fontSize: 11.5, fontWeight: '500', color: C.ink3 },
  issueBox: { gap: 8, borderLeftWidth: 3, borderLeftColor: '#8569E3', backgroundColor: '#F8F7FC', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 12, marginTop: 14 },
  issueText: { fontSize: 14, lineHeight: 23, color: '#2E2E38' },
  empty: { fontSize: 12.5, lineHeight: 19, color: C.ink3, marginTop: 6 },
  ev: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: '#F3F4F6' },
  no: { width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  noT: { fontSize: 11, lineHeight: 14, fontWeight: '800', color: '#FFFFFF' },
  tg5: { borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1, backgroundColor: '#EEE9FB' },
  tg5T: { fontSize: 11.5, lineHeight: 16, fontWeight: '800', color: '#5B3BD1' },
  evD: { fontSize: 12, lineHeight: 17, color: C.ink3 },
  evB: { flex: 1, minWidth: 0, fontSize: 13.5, lineHeight: 19, fontWeight: '600', color: C.ink },
  mc: { borderRadius: 14, paddingVertical: 12, paddingHorizontal: 14, marginTop: 12 },
  dg: { gap: 8, borderRadius: 14, backgroundColor: '#FFF9E6', paddingVertical: 12, paddingHorizontal: 14, marginTop: 12 },
  dgH: { fontSize: 13, lineHeight: 18, fontWeight: '800', color: C.ink },
  dgLead: { fontSize: 13, lineHeight: 20, color: '#3F3A2A' },
  dgM: { gap: 4, borderRadius: 10, backgroundColor: '#FFFFFF', padding: 10 },
  dgT: { fontSize: 13.5, lineHeight: 19, fontWeight: '700', color: C.ink },
  dgS: { fontSize: 11.5, lineHeight: 16, color: '#8B95A1' },
  dgC: { gap: 1, marginTop: 2 },
  dgCT: { fontSize: 12.5, lineHeight: 18, fontWeight: '600', color: '#2B2F36' },
  dgCB: { fontSize: 12, lineHeight: 17, color: '#5B6270' },
  dgSt: { fontSize: 12, lineHeight: 17, color: '#A35A00' },
  mcH: { flexDirection: 'row', justifyContent: 'space-between' },
  mcHT: { fontSize: 12, lineHeight: 17, opacity: 0.8 },
  mcB: { fontSize: 14.5, lineHeight: 20, fontWeight: '700', marginTop: 4 },
  mcS: { fontSize: 12, fontWeight: '500', opacity: 0.7 },
  mcP: { fontSize: 13, lineHeight: 20, marginTop: 4 },
  mcEmpty: { borderRadius: 14, backgroundColor: '#F7F8FA', paddingVertical: 12, paddingHorizontal: 14, marginTop: 12 },
  mcEmptyH: { fontSize: 12.5, lineHeight: 18, fontWeight: '800', color: C.ink2 },
  mcEmptyL: { fontSize: 12.5, lineHeight: 18, fontWeight: '700', color: C.ink2 },
  wt: { backgroundColor: '#FBF8FF', borderWidth: 1, borderColor: '#EEE7FB', borderRadius: 14, padding: 12, marginTop: 12 },
  wtH: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  wtHT: { fontSize: 13, lineHeight: 18, fontWeight: '800', color: '#5B3BD1' },
  it: { flexDirection: 'row', gap: 10, alignItems: 'center', backgroundColor: '#FFFFFF', borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12, marginTop: 8 },
  itB: { fontSize: 13.5, lineHeight: 20, fontWeight: '700', color: C.ink },
  itS: { fontSize: 12, lineHeight: 17, color: C.ink3 },
  itBtn: { height: 32, paddingHorizontal: 12, borderRadius: 10, backgroundColor: C.ink, justifyContent: 'center' },
  itBtnT: { fontSize: 12.5, lineHeight: 17, fontWeight: '700', color: '#FFFFFF' },
  itDone: { height: 32, paddingHorizontal: 10, borderRadius: 10, borderWidth: 1, borderColor: '#E6E3F3', justifyContent: 'center' },
  itDoneT: { fontSize: 12.5, lineHeight: 17, fontWeight: '600', color: '#8B95A1' },
  src: { fontSize: 12.5, lineHeight: 24, color: '#3F434A' },
  srcS: { fontSize: 12.5, lineHeight: 20, color: C.ink3, marginTop: 8 },
  disc: { fontSize: 11.5, lineHeight: 17, color: C.ink3, textAlign: 'center', marginTop: 18 },
});
