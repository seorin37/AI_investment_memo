/* MEMO'S 웹 시연용 데이터 — 피그마 Page 2.5 / Page 3 문구 그대로 */
export type ColorKey = "yellow" | "green" | "blue" | "purple" | "pink";
export const PAPER: Record<ColorKey, { bg: string; accent: string; label: string }> = {
  yellow: { bg: "#fceaaa", accent: "#efbf2a", label: "노랑" },
  green: { bg: "#cdefd9", accent: "#2fae68", label: "초록" },
  blue: { bg: "#cfe0ff", accent: "#3d73f0", label: "파랑" },
  purple: { bg: "#d2beff", accent: "#7046f5", label: "보라" },
  pink: { bg: "#f7c6f0", accent: "#d62bc4", label: "분홍" },
};

export type Hold = "보유" | "관심";
export type Stock = { code: string; name: string; short: string; logo: string; logoBg: string; hold: Hold; market: string; price: number; chg: number; pct: number; seed: number; unread?: number /* API 모드: 서버의 읽지 않은 AI 업데이트 수 */ };
export const ALL_STOCKS: Stock[] = [
  { code: "000660", name: "SK하이닉스", short: "S", logo: "S", logoBg: "#ea002c", hold: "보유", market: "KOSPI", price: 180500, chg: 4200, pct: 2.38, seed: 3 },
  { code: "005930", name: "삼성전자", short: "삼", logo: "삼", logoBg: "#1428a0", hold: "관심", market: "KOSPI", price: 71400, chg: 1500, pct: 2.15, seed: 7 },
  { code: "035420", name: "네이버", short: "N", logo: "네", logoBg: "#03c75a", hold: "관심", market: "KOSPI", price: 212300, chg: 2700, pct: 1.29, seed: 11 },
];
export const SEARCH_POOL = [
  { code: "005930", name: "삼성전자", market: "KOSPI" }, { code: "005935", name: "삼성전자우", market: "KOSPI" },
  { code: "000660", name: "SK하이닉스", market: "KOSPI" }, { code: "035420", name: "네이버", market: "KOSPI" },
  { code: "105560", name: "KB금융", market: "KOSPI" }, { code: "005380", name: "현대차", market: "KOSPI" },
  { code: "000270", name: "기아", market: "KOSPI" }, { code: "373220", name: "LG에너지솔루션", market: "KOSPI" },
  { code: "035720", name: "카카오", market: "KOSPI" }, { code: "068270", name: "셀트리온", market: "KOSPI" },
  { code: "247540", name: "에코프로비엠", market: "KOSDAQ" }, { code: "028300", name: "HLB", market: "KOSDAQ" },
];
export const NEW_LOGO: Record<string, [string, string]> = { "105560": ["K", "#ffbc00"], "005380": ["현", "#002c5f"], "000270": ["기", "#05141f"], "373220": ["LG", "#a50034"], "035720": ["K", "#ffcd00"], "068270": ["C", "#2f4ea1"], "005935": ["삼", "#1428a0"], "247540": ["E", "#0a7e3f"], "028300": ["H", "#d71a20"] };

/* 시장 */
export const MARKET = [
  { key: "kospi", flag: "🇰🇷", name: "코스피", v: 2650.35, c: -12.4, p: -0.47, seed: 3 },
  { key: "kosdaq", flag: "🇰🇷", name: "코스닥", v: 850.12, c: -4.18, p: -0.49, seed: 7 },
  { key: "usd", flag: "🇺🇸", name: "원/달러", v: 1350.2, c: 3.2, p: 0.24, seed: 11 },
];
export const MACRO = [["국고채 3년", "2.61%", "-0.02"], ["미국채 10년", "4.18%", "+0.03"], ["금 (g)", "128,450원", "+0.6%"], ["WTI", "$71.2", "-0.8%"]];

