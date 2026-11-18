/** 주간보고서 예시 — 체험판 v3 (SK하이닉스 · 삼성전자 · 네이버, 국내 증시 흐름 포함 / 1종목 버전) */
import type { ReportStock, WeeklyReportProps } from '@/features/studio/WeeklyReport.types';

const sk: ReportStock = {
  stock_code: '000660', name: 'SK하이닉스', logo_text: 'S', logo_bg: '#EA002C', status: 'holding',
  close_label: '180,500원', weekly_change: 6.2, week_high: '182,000', week_low: '168,500', volume_change: '+18%',
  closes: [170000, 172500, 177800, 179300, 180500], prev_week_close: 170000,
  events: [{ day: 1, no: 1, kind: 'disclosure' }, { day: 3, no: 3, kind: 'news' }, { day: 4, no: 4, kind: 'news' }],
  count_label: '공시 1 · 뉴스 2',
  narrative: '화요일(11.04) 신규 시설투자 공시[1]가 나왔고, 다음 날 11.05 종가 기준 3.1% 오르며 거래량이 이번 주 가장 많았어요. 목요일에는 HBM4 공급 확대 기사[3]가 이어졌고, 금요일 180,500원으로 마감했어요.',
  items: [
    { no: 1, kind: 'disclosure', date: '11.04', title: '신규 시설투자 결정', source: 'DART' },
    { no: 3, kind: 'news', date: '11.06', title: 'HBM4 공급 확대 기대감', source: '한국경제' },
    { no: 4, kind: 'news', date: '11.07', title: '반도체 장비 발주 증가', source: '매일경제' },
  ],
  memo_link: { title: 'HBM 수요 계속 확인', meta: '9.25 작성 · AI 연결 중', text: "메모의 추적 항목 'HBM 생산 능력'과 관련된 소식 2건([1], [3])이 이번 주에 붙었어요.", paper: '#FCEAAA' },
  watch: [
    { text: '11월 말 분기보고서에 HBM 매출이 따로 나오는지', basis: '정기 공시 일정', added: false },
    { text: '메모의 가격 조건 15만 원과 지금 가격의 거리 (현재 20.3% 위)', basis: '내 메모 가격 조건', added: true },
  ],
};

const ss: ReportStock = {
  stock_code: '005930', name: '삼성전자', logo_text: '삼', logo_bg: '#1428A0', status: 'watching',
  close_label: '71,400원', weekly_change: 1.4, week_high: '72,100', week_low: '69,800', volume_change: '-4%',
  closes: [70400, 69800, 71900, 72000, 71400], prev_week_close: 70400,
  events: [{ day: 2, no: 2, kind: 'disclosure' }],
  count_label: '공시 1',
  narrative: '수요일(11.05) 자기주식 취득 결정 공시[2]가 나온 날 종가가 3.0% 올랐어요. 이후 이틀은 큰 움직임 없이 71,400원으로 마감했고, 거래량은 지난주보다 4% 줄었어요.',
  items: [{ no: 2, kind: 'disclosure', date: '11.05', title: '자기주식 취득 결정', source: 'DART' }],
  memo_link: { title: '자사주 매입 나오면 다시 보기', meta: '10.02 작성 · AI 연결 꺼짐', text: '메모에 적어 둔 자사주 매입이 이번 주 공시[2]로 나왔어요.', paper: '#D9E4FF' },
  watch: [{ text: '취득 기간 동안 나오는 자기주식 취득 결과 보고', basis: '이번 주 공시[2]의 취득 기간', added: false }],
};

const nv: ReportStock = {
  stock_code: '035420', name: '네이버', logo_text: '네', logo_bg: '#03C75A', status: 'watching',
  close_label: '212,300원', weekly_change: -0.8, week_high: '216,000', week_low: '211,500', volume_change: '-9%',
  closes: [214000, 216000, 213800, 212000, 212300], prev_week_close: 214000,
  events: [], count_label: '새 소식 없음',
  narrative: '이번 주 새 공시·뉴스는 없었어요. 화요일 216,000원까지 올랐다가 이후 내려 212,300원으로 마감했어요.',
  items: [],
  watch: [{ text: '다음 주 새 공시·뉴스가 나오는지', basis: '이번 주 소식 0건 · 추가하면 새 메모로 남겨요', added: false }],
};

const noop = () => {};

export const mockWeeklyReportProps: WeeklyReportProps = {
  week_label: '2026년 11월 2주',
  period_label: '11.03(월) ~ 11.07(금) · 거래일 5일',
  created_label: '11.09 14:02 작성',
  summary: '내 종목 3곳 중 2곳이 올랐어요. SK하이닉스가 +6.2%로 가장 크게 움직였어요.',
  stocks: [sk, ss, nv],
  market: {
    indices: [{ name: '코스피', value: '2,650.35', change: 2.0 }, { name: '코스닥', value: '862.10', change: 0.6 }, { name: '원/달러', value: '1,350.20', change: -1.6 }],
    headlines: [
      { date: '11.04 화', text: '미국 반도체 지수 강세에 국내 반도체주 동반 상승', ref: '[5]' },
      { date: '11.05 수', text: '외국인, 사흘 연속 코스피 순매수', ref: '[6]' },
      { date: '11.07 금', text: '원/달러 환율 1,350원대로 내려 원화 강세', ref: '[7]' },
    ],
  },
  sources: [
    '[1] DART · SK하이닉스 신규시설투자 · 2026.11.04',
    '[2] DART · 삼성전자 자기주식취득결정 · 2026.11.05',
    '[3] 한국경제 · 기사 제목 · 2026.11.06',
    '[4] 매일경제 · 기사 제목 · 2026.11.07',
    '[5] 언론사 · 기사 제목 · 2026.11.04',
    '[6] 언론사 · 기사 제목 · 2026.11.05',
    '[7] 언론사 · 기사 제목 · 2026.11.07',
  ],
  onAddWatch: noop,
  onOpenMemo: noop,
};

/** 종목 1개만 고른 보고서 (국내 증시 흐름 꺼짐) */
export const mockWeeklyReportOneProps: WeeklyReportProps = {
  ...mockWeeklyReportProps,
  stocks: [ss],
  market: undefined,
  summary: '삼성전자는 이번 주 1.4% 올라 71,400원으로 마감했어요. 공시 1건이 나왔고, 메모에 적어 둔 내용과 연결됐어요.',
  sources: ['[2] DART · 삼성전자 자기주식취득결정 · 2026.11.05'],
};
