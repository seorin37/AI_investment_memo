import React, { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { MobileScreen } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { ChecklistDetail } from '@/features/board/ChecklistDetail';
import { mockChecklistDetailProps, mockChecklistNewProps } from '@/features/board/ChecklistDetail.mock';
import { useUI } from '@/store/ui';

/** 체크리스트 (id = 'new' 면 새로 만들기). mock 단계: 화면 안에서만 바뀜 */
export default function ChecklistScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const base = id === 'new' ? mockChecklistNewProps : mockChecklistDetailProps;
  const [title, setTitle] = useState(base.title);
  const [items, setItems] = useState(base.items);
  const [pinned, setPinned] = useState(base.pinned);
  const bar =
    base.mode === 'new' ? (
      <TopBar left="cancel" title="새 체크리스트" onCancel={() => router.back()}
        actions={[{ kind: 'text', label: '완료', emphasis: true, disabled: !items.length, onPress: () => { toast('저장했어요 (예시)'); router.back(); } }]} />
    ) : (
      <TopBar left="back" title="메모 보드" onBack={() => router.back()} actions={[{ kind: 'pill', label: '고정', on: pinned, onPress: () => setPinned((p) => !p) }]} />
    );
  return (
    <MobileScreen bg="#FFFFFF" bar={bar}>
      <ChecklistDetail
        {...base}
        title={title}
        items={items}
        pinned={pinned}
        onChangeTitle={setTitle}
        onToggleItem={(iid) => setItems((all) => all.map((i) => (i.id === iid ? { ...i, done: !i.done } : i)))}
        onDeleteItem={(iid) => setItems((all) => all.filter((i) => i.id !== iid))}
        onAddItem={(text) => setItems((all) => [...all, { id: `n${Date.now()}`, text, done: false }])}
        onAllDone={() => toast('모두 끝냈어요')}
      />
    </MobileScreen>
  );
}