/* 최신 업데이트 */
export type UpKind = "공시" | "뉴스" | "주가";
export type Upd = { code: string; kind: UpKind; title: string; when: string; src: string; memo?: string };
export const UPDATES: Upd[] = [
  { code: "005930", kind: "공시", title: "자기주식 취득 결정 관련 공시", when: "2시간 전", src: "DART", memo: "자사주 매입 나오면 다시 보기" },
  { code: "005930", kind: "뉴스", title: "HBM4 공급 확대 기대감", when: "1일 전", src: "한국경제" },
  { code: "005930", kind: "주가", title: "주가 +2.1% 상승", when: "3시간 전", src: "시세" },
  { code: "000660", kind: "공시", title: "신규 시설투자 관련 공시", when: "2시간 전", src: "DART", memo: "실적 나오면 다시 보기" },
  { code: "000660", kind: "뉴스", title: "HBM4 공급 확대 기대감", when: "1일 전", src: "한국경제", memo: "요즘 반도체 분위기 좋아 보여" },
  { code: "000660", kind: "주가", title: "주가 +7.1% 상승", when: "2일 전", src: "시세" },
  { code: "035420", kind: "공시", title: "사업보고서 제출 관련 공시", when: "1시간 전", src: "DART" },
  { code: "035420", kind: "뉴스", title: "AI 검색 서비스 개편 기대감", when: "5시간 전", src: "매일경제" },
  { code: "035420", kind: "주가", title: "주가 +1.3% 상승", when: "1일 전", src: "시세" },
];
/* 종목별 새 소식 수 (홈 요약 · 업데이트 위젯 · 넛지가 같이 씀) — 홈 '업데이트' 위젯 숫자와 같음 */
export const NEW_N: Record<string, number> = { "005930": 2, "000660": 3, "035420": 0 };
export const SAMSUNG_TIMELINE: [UpKind, string, string][] = [
  ["공시", "자기주식 취득 결정 관련 주요사항 보고", "DART · 10분 전"], ["뉴스", "차세대 HBM 패키징 투자 확대 발표", "뉴스 · 45분 전"],
  ["주가", "장중 2.1% 상승, 거래량 증가", "시세 · 2시간 전"], ["공시", "분기보고서 제출 및 실적 전망 공시", "DART · 4시간 전"],
  ["뉴스", "파운드리 신규 수주 기대감 확대", "뉴스 · 1일 전"], ["주가", "외국인 순매수 전환, 종가 1.4% 상승", "시세 · 2일 전"],
  ["뉴스", "반도체 업황 회복 전망 리포트 발간", "뉴스 · 3일 전"], ["공시", "사업보고서 정정 공시", "DART · 4일 전"],
  ["뉴스", "AI 반도체 생태계 협력 확대", "뉴스 · 5일 전"], ["주가", "기관 순매수 유입, 주가 0.8% 상승", "시세 · 6일 전"],
  ["공시", "현금배당 결정 공시", "DART · 1주 전"],
];

/* 뉴스 위젯 (매일경제·한국경제·서울경제·연합뉴스만) */
export const NEWS = {
  head: { src: "연합뉴스", t: "반도체 강세에 코스피 상승 출발", when: "13:12 · 방금" },
  list: [["12:48", "SK하이닉스, HBM4 공급 확대 기대감에 강세", "한국경제"], ["11:30", "외국인, 이틀 연속 반도체 순매수", "매일경제"], ["10:05", "3분기 실적 시즌 개막… IT·반도체 주목", "서울경제"], ["09:41", "원·달러 환율, 하락 출발", "연합뉴스"], ["08:52", "삼성전자, 실적 발표 앞두고 관망세", "한국경제"]] as [string, string, string][],
};
export const SCHEDULE = [["11.13 (금)", "삼성전자 분기 배당 기준일", "삼성전자"], ["11.17 (화)", "한국은행 금융통화위원회", "시장"], ["11.18 (수)", "미국 소비자물가 발표", "시장"], ["11.20 (금)", "옵션 만기일", "시장"]];

