import type { JBlock, JournalEntry } from './Journal.types';

/*
 * 투자 기록 mock — 숫자·날짜·문장은 여기 한 곳에서만.
 * 원본 journal.html NOTES (11.17 웹 통일 4개 · 오늘 = 2026.11.5) 그대로. 단 1번 기록의 시장 해석 문장
 * ('강세를 보였다' · '기대감에 상승' · '장 초반 약세 뒤 회복')은 사실 문장으로 바꿈.
 * 연결 단계: 날짜 글자(date · web_date · full)와 묶음(group)은 created_at·updated_at 으로 계산, 개수는 목록 길이.
 */
const T = (text: string): JBlock => ({ s: 'title', text });
const B = (text: string): JBlock => ({ s: 'body', text });
const H = (text: string): JBlock => ({ s: 'head', text });
const C = (text: string, done = false): JBlock => ({ s: 'body', text, check: done });

export const mockJournal: JournalEntry[] = [
  {
    id: 'j1',
    title: '10/13 투자 복기',
    date: '2026. 10. 13.',
    web_date: '10월 13일',
    full: '2026년 10월 13일 오후 6:20',
    group: '지난 30일',
    pinned: false,
    blocks: [
      T('10/13 투자 복기'),
      B('오늘 반도체 업종 종목이 올랐다.\nSK하이닉스는 HBM4 공급 확대 보도가 나온 날 올랐고,\n삼성전자는 전날과 비슷하게 마감했다.'),
      B('잘한 점: 급등 구간에서 추격 매수를 하지 않았다.'),
      B('아쉬운 점: 실적 발표 전에\n체크리스트를 다시 확인하지 못했다.'),
      H('다음 액션'),
      C('실적 발표일 확인하기'),
      C('분할 매수 계획 세우기'),
    ],
  },
  {
    id: 'j2',
    title: '10/08 실적 발표 전 점검',
    date: '2026. 10. 8.',
    web_date: '10월 8일',
    full: '2026년 10월 8일 오후 9:02',
    group: '지난 30일',
    pinned: false,
    blocks: [T('10/08 실적 발표 전 점검'), B('발표일 확인하고 체크리스트 정리.'), B('컨센서스 대비 가이던스 문구를 꼭 볼 것.'), C('가이던스 문구 확인', true)],
  },
  {
    id: 'j3',
    title: '10/01 매수 전략 메모',
    date: '2026. 10. 1.',
    web_date: '10월 1일',
    full: '2026년 10월 1일 오전 8:40',
    group: '10월',
    pinned: false,
    blocks: [T('10/01 매수 전략 메모'), B('급하게 따라 사지 않기.'), B('15만원 근처에서만 분할로 접근.')],
  },
  {
    id: 'j4',
    title: '09/25 손절 기준 정리',
    date: '2026. 9. 25.',
    web_date: '9월 25일',
    full: '2026년 9월 25일 오후 11:10',
    group: '9월',
    pinned: false,
    blocks: [T('09/25 손절 기준 정리'), B('지지선 근처에서 분할 매수 고민.'), B('-10%면 이유를 다시 적고 판단하기.')],
  },
];

/** 날짜 묶음 순서 (원본 GO) */
export const mockJournalGroupOrder = ['오늘', '어제', '지난 7일', '지난 30일', '10월', '9월'];

/** 검색칸을 눌렀을 때 '최근 기록'으로 보여 줄 개수 (원본 NOTES.slice(0,3)) */
export const mockJournalRecentCount = 3;

/** 처음 들어올 때 뼈대를 보여 주는 시간 (원본 loadList 900ms) — 연결 단계에서는 불러오기 끝날 때까지 */
export const mockJournalLoadMs = 900;

/** 새로 쓰거나 고친 기록에 붙는 '지금' (원본 openNew · saveCur: 2026.11.5 오후 4:20 · 묶음 '오늘'). 연결 단계에서 서버 시각으로 */
export const mockJournalNow = { date: '오후 4:20', web_date: '11월 5일', full: '2026년 11월 5일 오후 4:20', group: '오늘' };
