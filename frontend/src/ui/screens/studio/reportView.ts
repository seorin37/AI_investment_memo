import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { ApiError, api } from '@/api';
import { env } from '@/config/env';
import { qk, useMyStocks } from '@/hooks/queries';
import { BRAND_LOGOS } from '@/lib/brandLogos';
import type { StudioItem } from '@/types/models';
import { mockReport, mockReportStocks, type ReportStock, type ReportWatch } from './Studio.mock';
import type { MadeItem } from './Studio.types';

/** 주간보고서 머리 (화면 Rep 모양 = mockReport). 서버 보고서는 이 모양으로 바꿔 쓴다 */
export type ReportRep = typeof mockReport;

const WD = ['월', '화', '수', '목', '금', '토', '일'];
const dayLabel = (iso: string) => {
  const d = new Date(`${iso}T00:00:00`);
  return `${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')} ${WD[(d.getDay() + 6) % 7]}`;
};

type ServerStock = Omit<ReportStock, 'logo' | 'logo_bg' | 'logo_ink' | 'sc' | 'st' | 'memo'> & {
  trade_dates?: string[];
  memo?: { memo_id?: string; title: string; meta: string; body: string; linked_count?: number } | null;
};
type ServerReport = {
  week: string; title: string; range: string; made_at: string; as_of?: string;
  market?: { name: string; value: string; pct: number }[];
  market_summary?: string;
  flow?: { day: string; text: string; src: string }[];
  stocks: ServerStock[];
  sources?: { text: string; code: string }[];
  source_note?: string;
};

/** 서버 보고서(studio_items.content, backend/app/studio_report/build.py) → 화면 (2026-11-23). 로고 색은 프론트 표(brandLogos) */
export function fromServerReport(c: ServerReport, added?: Record<string, string>): { rep: ReportRep; stocks: ReportStock[] } {
  const first = c.stocks[0];
  const days = (first?.trade_dates ?? []).map(dayLabel);
  const rep: ReportRep = {
    ...mockReport,
    week: c.week,
    title: c.title,
    range: c.range,
    made_at: c.made_at,
    days: days.length ? days : mockReport.days,
    days_short: days.length ? days.map((d) => d.split(' ')[1]) : mockReport.days_short,
    market: c.market ?? [],
    flow: c.flow ?? [],
    market_summary: c.market_summary ?? '',
    summary_default: '',
    sources: c.sources ?? [],
    source_note: c.source_note ?? mockReport.source_note,
  };
  const stocks: ReportStock[] = c.stocks.map((s) => {
    const b = BRAND_LOGOS[s.stock_code];
    const bg = b?.logo_bg ?? '#575B63';
    return {
      ...s,
      logo: b?.logo ?? s.name.slice(0, 1),
      logo_bg: bg,
      logo_ink: b?.logo_ink,
      sc: bg,
      st: '#F5F6F8',
      memo: s.memo ? { bg: '#FCEAAA', ink: '#3F3A2A', ...s.memo } : undefined,
      watch: (s.watch ?? []).map((w) => ({ ...w, added: !!(added && w.sid && added[`${s.stock_code}:${w.sid}`]) })),
    } as ReportStock;
  });
  return { rep, stocks };
}

/** 서버 만든 항목(kind=report) → 화면 MadeItem */
export function fromServerReportItem(s: StudioItem): MadeItem {
  const view = fromServerReport(s.content as unknown as ServerReport, (s.content as { added?: Record<string, string> }).added);
  const market = !!(s.content as { market_on?: boolean }).market_on;
  const sub = `주간보고서 · ${view.stocks.length}종목 · ${view.rep.made_at.split(' ')[0]}`;
  return { id: s.id, server: true, kind: 'report', title: s.title, sub, meta: sub, left: `${s.days_left}일 뒤 삭제`,
    codes: view.stocks.map((x) => x.stock_code), market, report: view };
}

/** 보고서 화면에 줄 값. 서버 보고서면 그 내용, 아니면(mock 모드·예시) 지금처럼 mock 3종목 */
export function reportView(item: MadeItem | undefined): { rep: ReportRep; stocks: ReportStock[]; allDefault: boolean; market: boolean } {
  if (item?.report) return { ...item.report, allDefault: false, market: !!item.market };
  const stocks = mockReportStocks.filter((s) => (item?.codes ?? mockReportStocks.map((x) => x.stock_code)).includes(s.stock_code));
  return { rep: mockReport, stocks, allDefault: stocks.length === mockReportStocks.length, market: !!item?.market };
}