/* 메모 (T3 종이) */
export type TL = { kind: UpKind | "edit" | "first" | "start"; date: string; title?: string; body?: string; src?: string; old?: { when: string; title: string; body: string } };
export type Memo = { id: number; code: string; date: string; title: string; body: string; color: ColorKey; ai: boolean; pinned: boolean; badge: number; col: number; tracks?: string; timeline?: TL[]; pinnedAt?: number };
/* 보드 6 · 메모 팝업 1~5 · AI 업데이트(Figma 2.5) 문구 그대로. 본문 줄바꿈은 팝업 그대로(\n), 카드에선 이어 붙임 */
export const MEMOS: Memo[] = [
  { id: 1, code: "000660", date: "10.01", title: "실적 나오면 다시 보기", body: "다음 분기 실적 확인하고\n추가 매수 생각해보기.", color: "yellow", ai: true, pinned: true, badge: 2, col: 0, tracks: "공시·뉴스 1개",
    timeline: [
      { kind: "뉴스", date: "10월 15일", title: "HBM4 공급 확대 소식이 나왔어요", body: "주요 고객사 대상 HBM4 공급 물량을 늘린다는 기사가 나왔어요. 메모에 적은 '실적'과 관련 있는 소식이에요.", src: "출처  한국경제 · 2026. 10. 15. 08:40" },
      { kind: "공시", date: "9월 29일", title: "3분기 실적 발표가 예정돼 있어요", body: "10월 24일 3분기 경영실적 발표(잠정) 예정 공시가 올라왔어요.", src: "출처  DART · 2026. 09. 29. 17:05" },
      { kind: "first", date: "10.01", old: { when: "10월 1일 · 처음 작성한 메모", title: "실적 나오면 다시 보기", body: "다음 분기 실적 확인하고 추가 매수 생각해보기." } },
      { kind: "start", date: "10월 1일" },
    ] },
  { id: 2, code: "000660", date: "10.03", title: "요즘 반도체 분위기 좋아 보여", body: "AI 수요 이야기 계속 나와서\n기대감 있는 것 같음.", color: "blue", ai: true, pinned: false, badge: 1, col: 1, tracks: "공시·뉴스 1개",
    timeline: [
      { kind: "뉴스", date: "10월 15일", title: "HBM4 공급 확대 소식이 나왔어요", body: "AI 서버용 HBM 수요가 이어진다는 기사예요.", src: "출처  한국경제 · 2026. 10. 15. 08:40" },
      { kind: "first", date: "10.03", old: { when: "10월 3일 · 처음 작성한 메모", title: "요즘 반도체 분위기 좋아 보여", body: "AI 수요 이야기 계속 나와서 기대감 있는 것 같음." } },
      { kind: "start", date: "10월 3일" },
    ] },
  { id: 3, code: "000660", date: "09.25", title: "15만원 밑으로 오면 다시 생각", body: "지지선 근처 오면\n분할 매수 고민해보기.", color: "green", ai: true, pinned: true, badge: 0, col: 2, tracks: "가격 조건 1개",
    timeline: [
      { kind: "뉴스", date: "10월 15일", title: "HBM4 공급 확대 소식이 나왔어요", body: "HBM4 공급 확대 보도와 외국인 매수 소식이 있었어요. 주가가 15만원 조건가에서 멀어진 배경을 살펴볼 수 있어요.", src: "출처  네이버 뉴스 · 2026. 10. 15. 08:40" },
      { kind: "주가", date: "10월 11일", title: "15만원 조건가에서 멀어졌어요", body: "종가 180,500원 · 조건가보다 30,500원(20.3%) 높아요. 아직 설정한 15만원 조건에 도달하지 않았어요.", src: "시세  토스증권 · 2026. 10. 11. 15:30\n설정한 가격 조건과 비교해 자동 계산했어요." },
      { kind: "edit", date: "10.06", old: { when: "10월 6일 21:14 · 수정 당시 메모", title: "15만원 밑으로 오면 다시 생각", body: "지지선 근처 오면 분할 매수 고민해보기." } },
      { kind: "주가", date: "10월 2일", title: "15만원 조건가에 가까워졌어요", body: "최근 5거래일 동안 6.2% 내렸어요. 종가 156,800원으로, 설정한 15만원보다 6,800원(4.5%) 높아요.", src: "시세  토스증권 · 2026. 10. 02. 15:30\n설정한 가격 조건과 비교해 자동 계산했어요." },
      { kind: "공시", date: "9월 29일", title: "3분기 실적 발표가 예정돼 있어요", body: "10월 24일 실적 발표 예정 소식이에요. 가격 조건과 함께 살펴볼 일정으로 연결했어요.", src: "출처  DART · 2026. 09. 29. 17:05" },
      { kind: "first", date: "09.25", old: { when: "9월 25일 22:31 · 처음 작성한 메모", title: "15만원 밑으로 오면 다시 생각", body: "지지선 근처 오면 다시 보기." } },
      { kind: "start", date: "9월 25일" },
    ] },
  { id: 4, code: "000660", date: "10.09", title: "삼성전자랑 같이 비교해보기", body: "두 종목 주가 흐름 비교해서\n판단하기.", color: "purple", ai: false, pinned: false, badge: 0, col: 1 },
  { id: 5, code: "000660", date: "10.05", title: "너무 급하게 따라 사지 말기", body: "지금은 좀 지켜보고\n조금 더 확인한 뒤에 들어가기.", color: "pink", ai: false, pinned: false, badge: 0, col: 2 },
  { id: 6, code: "005930", date: "10.12", title: "자사주 매입 나오면 다시 보기", body: "주주환원 나오는지 확인하고 판단하기.", color: "yellow", ai: false, pinned: true, badge: 0, col: 0, tracks: "공시·뉴스 1개",
    timeline: [{ kind: "공시", date: "11월 5일", title: "자기주식 취득 결정 공시가 나왔어요", body: "메모에서 기다리던 주주환원 공시예요.", src: "출처  DART · 2026. 11. 05." }, { kind: "first", date: "10.12", old: { when: "10월 12일 · 처음 작성한 메모", title: "자사주 매입 나오면 다시 보기", body: "주주환원 나오는지 확인하고 판단하기." } }, { kind: "start", date: "10월 12일" }] },
  { id: 7, code: "005930", date: "10.20", title: "파운드리 수주 소식 지켜보기", body: "대형 고객 수주 나오면 다시 보기.", color: "blue", ai: false, pinned: false, badge: 0, col: 1 },
  { id: 8, code: "035420", date: "10.18", title: "AI 검색 반응 보기", body: "서비스 개편 후 이용자 반응 확인.", color: "green", ai: true, pinned: false, badge: 0, col: 0, tracks: "공시·뉴스 1개", timeline: [{ kind: "first", date: "10.18", old: { when: "10월 18일 · 처음 작성한 메모", title: "AI 검색 반응 보기", body: "서비스 개편 후 이용자 반응 확인." } }, { kind: "start", date: "10월 18일" }] },
];
export const CHECKLIST = [{ t: "실적 발표 전 확인", d: false }, { t: "관련 뉴스 다시 확인", d: true }, { t: "가격 떨어지면 다시 보기", d: false }, { t: "삼성전자랑 같이 비교해보기", d: false }];

