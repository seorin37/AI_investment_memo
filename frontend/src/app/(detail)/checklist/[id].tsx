import React, { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { mockBoardChecklist, mockBoardStock } from '@/ui/screens/board/MemoBoard.mock';
import { AppChecklist } from '@/ui/screens/board/app/Checklist';

const NOT_YET = '아직 연결되지 않았어요 · 데이터는 그대로예요';
/** mock 기준일 (보드 · 홈 mock 과 같은 날) */
const MOCK_TODAY = '2026년 11월 19일 작성';
const fullDate = (iso: string) => {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return `${y}년 ${m}월 ${d}일 작성`;
};

/**
 * 앱 체크리스트 = UI v2 (원본 app/memo.html .ckp). id = 'new' 면 + 버튼에서 새로 만들기.
 * mock 단계: 체크 · 이름 · 항목 · 고정은 화면 안에서만 바뀌고, 저장(완료)은 공통 미연결 안내.
 */
export default function ChecklistScreen() {
  const { id, name } = useLocalSearchParams<{ id: string; code?: string; name?: string }>();
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const isNew = id === 'new';
  const base = isNew ? null : mockBoardChecklist;
  const [title, setTitle] = useState(base?.title ?? '체크리스트');
  const [items, setItems] = useState(base?.items ?? []);
  const [pinned, setPinned] = useState(!!base?.pinned);
  return (
    <AppChecklist
      mode={isNew ? 'new' : 'edit'}
      stock_name={name || mockBoardStock.name}
      title={title}
      date_full={base ? fullDate(base.created_at) : MOCK_TODAY}
      items={items}
      pinned={pinned}
      onChangeTitle={setTitle}
      onToggleItem={(iid) => setItems((all) => all.map((i) => (i.id === iid ? { ...i, done: !i.done } : i)))}
      onDeleteItem={(iid) => setItems((all) => all.filter((i) => i.id !== iid))}
      onAddItem={(text) => setItems((all) => [...all, { id: `n${Date.now()}`, text, done: false }])}
      onTogglePin={() => {
        /* 원본 #ckpin: 화면 안에서 바뀌고 안내 (보드 저장은 연결 단계) */
        const next = !pinned;
        setPinned(next);
        toast(next ? '체크리스트를 고정했어요' : '고정을 풀었어요');
      }}
      onBack={() => router.back()}
      onCancel={() => router.back()}
      onDone={() => {
        /* 원본 endNewCk(true): 빈 체크리스트는 저장하지 않음 · 저장은 연결 전이라 공통 안내 */
        toast(items.length ? NOT_YET : '빈 체크리스트는 저장하지 않았어요');
        router.back();
      }}
    />
  );
}
