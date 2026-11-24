import { useState } from 'react';
import { env } from '@/config/env';
import {
  useAddChecklistItem,
  useAiStats,
  useHomeChecklist,
  useHomeLayout,
  useMyStocks,
  useSaveHomeLayout,
  useSetChecklistItem,
  useUpdates,
} from '@/hooks/queries';
import { mockItems, SEED_CARDS, useMockBoard } from '@/store/mockBoard';
import type { AiUpdate, Checklist } from '@/types/models';
import { arrange, patchChecklist } from '@/ui/screens/board/boardCards';
import { fallbackLogo } from '@/ui/screens/company/useCompanyInfo';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { mockHomeData } from './Home.mock';
import type { HomeData, HomeWidget } from './Home.types';
import { checklistsFrom, layoutFrom, updateRows, widgetsFrom } from './homeMine';

/**
 * 홈(②) 내 데이터 (2026-11-22, 업데이트 useUpdatesData 와 같은 틀). 시장 지수(useHomeMarket) · 뉴스(useHomeNewsProps)는 따로.
 * - 이름: useMyProfile (로그인한 계정) · 보유/관심 수 · 체크리스트 칩 종목: GET /stocks · AI 연결 메모 수: GET /ai/stats
 * - 업데이트 위젯: 종목별 안 읽은 소식 수(GET /stocks unread_updates) + 가장 새 카드(GET /updates)
 * - 체크리스트 위젯: GET /checklist-items 를 종목별로 묶음(여러 개면 한 목록) · 체크 PATCH(항목이 든 체크리스트) · 추가 POST /checklist-items
 * - 켜 둔 위젯: GET·PUT /home/layout (화면 'check' = 서버 'checklist'). 저장한 적 없으면(unset) 기본 위젯
 * - USE_MOCK=true 면 Home.mock. 보드가 있는 종목(000660)의 체크리스트는 보드와 같은 store/mockBoard
 */
const BOARD_CODE = '000660';
type Mine = Pick<HomeData, 'user_name' | 'counts' | 'updates' | 'stocks' | 'checklists' | 'widgets'>;

export function useHomeData() {
  const real = !env.useMock;
  const { profile } = useMyProfile();
  const stocks = useMyStocks();
  const feed = useUpdates();
  const stats = useAiStats();
  const checks = useHomeChecklist();
  const layout = useHomeLayout();
  const saveLayout = useSaveHomeLayout();
  const setItem = useSetChecklistItem();
  const addItem = useAddChecklistItem();
  const [mockWidgets, setMockWidgets] = useState<HomeWidget[]>(mockHomeData.widgets);
  const [mockChecks, setMockChecks] = useState<Record<string, Checklist>>(mockHomeData.checklists);

  const mockBoard = useMockBoard((s) => s.boards[BOARD_CODE]) ?? SEED_CARDS;

  if (!real) {
    /* 고정된 것 → 보드 앞쪽 순으로 한 목록 (서버 GET /checklist-items 와 같은 순서) */
    const rank = arrange(mockBoard);
    const lists = [...mockBoard.checklists].sort((a, b) => rank.indexOf(a.id) - rank.indexOf(b.id));
    const merged: Checklist | null = lists.length ? { ...lists[0], title: lists.length > 1 ? '체크리스트' : lists[0].title, items: lists.flatMap((c) => c.items) } : null;
    const board = useMockBoard.getState();
    const patch = (code: string, f: (c: Checklist) => Checklist) => setMockChecks((all) => (all[code] ? { ...all, [code]: f(all[code]) } : all));
    const { [BOARD_CODE]: _seed, ...others } = mockChecks;
    const data: Mine = { ...mockHomeData, user_name: profile.name, widgets: mockWidgets, checklists: merged ? { [BOARD_CODE]: merged, ...others } : others };
    return {
      data,
      onChangeWidgets: setMockWidgets,
      onToggleCheck: (code: string, id: string) => {
        const own = code === BOARD_CODE ? lists.find((c) => c.items.some((i) => i.id === id)) : undefined;
        if (own) return board.update(BOARD_CODE, SEED_CARDS, (b) => patchChecklist(b, own.id, (c) => ({ ...c, items: c.items.map((i) => (i.id === id ? { ...i, done: !i.done } : i)) })));
        patch(code, (c) => ({ ...c, items: c.items.map((i) => (i.id === id ? { ...i, done: !i.done } : i)) }));
      },
      onAddCheck: (code: string, text: string) => {
        if (code === BOARD_CODE) {
          const item = { text, done: false };
          if (!lists.length) return void board.addChecklist(BOARD_CODE, SEED_CARDS, { title: '체크리스트', items: [item] });
          return board.update(BOARD_CODE, SEED_CARDS, (b) => patchChecklist(b, lists[0].id, (c) => ({ ...c, items: [...c.items, ...mockItems([item])] })));
        }
        patch(code, (c) => ({ ...c, items: [...c.items, { id: `n${c.items.length + 1}`, text, done: false }] }));
      },
    };
  }

  const mine = stocks.data ?? [];
  const checklists = checklistsFrom(checks.data ?? []);
  const data: Mine = {
    user_name: profile.name,
    counts: {
      holding: mine.filter((s) => s.status === 'holding').length,
      watching: mine.filter((s) => s.status === 'watching').length,
      ai_memos: stats.data?.linked_memos ?? 0,
    },
    // 계약 타입은 MarketUpdate[] 지만 실제 서버는 AiUpdate 를 준다 (useUpdatesData 와 같음)
    updates: updateRows(mine, (feed.data ?? []) as AiUpdate[], fallbackLogo),
    stocks: mine.map((s) => ({ stock_code: s.code, name: s.name })),
    checklists,
    widgets: widgetsFrom(layout.data, mockHomeData.widgets),
  };
  return {
    data,
    onChangeWidgets: (w: HomeWidget[]) => saveLayout.mutate(layoutFrom(w)),
    onToggleCheck: (code: string, id: string) => {
      /* 종목에 체크리스트가 여러 개일 수 있어 그 항목이 든 체크리스트로 */
      const row = checks.data?.find((r) => r.id === id);
      if (row) setItem.mutate({ checklistId: row.checklist_id, itemId: id, done: !row.done, stockCode: code });
    },
    onAddCheck: (code: string, text: string) => addItem.mutate({ stockCode: code, text }),
  };
}