/* 투자 기록 */
export type Journal = { id: number; title: string; date: string; full: string; body: string[]; html?: string; todo: { t: string; d: boolean }[]; pinned?: boolean };
export const JOURNAL: Journal[] = [
  { id: 1, title: "10/13 투자 복기", date: "10월 13일", full: "2026년 10월 13일 오후 6:20", body: ["오늘 반도체 업종이 강세를 보였다. SK하이닉스는 HBM4 공급 확대 기대감에 상승했고, 삼성전자는 장 초반 약세 뒤 회복했다.", "잘한 점: 급등 구간에서 추격 매수를 하지 않았다.", "아쉬운 점: 실적 발표 전에 체크리스트를 다시 확인하지 못했다."], todo: [{ t: "실적 발표일 확인하기", d: false }, { t: "분할 매수 계획 세우기", d: false }] },
  { id: 2, title: "10/08 실적 발표 전 점검", date: "10월 8일", full: "2026년 10월 8일 오후 9:02", body: ["발표일 확인하고 체크리스트 정리.", "컨센서스 대비 가이던스 문구를 꼭 볼 것."], todo: [{ t: "가이던스 문구 확인", d: true }] },
  { id: 3, title: "10/01 매수 전략 메모", date: "10월 1일", full: "2026년 10월 1일 오전 8:40", body: ["급하게 따라 사지 않기.", "15만원 근처에서만 분할로 접근."], todo: [] },
  { id: 4, title: "09/25 손절 기준 정리", date: "9월 25일", full: "2026년 9월 25일 오후 11:10", body: ["지지선 근처에서 분할 매수 고민.", "-10%면 이유를 다시 적고 판단하기."], todo: [] },
];

