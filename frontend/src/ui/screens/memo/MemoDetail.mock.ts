import type { MemoVersion } from '@/types/models';
import { mockBoardMemos } from '@/ui/screens/board/MemoBoard.mock';
import type { AiTrackItem, MemoFeedItem } from './MemoDetail.types';

/**
 * 메모 상세 예시 데이터 — 보드 예시(MemoBoard.mock)의 m1~m5 와 같은 메모.
 * 소식·이력 문장은 원본 앱 memo.html notes[].feed · revs 를 옮김. 문구 규칙(7번)으로 바꾼 곳은 보고서 '바꾼 문구'에.
 * 날짜는 웹 예시 계정 기준 (보드와 같음).
 */
const at = (d: string, t = '09:00') => `2026-${d}T${t}:00+09:00`;
const ver = (version: number, d: string, title: string, body: string): MemoVersion => ({ version, title, body, saved_at: at(d) });

/* 수정 이력 (최신이 앞) — 원본 revs. m3 만 한 번 고침 */
export const mockVersions: Record<string, MemoVersion[]> = {
  m1: [ver(1, '10-03', '실적 나오면 다시 보기', '다음 분기 실적 확인하고\n비중 다시 점검해보기.')],
  m2: [ver(1, '10-05', '요즘 반도체 분위기 좋아 보여', 'HBM 수요 이야기가 계속 나오는지\n지켜보기.')],
  m3: [
    ver(2, '10-08', '15만원 밑으로 오면 다시 생각', '지지선 근처 오면\n비중 다시 점검해보기.'),
    ver(1, '09-27', '15만원 밑으로 오면 다시 생각', '지지선 근처 오면\n다시 보기.'),
  ],
  m4: [ver(1, '10-11', '삼성전자랑 같이 비교해보기', '두 종목 주가 흐름 비교해서\n판단하기.')],
  m5: [ver(1, '10-07', '너무 급하게 판단하지 말기', '지금은 좀 지켜보고\n조금 더 확인한 뒤에 다시 보기.')],
};

const NEWS_HBM = { kind: '뉴스' as const, headline: 'HBM4 공급 확대 소식이 나왔어요', article_title: 'SK하이닉스, HBM4 공급 물량 확대', url: 'https://news.naver.com' };
const DART_Q3 = {
  kind: '공시' as const,
  headline: '3분기 실적 발표가 예정돼 있어요',
  source: 'DART · 2026. 10. 13. 17:05',
  url: 'https://dart.fss.or.kr',
  quote: '2026년 3분기 경영실적 발표(잠정) — 일시: 2026년 10월 24일',
  quote_mark: '일시: 2026년 10월 24일',
};

/* AI 업데이트 — 원본 feed. 안 읽음 수는 보드의 배지(unread_updates)와 같음 */
export const mockFeed: Record<string, MemoFeedItem[]> = {
  m1: [
    { ...NEWS_HBM, id: 'f1', at: at('10-15', '08:40'), summary: '메모에서 확인하려던 "실적 발표 내용" 관련 뉴스예요.', source: '한국경제 · 2026. 10. 15. 08:40', memo_version: 1, unread: true },
    { ...DART_Q3, id: 'f2', at: at('10-13', '17:05'), summary: '10월 24일 3분기 경영실적 발표(잠정) 예정 공시가 올라왔어요.', memo_version: 1, unread: false },
  ],
  m2: [{ ...NEWS_HBM, id: 'f3', at: at('10-15', '08:40'), summary: '메모에서 확인하려던 "HBM 수요" 관련 뉴스예요.', source: '한국경제 · 2026. 10. 15. 08:40', memo_version: 1, unread: true }],
  m3: [
    { ...NEWS_HBM, id: 'f4', at: at('10-15', '08:40'), summary: '메모에서 확인하려던 "15만원 조건가" 관련 뉴스예요.', source: '네이버 뉴스 · 2026. 10. 15. 08:40', memo_version: 2, unread: false },
    {
      id: 'f5',
      kind: '주가',
      at: at('10-11', '15:30'),
      headline: '15만원 조건가에서 멀어졌어요',
      summary: '종가 180,500원 · 조건가보다 30,500원(20.3%) 높아요. 아직 설정한 15만원 조건에 도달하지 않았어요.',
      source: 'KIS · 2026. 10. 11. 종가',
      url: null,
      memo_version: 2,
      unread: false,
    },
    {
      id: 'f6',
      kind: '주가',
      at: at('10-02', '15:30'),
      headline: '15만원 조건가에 가까워졌어요',
      summary: '최근 5거래일 동안 6.2% 내렸어요. 종가 156,800원으로, 설정한 15만원보다 6,800원(4.5%) 높아요.',
      source: 'KIS · 2026. 10. 02. 종가',
      url: null,
      memo_version: 1,
      unread: false,
    },
    { ...DART_Q3, id: 'f7', at: at('09-29', '17:05'), source: 'DART · 2026. 09. 29. 17:05', summary: '10월 24일 실적 발표 예정 소식이에요. 가격 조건과 함께 살펴볼 일정으로 연결했어요.', memo_version: 1, unread: false },
  ],
  m4: [],
  m5: [],
};

