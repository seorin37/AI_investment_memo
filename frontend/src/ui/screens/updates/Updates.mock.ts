import type { Memo, MemoVersion } from '@/types/models';
import { mockBoardMemos } from '@/ui/screens/board/MemoBoard.mock';
import { mockFeed, mockVersions } from '@/ui/screens/memo/MemoDetail.mock';
import type { MemoFeedItem } from '@/ui/screens/memo/MemoDetail.types';
import type { UpdateItem, UpdateStock } from './Updates.types';

/**
 * 업데이트 예시 — SK하이닉스 소식은 ④ 메모 상세 예시(MemoDetail.mock)의 소식을 그대로 씀 (근거 상세까지 같은 내용).
 * 삼성전자 · 네이버 소식은 웹 원본 예시 계정의 업데이트(삼성 자사주 · 네이버 AI 검색)를 메모 소식 모양으로 옮김.
 * 읽지 않은 소식: SK하이닉스 2 · 네이버 1 (홈 ② · 내 종목과 같음).
 */
export const mockUpdatesNow = '2026-11-19T09:00:00+09:00';

export const mockUpdateStocks: UpdateStock[] = [
  { stock_code: '000660', name: 'SK하이닉스', logo: 'S', logo_bg: '#EA002C', market: 'KOSPI', status: 'holding', ai_ready: true },
  { stock_code: '005930', name: '삼성전자', logo: '삼', logo_bg: '#1428A0', market: 'KOSPI', status: 'watching', ai_ready: true },
  { stock_code: '035420', name: '네이버', logo: '네', logo_bg: '#03C75A', market: 'KOSPI', status: 'watching', ai_ready: true },
];

const at = (d: string, t: string) => `2026-${d}T${t}:00+09:00`;
const other = (id: string, code: string, color: Memo['color'], created: string, title: string, body: string): Memo => ({
  id,
  kind: 'memo',
  stock_code: code,
  title,
  body,
  tags: [],
  color,
  pinned: false,
  ai_linked: true,
  ai_linked_at: `${created}T09:00:00+09:00`,
  price_conditions: [],
  unread_updates: 0,
  position: 0,
  created_at: `${created}T09:00:00+09:00`,
  updated_at: `${created}T09:00:00+09:00`,
});

/** 다른 종목의 AI 연결 메모 (원본 seed.ts) */
export const mockOtherMemos: Memo[] = [
  other('m6', '005930', 'yellow', '2026-10-14', '자사주 매입 나오면 다시 보기', '주주환원 나오는지 확인하고 판단하기.'),
  other('m7', '035420', 'green', '2026-10-20', 'AI 검색 반응 보기', '서비스 개편 후 이용자 반응 확인.'),
];
export const mockOtherVersions: Record<string, MemoVersion[]> = {
  m6: [{ version: 1, title: '자사주 매입 나오면 다시 보기', body: '주주환원 나오는지 확인하고 판단하기.', saved_at: '2026-10-14T09:00:00+09:00' }],
  m7: [{ version: 1, title: 'AI 검색 반응 보기', body: '서비스 개편 후 이용자 반응 확인.', saved_at: '2026-10-20T09:00:00+09:00' }],
};
export const mockOtherFeed: Record<string, MemoFeedItem[]> = {
  m6: [
    {
      id: 's1',
      kind: '공시',
      at: at('11-18', '16:10'),
      headline: '자기주식 취득 결정 공시가 나왔어요',
      summary: '자기주식을 취득하기로 결정했다는 공시예요. 취득 예정 수량과 기간은 원문에서 확인해 주세요.',
      source: 'DART · 2026. 11. 18. 16:10',
      url: 'https://dart.fss.or.kr',
      report: '주요사항보고서(자기주식취득결정)',
      quote: '회사는 자기주식 취득을 결정하였으며 취득 예정 기간은 아래와 같습니다.',
      quote_mark: '자기주식 취득을 결정',
      memo_version: 1,
      unread: false,
    },
    {
      id: 's2',
      kind: '뉴스',
      at: at('11-05', '14:12'),
      headline: '삼성전자 자사주 관련 신규 계약 소식이 나왔어요',
      article_title: '삼성전자 자사주 관련 신규 계약 소식',
      summary: '메모에서 확인하려던 "자사주 매입" 관련 뉴스예요.',
      source: '한국경제 · 2026. 11. 05. 14:12',
      provider: '한국경제 · 네이버 뉴스',
      url: 'https://news.naver.com',
      memo_version: 1,
      unread: false,
    },
  ],
  m7: [
    {
      id: 'n2',
      kind: '공시',
      at: at('11-17', '17:30'),
      headline: '기업설명회(IR) 개최 공시가 나왔어요',
      summary: '기업설명회를 연다는 공시예요. 일시와 장소는 원문에서 확인해 주세요.',
      source: 'DART · 2026. 11. 17. 17:30',
      url: 'https://dart.fss.or.kr',
      report: '기업설명회(IR) 개최(안내공시)',
      quote: '회사는 기업설명회(IR)를 개최하며, 일시는 아래와 같습니다.',
      quote_mark: '기업설명회(IR)를 개최',
      memo_version: 1,
      unread: false,
    },
    {
      id: 'n1',
      kind: '뉴스',
      at: at('11-11', '07:02'),
      headline: '네이버, AI 검색 관련 보도가 나왔어요',
      article_title: '네이버, AI 검색 관련 보도 뒤 거래 늘어',
      summary: '메모에서 확인하려던 "AI 검색 반응" 관련 뉴스예요.',
      source: '매일경제 · 2026. 11. 11. 07:02',
      provider: '매일경제 · 네이버 뉴스',
      url: 'https://news.naver.com',
      memo_version: 1,
      unread: true,
    },
  ],
};

const allMemos = [...mockBoardMemos, ...mockOtherMemos];
/** 근거 상세·이력 화면이 메모를 찾을 때 (보드 메모 + 다른 종목 메모) */
export const findMemo = (id: string) => allMemos.find((m) => m.id === id) ?? mockBoardMemos[0];
export const feedOf = (id: string): MemoFeedItem[] => mockFeed[id] ?? mockOtherFeed[id] ?? [];
export const versionsOf = (id: string): MemoVersion[] => mockVersions[id] ?? mockOtherVersions[id] ?? [];

/**
 * 업데이트 목록 (최신이 앞). 같은 기사가 메모 여러 개에 붙으면 한 줄로 (처음 붙은 메모 기준 — 원본도 소식 한 건 = 한 줄).
 * SK하이닉스 읽지 않은 소식 2건(홈 ② 와 같게): HBM4 뉴스 + 3분기 실적 공시(f2) 를 안 읽음으로.
 */
const UNREAD_HERE = new Set(['f2']);
export const mockUpdateItems: UpdateItem[] = allMemos
  .flatMap((m) => feedOf(m.id).map((f) => ({ ...f, unread: f.unread || UNREAD_HERE.has(f.id), stock_code: m.stock_code, memo_id: m.id, memo_title: m.title, memo_color: m.color })))
  .filter((u, i, all) => all.findIndex((x) => x.stock_code === u.stock_code && x.headline === u.headline && x.at === u.at) === i)
  .sort((a, b) => b.at.localeCompare(a.at));
