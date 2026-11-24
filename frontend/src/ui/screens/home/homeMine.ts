import type { AiUpdate, Checklist, HomeChecklistItem, HomeLayout, MyStock, WidgetType } from '@/types/models';
import type { HomeUpdateRow, HomeWidget } from './Home.types';

/** 홈 내 데이터 변환 (useHomeData). 화면 hook 과 떼어 DB 없이 테스트 (tests/home-mine.test.mjs) */
type Logo = (code: string, name: string) => Pick<HomeUpdateRow, 'logo' | 'logo_bg'>;

const TO_SERVER: Record<HomeWidget, WidgetType> = { market: 'market', updates: 'updates', news: 'news', check: 'checklist' };
const FROM_SERVER: Partial<Record<WidgetType, HomeWidget>> = { market: 'market', updates: 'updates', news: 'news', checklist: 'check' };
const KIND = { disclosure: '공시', news: '뉴스', price: '주가' } as const;

export function widgetsFrom(layout: HomeLayout | undefined, fallback: HomeWidget[]): HomeWidget[] {
  if (!layout || layout.mode === 'unset' || !layout.widgets.length) return fallback;
  return layout.widgets.flatMap((w) => (FROM_SERVER[w.type] ? [FROM_SERVER[w.type]!] : []));
}

export function layoutFrom(widgets: HomeWidget[]): HomeLayout {
  return { mode: 'template', widgets: widgets.map((w, i) => ({ id: `w${i + 1}`, type: TO_SERVER[w], span: w === 'market' ? 4 : 2 })) };
}

export function updateRows(stocks: MyStock[], feed: AiUpdate[], logoOf: Logo): HomeUpdateRow[] {
  return stocks.map((s) => {
    const u = feed.find((x) => x.stock_code === s.code); // 피드는 최신순
    return {
      stock_code: s.code,
      name: s.name,
      status: s.status,
      new_count: s.unread_updates,
      ...logoOf(s.code, s.name),
      latest: u ? { kind: KIND[u.type] ?? '뉴스', title: u.headline || u.title, memo_title: u.memo_title, memo_color: u.memo_color ?? 'yellow' } : undefined,
    };
  });
}

export function checklistsFrom(rows: HomeChecklistItem[]): Record<string, Checklist> {
  const out: Record<string, Checklist> = {};
  for (const r of rows) {
    const c = (out[r.stock_code] ??= {
      id: r.checklist_id, kind: 'checklist', stock_code: r.stock_code, title: '', position: 0, created_at: '', updated_at: '', items: [],
    });
    c.items.push({ id: r.id, text: r.text, done: r.done });
  }
  return out;
}
