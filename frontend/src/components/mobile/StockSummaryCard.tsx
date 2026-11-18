/**
 * 종목 화면 위쪽 공용 부분: 종목 요약 카드(로고·이름·보유/관심·종가·등락·작은 주가 선) + [메모 보드 | 기업정보] 전환.
 * 메모 보드(MemoBoard)와 기업정보(CompanyOverview)가 같이 씀.
 * 움직임: [메모 보드|기업정보] 알약이 미끄러짐(#039 · 화면이 바뀌어도 직전 탭에서 출발) · 작은 주가 선이 그려짐(1.2s).
 */
import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import Svg, { Circle, Path } from 'react-native-svg';
import { lineLength, useDraw } from '@/components/motion/ChartMotion';
import { SlidingPill } from '@/components/motion/SlidingPill';

const C = {
  card: '#ECEEF1',
  text: '#16171A',
  sub: '#575B63',
  muted: '#9A9EA7',
  up: '#E5484D',
  down: '#2F6BDB',
  tagBg: '#FFFFFF',
  segBg: '#E9EBEE',
  segOn: '#FFFFFF',
  logoText: '#FFFFFF',
  dash: '#C9CDD4',
} as const;
const R = { card: 20, seg: 15, segBtn: 12, logo: 12 };
const PAD = 16;

export interface StockSummary {
  stock_code: string;
  name: string;
  market: string; // 'KOSPI'
  logo_text: string; // 로고 자리 글자 (실제 앱은 로고 이미지)
  logo_bg: string;
  logo_fg?: string;
  status: 'holding' | 'watching';
  close: number; // 전일 확정 종가
  change_amount: number;
  change_rate: number; // %
  close_date: string; // 'MM.DD'
  spark: number[]; // 최근 종가 (작은 선)
}

export type StockTab = 'board' | 'company';

export interface StockSummaryCardProps {
  stock: StockSummary;
  tab: StockTab;
  onChangeTab: (tab: StockTab) => void;
}

/** 직전에 보던 탭 (메모 보드 ↔ 기업정보로 화면이 바뀌어도 알약이 이어서 미끄러지게) */
let LAST_TAB: StockTab | null = null;

const won = (n: number) => `${Math.round(n).toLocaleString('ko-KR')}원`;

export function StockSummaryCard({ stock, tab, onChangeTab }: StockSummaryCardProps) {
  const up = stock.change_rate >= 0;
  const col = up ? C.up : C.down;
  const from = LAST_TAB ?? tab;
  useEffect(() => { LAST_TAB = tab; }, [tab]);
  return (
    <View style={st.wrap}>
      <View style={st.card}>
        <View style={st.row}>
          <View style={[st.logo, { backgroundColor: stock.logo_bg }]}>
            <Text style={[st.logoText, { color: stock.logo_fg ?? C.logoText }]}>{stock.logo_text}</Text>
          </View>
          <View style={st.nameCol}>
            <Text style={st.name} numberOfLines={1}>{stock.name}</Text>
            <Text style={st.code}>{stock.stock_code} · {stock.market}</Text>
          </View>
          <View style={st.tag}><Text style={st.tagText}>{stock.status === 'holding' ? '보유' : '관심'}</Text></View>
        </View>
        <View style={st.priceRow}>
          <View style={st.priceCol}>
            <Text style={st.price} numberOfLines={1} adjustsFontSizeToFit>{won(stock.close)}</Text>
            <Text style={[st.chg, { color: col }]}>
              {up ? '+' : ''}{Math.round(stock.change_amount).toLocaleString('ko-KR')} ({up ? '+' : ''}{stock.change_rate.toFixed(2)}%)
            </Text>
          </View>
          <Spark values={stock.spark} color={col} replay={stock.stock_code} />
        </View>
        <Text style={st.note}>{stock.close_date} 종가 기준</Text>
      </View>
      <SlidingPill<StockTab> items={[{ key: 'board', label: '메모 보드' }, { key: 'company', label: '기업정보' }]} value={tab} from={from}
        onChange={onChangeTab} equal style={st.seg} itemStyle={st.segBtn} pillStyle={st.segOn} textStyle={st.segText} textOnStyle={st.segTextOn} />
    </View>
  );
}

function Spark({ values, color, replay }: { values: number[]; color: string; replay: string }) {
  const W = 120, H = 44;
  const draw = useDraw(replay);
  if (values.length < 2) return null;
  const mn = Math.min(...values), mx = Math.max(...values);
  const x = (i: number) => 2 + (i * (W - 8)) / (values.length - 1);
  const y = (v: number) => 4 + (H - 12) * (1 - (v - mn) / (mx - mn || 1));
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const last = values[values.length - 1];
  const len = lineLength(values.map((v, i) => [x(i), y(v)]));
  return (
    <Svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
      <Path d={`M2 ${H - 4}H${W - 2}`} stroke={C.dash} strokeDasharray="2 3" />
      <Path d={`${d} L${x(values.length - 1)} ${H} L2 ${H}Z`} fill={color} fillOpacity={0.12} />
      <Path d={d} stroke={color} strokeWidth={1.6} fill="none" {...draw(len)} />
      <Circle cx={x(values.length - 1)} cy={y(last)} r={3.2} fill={C.segOn} stroke={color} strokeWidth={1.6} />
    </Svg>
  );
}

const st = StyleSheet.create({
  wrap: { paddingHorizontal: PAD, gap: 14 },
  card: { backgroundColor: C.card, borderRadius: R.card, padding: 18 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  logo: { width: 40, height: 40, borderRadius: R.logo, alignItems: 'center', justifyContent: 'center' },
  logoText: { fontSize: 17, fontWeight: '800' },
  nameCol: { flex: 1, minWidth: 0 },
  name: { fontSize: 17, fontWeight: '800', color: C.text },
  code: { fontSize: 12.5, color: C.sub, marginTop: 2 },
  tag: { backgroundColor: C.tagBg, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  tagText: { fontSize: 12, fontWeight: '700', color: C.text },
  priceRow: { flexDirection: 'row', alignItems: 'flex-end', marginTop: 14, gap: 10 },
  priceCol: { flex: 1, minWidth: 0 },
  price: { fontSize: 28, fontWeight: '800', color: C.text, letterSpacing: -0.5 },
  chg: { fontSize: 14, fontWeight: '600', marginTop: 2 },
  note: { fontSize: 12, color: C.muted, marginTop: 10 },
  seg: { flexDirection: 'row', backgroundColor: C.segBg, borderRadius: R.seg, padding: 4, height: 48 },
  segBtn: { alignSelf: 'stretch' },
  segOn: { backgroundColor: C.segOn, borderRadius: R.segBtn },
  segText: { fontSize: 15, color: C.sub },
  segTextOn: { fontSize: 15, fontWeight: '800', color: C.text },
});
