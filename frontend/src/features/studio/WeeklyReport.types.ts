/** AI 주간보고서 결과 화면 */

export interface ReportNewsItem {
  no: number; // 출처 번호 [1]
  kind: 'disclosure' | 'news';
  date: string; // 'MM.DD'
  title: string;
  source: string; // 'DART' · '한국경제'
}

export interface ReportWatchItem {
  text: string;
  basis: string; // '근거 · 정기 공시 일정'
  /** [메모에 추가] 를 이미 눌렀는지 */
  added: boolean;
}

export interface ReportStock {
  stock_code: string;
  name: string;
  logo_text: string;
  logo_bg: string;
  logo_fg?: string;
  status: 'holding' | 'watching';
  close_label: string; // '180,500원' (금요일 종가)
  weekly_change: number; // %
  week_high: string;
  week_low: string;
  volume_change: string; // '+18%'
  /** 월~금 종가 5개 */
  closes: number[];
  prev_week_close: number;
  /** 주가 선 위 소식 번호: day = 0(월)~4(금) */
  events: { day: number; no: number; kind: 'disclosure' | 'news' }[];
  /** 표지 카드 아래 '공시 1 · 뉴스 2' */
  count_label: string;
  narrative: string;
  items: ReportNewsItem[];
  memo_link?: { title: string; meta: string; text: string; paper: string };
  watch: ReportWatchItem[];
}

export interface ReportMarket {
  indices: { name: string; value: string; change: number }[];
  headlines: { date: string; text: string; ref: string }[];
}

export interface WeeklyReportProps {
  week_label: string; // '2026년 11월 2주'
  period_label: string; // '11.03(월) ~ 11.07(금) · 거래일 5일'
  created_label: string; // '11.09 14:02 작성'
  /** 이번 주 한눈에 (서버가 만든 요약 문장) */
  summary: string;
  stocks: ReportStock[];
  /** 국내 증시 흐름을 넣었을 때만 (11.17: 고를 수 있음, 처음엔 꺼짐) */
  market?: ReportMarket;
  sources: string[];
  onAddWatch: (stock_code: string, index: number) => void;
  onOpenMemo: (stock_code: string) => void;
}