/** 만들기 창 종목 목록. 실제 모드는 내 종목 (만들기 전 '공시·뉴스 수' 미리 보기는 없음) */
export function useReportPickStocks(): { stocks: ReportStock[]; counts: boolean } {
  const mine = useMyStocks().data ?? [];
  if (env.useMock) return { stocks: mockReportStocks, counts: true };
  return {
    counts: false,
    stocks: mine.map((m) => {
      const b = BRAND_LOGOS[m.code];
      const bg = b?.logo_bg ?? '#575B63';
      return { stock_code: m.code, name: m.name, logo: b?.logo ?? m.name.slice(0, 1), logo_bg: bg, logo_ink: b?.logo_ink, sc: bg, st: '#F5F6F8',
        own: m.status === 'holding' ? '보유' : '관심', pct: 0, close: 0, prev: 0, closes: [0, 0, 0, 0, 0], yr: [0, 1], hi: '', lo: '', vol: '',
        events: [], counts: { 공시: 0, 뉴스: 0 }, story: '', items: [], watch: [] } as ReportStock;
    }),
  };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** 실제 모드 보고서 만들기: POST /studio/reports → 완성될 때까지 목록을 다시 받아 확인 (최대 2분). 완성된 항목을 돌려준다 */
export function useCreateReport() {
  const qc = useQueryClient();
  return async (codes: string[], market: boolean): Promise<MadeItem> => {
    let res;
    try {
      res = await api.createReport({ codes, market });
    } catch (e) {
      throw new Error(e instanceof ApiError ? e.message : '보고서를 만들지 못했어요');
    }
    /* 4종목 + 국내 증시면 2분을 넘기기도 해서(11-24 2분 17초) 6분까지 기다린다. 그래도 안 끝나면 실패가 아니라
       '아직 만드는 중'으로 (서버는 계속 만들고, 끝나면 만든 항목에 생긴다) */
    const until = Date.now() + 6 * 60_000;
    while (Date.now() < until) {
      const items = await api.listStudioItems();
      const it = items.find((x) => x.id === res.item_id);
      if (it?.status === 'ready') {
        qc.setQueryData(qk.studioItems, items);
        void qc.invalidateQueries({ queryKey: qk.usage });
        return fromServerReportItem(it);
      }
      if (it?.status === 'failed') throw new Error('보고서를 만들지 못했어요');
      await sleep(2000);
    }
    const pending = new Error('보고서가 아직 만들어지는 중이에요. 잠시 뒤 만든 항목에서 확인해 주세요');
    pending.name = 'ReportPending';
    for (const ms of [30_000, 90_000, 180_000]) setTimeout(() => void qc.invalidateQueries({ queryKey: qk.studioItems }), ms);   // 끝나면 만든 항목에 보이게
    throw pending;
  };
}

/**
 * 앞으로 지켜볼 것 → '메모에 추가' (2026-11-24). 웹: 종목 보드로 가서 새 메모 창을 제안의 memo_title·memo_body로 채워 연다
 * (AI 연결 켬). 앱은 NewMemoSheet 를 채워 엶. 서버 보고서면 저장 뒤 '추가됨'을 남기도록 보고서 id·키를 같이 넘긴다.
 */
export function useWatchToMemo() {
  const open = useOpenMemoDraft();
  return (stock: ReportStock, w: ReportWatch, reportId?: string) =>
    open({ code: stock.stock_code, name: stock.name, title: w.memo_title ?? w.text, body: w.memo_body ?? '',
      itemId: reportId, key: w.sid ? `${stock.stock_code}:${w.sid}` : undefined });
}

/**
 * 제안 → 메모 창 열기 (웹, 주간보고서·투자 실험실 공통, 2026-11-24). 종목 보드 새 메모 창을 제목·본문을 채우고 AI 연결을 켠 채로 연다. itemId·key가 있으면 저장 뒤 그 만든 항목에 '추가됨'을 남긴다.
 */
export function useOpenMemoDraft() {
  const router = useRouter();
  return (p: { code: string; name?: string; title: string; body: string; itemId?: string; key?: string }) => {
    const mark = p.itemId && p.key ? { wr: p.itemId, wk: p.key } : {};
    router.navigate({ pathname: '/stocks/[code]', params: { code: p.code, new: '1', nt: p.title, nb: p.body, ...mark } });
  };
}

/** 제안으로 만든 메모를 저장한 뒤 호출: 보고서에 '추가됨'을 남기고 만든 항목을 다시 받는다 (실패해도 메모는 그대로) */
export function useMarkWatchAdded() {
  const qc = useQueryClient();
  return (reportId: string | undefined, key: string | undefined, memoId: string) => {
    if (!reportId || !key || env.useMock) return;
    void api.markReportWatch(reportId, key, memoId).then(
      () => qc.invalidateQueries({ queryKey: qk.studioItems }),
      () => undefined,
    );
  };
}