/* 추적 항목 (서버가 정함 — 원본 items · extract 결과) */
export const mockTrackItems: Record<string, AiTrackItem[]> = {
  m1: [{ kind: 'fact', label: '실적 발표 내용', quote: '다음 분기 실적 확인하고' }],
  m2: [{ kind: 'fact', label: 'HBM 매출·공급 현황', quote: 'HBM 수요 이야기가 계속 나오는지' }],
  m3: [{ kind: 'price', label: '15만원 미만이 되면 알려드려요', price: 150000, direction: '미만', quote: '15만원 밑으로 오면 다시 생각' }],
  /* 원본 extract: '삼성전자랑 같이 비교해보기' 에서는 찾은 항목 없음 → 항목 없음 화면 */
  m4: [],
  m5: [],
};

/**
 * 새 메모의 추적 항목 흉내 — 원본 체험판 extract() 규칙 그대로 (○○만원 + 아래/위 → 가격 조건, HBM·실적·보고서·배당 등 → 공시·뉴스).
 * 실제는 서버 추출 결과 (P0-2).
 */
export function mockExtract(title: string, body: string): AiTrackItem[] {
  const t = `${title}\n${body}`;
  const out: AiTrackItem[] = [];
  let m = t.match(/(\d+)\s*만\s*원?\S*\s*(아래|밑|미만|이하)/);
  let dir: '미만' | '이상' = '미만';
  if (!m) {
    m = t.match(/(\d+)\s*만\s*원?\S*\s*(위|이상|넘)/);
    dir = '이상';
  }
  if (m) {
    const line = (t.split('\n').find((l) => l.includes(`${m![1]}만`)) ?? m[0]).trim();
    out.push({ kind: 'price', label: `${m[1]}만원 ${dir === '미만' ? '미만이' : '이상이'} 되면 알려드려요`, price: Number(m[1]) * 10000, direction: dir, quote: line });
  }
  const KW: [string, string][] = [['HBM', 'HBM 매출·공급 현황'], ['배당', '배당 정책'], ['수주', '수주 소식'], ['가이던스', '실적 가이던스'], ['실적', '실적 발표 내용'], ['정기보고서', '정기보고서 내용'], ['분기보고서', '분기보고서 내용'], ['커머스', '커머스 매출 흐름']];
  const hit = KW.find(([k]) => t.includes(k));
  if (hit) out.unshift({ kind: 'fact', label: hit[1], quote: (t.split('\n').find((l) => l.includes(hit[0])) ?? t).trim() });
  return out;
}

/** 예시 '오늘' (편집해서 저장하면 이 날짜로 수정) */
export const mockToday = '2026-11-19T09:00:00+09:00';

export const mockDetailStockName = 'SK하이닉스';
export const mockLastChecked = '11.18 장 마감 후';

export function mockMemoById(id: string) {
  return mockBoardMemos.find((m) => m.id === id) ?? mockBoardMemos[0];
}
