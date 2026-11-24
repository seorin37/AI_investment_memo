import { useQueryClient } from '@tanstack/react-query';
import { ApiError, api } from '@/api';
import { env } from '@/config/env';
import { qk, useMyStocks } from '@/hooks/queries';
import { useStudioPlayer } from '@/store/studioPlayer';
import { useUI } from '@/store/ui';
import { mockLabStocks, type LabDir } from './Studio.mock';
import { labTitle } from './labParts';

export type LabStock = (typeof mockLabStocks)[number];

const toLabStock = (stock_code: string, name: string, hold: LabStock['hold']): LabStock => ({
  stock_code,
  name,
  logo: name.slice(0, 1),
  logo_bg: '#575B63',
  hold,
  fx_strong: false,
  memo: '',
  memo_text: '',
});

/** 실험할 종목. 실제 모드는 내 종목이고, 예시 메모는 보여 주지 않는다 */
export function useLabStocks(): LabStock[] {
  const mine = useMyStocks().data ?? [];
  if (env.useMock) return mockLabStocks;
  if (mine.length) return mine.map((s) => toLabStock(s.code, s.name, s.status === 'holding' ? '보유' : '관심'));
  return mockLabStocks.map((s) => ({ ...s, memo: '', memo_text: '' }));
}

/** 만든 항목의 종목. 내 종목에서 빠졌어도 실험 당시 이름으로 보여 준다 */
export function labStockFor(stocks: LabStock[], lab: { code: string; name?: string }): LabStock {
  return stocks.find((s) => s.stock_code === lab.code) ?? (lab.name ? toLabStock(lab.code, lab.name, '관심') : stocks[0]);
}

/** 실험 실행 → 만든 항목에 추가. 성공하면 true, 실패하면 안내를 띄우고 false */
export function useRunLab() {
  const queryClient = useQueryClient();
  const addLab = useStudioPlayer((s) => s.addLab);
  const toast = useUI((s) => s.showToast);
  return async (stock: LabStock, dirs: LabDir[]): Promise<boolean> => {
    try {
      const result = await api.runLab({ stock_code: stock.stock_code, dirs });
      const t = labTitle(stock.stock_code, dirs, stock.name);
      /* 서버에 저장됐으면 그 id로 (새로고침 뒤에도 같은 항목) — 목록을 다시 받아 서버 값으로 맞춘다 (2026-11-23) */
      addLab({
        id: result.item_id ?? `m${Date.now()}`,
        server: !!result.item_id,
        kind: 'lab',
        title: t.title,
        sub: t.sub,
        meta: t.sub,
        left: '30일 뒤 삭제',
        lab: { code: stock.stock_code, dirs, name: stock.name, groups: result.groups },
      });
      void queryClient.invalidateQueries({ queryKey: qk.usage });
      if (result.item_id) void queryClient.invalidateQueries({ queryKey: qk.studioItems });
      return true;
    } catch (error) {
      toast(error instanceof ApiError ? error.message : '실험을 실행하지 못했어요. 잠시 뒤 다시 시도해 주세요.');
      return false;
    }
  };
}