/* 휴지통 — memo/stock: API 모드에서 지운 원래 항목 (복원할 때 다시 저장) */
export type TrashItem = { icon: string; t: string; s: string; type: string; memo?: Memo; stock?: Stock };
export const TRASH: TrashItem[] = [
  { icon: "memo", t: "20만원 밑으로 오면 다시 생각", s: "SK하이닉스 / 메모 · 2시간 전 삭제", type: "메모" },
  { icon: "journal", t: "10/08 실적 발표 전 점검", s: "투자 기록 · 어제 삭제", type: "투자 기록" },
  { icon: "memo", t: "삼성전자랑 같이 비교해보기", s: "SK하이닉스 / 메모 · 3일 전 삭제", type: "메모" },
  { icon: "stock", t: "현대차", s: "종목 · 6일 전 삭제", type: "종목" },
];

/* 퀴즈 */
export const QUIZ_OX = { label: "어제(11.11 수) 증시 퀴즈", q: "어제 코스피는 전날보다 올랐다.", answer: "O" as const, exp: "어제 코스피는 2,650.35로 전날보다 1.2% 올라 마감했어요.", concept: "지수의 등락률은 전날 종가와 비교해 계산해요.", src: "출처 · 한국거래소 지수 종가 (11.11 기준)" };
export const QUIZ_4 = { label: "어제(11.11 수) 증시 퀴즈", q: "어제 코스피에서 거래대금이\n가장 많았던 종목은?", options: ["SK하이닉스", "삼성전자", "현대차", "LG에너지솔루션"], answer: 0, exp: "어제 SK하이닉스 거래대금은 7,512억 원으로 코스피에서 가장 많았어요.", concept: "거래대금은 하루 동안 거래된 주식 금액을 모두 더한 값이에요." };

/* 실험실 */
export const LAB_VARS = [["원/달러 환율", "하락"], ["국제유가(WTI)", "유지"], ["한국 기준금리", "유지"], ["미국 10년물 국채금리", "상승"]] as [string, "상승" | "유지" | "하락"][];

/* 오디오 */
export const AUDIO_CHAPTERS = [["0:00", "어제 증시 요약"], ["0:28", "SK하이닉스"], ["1:10", "삼성전자"], ["1:48", "NAVER · 새 소식 없음"], ["2:02", "마무리"]];
export const AUDIO_SCRIPT = [
  ["A · 메인", "오늘은 고르신 종목 3곳의 소식을 살펴볼게요. 먼저 어제 증시부터요."],
  ["B · 해설", "어제 코스피는 1.2% 올랐고, 원/달러 환율은 조금 내렸어요."],
  ["A · 메인", "SK하이닉스로 가 볼까요? 전에 HBM 수요 메모를 남기셨는데, 관련 소식이 있다고요?"],
  ["B · 해설", "네. 10월 30일 신규 시설투자 공시가 나왔고, 추적 중인 HBM 항목과 연결됐어요."],
  ["A · 메인", "그럼 메모와는 어떤 관계로 보면 될까요?"],
];
