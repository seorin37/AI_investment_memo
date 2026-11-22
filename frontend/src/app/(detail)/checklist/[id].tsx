import React, { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/api';
import { env } from '@/config/env';
import { qk, useBoardItem, useStock } from '@/hooks/queries';
import { useUI } from '@/store/ui';
import type { ChecklistItem } from '@/types/models';
import { mockBoardChecklist, mockBoardStock } from '@/ui/screens/board/MemoBoard.mock';
import { AppChecklist } from '@/ui/screens/board/app/Checklist';

const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';
/** mock 기준일 (보드 · 홈 mock 과 같은 날) */
const MOCK_TODAY = '2026년 11월 19일 작성';
const fullDate = (iso: string) => {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return `${y}년 ${m}월 ${d}일 작성`;
};
const todayFull = () => fullDate(new Date(Date.now() + 9 * 3600_000).toISOString());
/** 화면에서 새로 더한 항목(id 'n…')은 서버 id 가 없다 → 저장할 때 id 없이 보냄 */
const toInput = (items: ChecklistItem[]) => items.map((i) => (/^\d+$/.test(i.id) ? i : { text: i.text, done: i.done }));

/**
 * 앱 체크리스트 = UI v2 (원본 app/memo.html .ckp). id = 'new' 면 + 버튼에서 새로 만들기.
 * 실제 모드(2026-11-22): 읽기 GET /board-items/{id} · 체크와 고정은 바로 저장(PATCH) ·
 *   이름 · 항목 더하기/빼기는 완료(또는 뒤로)할 때 PATCH, 새로 만들기는 POST /stocks/{code}/checklists.
 * mock 모드: 체크 · 이름 · 항목 · 고정은 화면 안에서만 바뀌고, 저장(완료)은 공통 미연결 안내.
 */
export default function ChecklistScreen() {
  const { id, code, name } = useLocalSearchParams<{ id: string; code?: string; name?: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useUI((s) => s.showToast);
  const real = !env.useMock;
  const isNew = id === 'new';
  const server = useBoardItem(real && !isNew ? id : '', real && !isNew);
  const remote = server.data?.kind === 'checklist' ? server.data : null;
  const stockCode = remote?.stock_code ?? code ?? '';
  const stock = useStock(real && !name ? stockCode : '');
  const base = real ? remote : isNew ? null : mockBoardChecklist;
  const [title, setTitle] = useState(base?.title ?? '체크리스트');
  const [items, setItems] = useState<ChecklistItem[]>(base?.items ?? []);
  const [pinned, setPinned] = useState(!!base?.pinned);
  const [dirty, setDirty] = useState(false);
  /* 실제 모드: 서버 체크리스트가 처음 오면 화면 상태를 그 값으로 */
  const [seeded, setSeeded] = useState(!real || isNew);
  if (!seeded && remote) {
    setSeeded(true);
    setTitle(remote.title);
    setItems(remote.items);
    setPinned(!!remote.pinned);
  }
  if (real && !isNew && !remote) return null;

  const refresh = () => {
    if (stockCode) void qc.invalidateQueries({ queryKey: qk.board(stockCode) });
    void qc.invalidateQueries({ queryKey: qk.boardItem(id) });
    void qc.invalidateQueries({ queryKey: qk.homeChecklist });
  };
  const failed = () => toast('저장하지 못했어요 · 잠시 뒤 다시 해 주세요');
  /** 완료 · 뒤로: 바꾼 이름·항목 저장 (새로 만들기는 만들기) */
  const finish = (fromBack: boolean) => {
    if (!real) {
      if (!fromBack) toast(items.length ? NOT_YET : '빈 체크리스트는 저장하지 않았어요');
      return router.back();
    }
    if (isNew) {
      if (fromBack) return router.back();
      if (!items.length || !stockCode) {
        toast('빈 체크리스트는 저장하지 않았어요');
        return router.back();
      }
      void api
        .createChecklist(stockCode, { title: title.trim() || '체크리스트', items: toInput(items) })
        .then((c) => (pinned ? api.updateBoardItem(c.id, { pinned: true }) : c))
        .then(() => {
          refresh();
          toast('체크리스트를 저장했어요');
          router.back();
        }, failed);
      return;
    }
    if (!dirty) return router.back();
    /* 서버 ChecklistItemInput 은 id 가 없어도 된다(새 항목). 프론트 patch 타입은 id 를 요구해서 맞춰 줌 */
    void api.updateBoardItem(id, { title: title.trim() || '체크리스트', items: toInput(items) as ChecklistItem[] }).then(() => {
      refresh();
      router.back();
    }, failed);
  };

  return (
    <AppChecklist
      mode={isNew ? 'new' : 'edit'}
      stock_name={name || stock.data?.name || (real ? stockCode : mockBoardStock.name)}
      title={title}
      date_full={base ? fullDate(base.created_at) : real ? todayFull() : MOCK_TODAY}
      items={items}
      pinned={pinned}
      onChangeTitle={(t) => {
        setTitle(t);
        setDirty(true);
      }}
      onToggleItem={(iid) => {
        const it = items.find((i) => i.id === iid);
        setItems((all) => all.map((i) => (i.id === iid ? { ...i, done: !i.done } : i)));
        /* 서버에 있는 항목이면 바로 저장 (보드 · 홈 위젯과 같은 PATCH) */
        if (real && !isNew && it && /^\d+$/.test(iid)) void api.setBoardChecklistItem(id, iid, !it.done).then(refresh, failed);
      }}
      onDeleteItem={(iid) => {
        setItems((all) => all.filter((i) => i.id !== iid));
        setDirty(true);
      }}
      onAddItem={(text) => {
        setItems((all) => [...all, { id: `n${Date.now()}`, text, done: false }]);
        setDirty(true);
      }}
      onTogglePin={() => {
        /* 원본 #ckpin: 바뀌고 안내. 실제 모드면 있는 체크리스트는 바로 저장 */
        const next = !pinned;
        setPinned(next);
        toast(next ? '체크리스트를 고정했어요' : '고정을 풀었어요');
        if (real && !isNew) void api.updateBoardItem(id, { pinned: next }).then(refresh, failed);
      }}
      onBack={() => finish(true)}
      onCancel={() => router.back()}
      onDone={() => finish(false)}
    />
  );
}
