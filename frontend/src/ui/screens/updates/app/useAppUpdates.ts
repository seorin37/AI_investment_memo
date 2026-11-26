import { create } from 'zustand';
import { env } from '@/config/env';
import { useUpdates } from '@/hooks/queries';
import { registerUserReset } from '@/lib/sessionReset';
import type { AiUpdate } from '@/types/models';
import { mockUpdateItems } from '../Updates.mock';
import type { UpdateItem } from '../Updates.types';
import { unreadOf } from '../updatesFormat';
import { toUpdateItem, useUpdatesData } from '../useUpdatesData';

/**
 * 앱: 업데이트 화면과 아래 탭 '업데이트' 배지가 같은 읽지 않은 수를 쓰게 (수정 76).
 * useUpdatesData(웹과 같이 씀)는 읽음 상태를 화면 안에만 들고 있어서, 앱에서 바꾼 읽음을 여기 모아 두고 양쪽에 같이 씀.
 * 데이터는 그대로 (실제 GET /updates 같은 쿼리 · mock 은 Updates.mock), 계산도 같은 unreadOf. 새 API 없음.
 */
const useRead = create<{ read: Record<string, boolean>; set: (ids: string[], read: boolean) => void }>((set) => ({
  read: {},
  set: (ids, read) => set((s) => ({ read: { ...s.read, ...Object.fromEntries(ids.map((id) => [id, read])) } })),
}));
registerUserReset('appUpdatesRead', () => useRead.setState({ read: {} }));

const applyRead = (items: UpdateItem[], read: Record<string, boolean>) => items.map((u) => (u.id in read ? { ...u, unread: !read[u.id] } : u));

/** 업데이트 화면 데이터 (useUpdatesData + 앱 읽음 상태) */
export function useAppUpdatesData() {
  const d = useUpdatesData();
  const read = useRead((s) => s.read);
  return {
    ...d,
    items: applyRead(d.items, read),
    onMarkRead: (ids: string[], r: boolean) => {
      useRead.getState().set(ids, r);
      d.onMarkRead(ids, r);
    },
  };
}

/** 아래 탭 '업데이트' 배지 = 업데이트 화면 '읽지 않은 소식 N건'과 같은 수 */
export function useUpdatesUnread(): number {
  const updates = useUpdates();
  const read = useRead((s) => s.read);
  const base = env.useMock ? mockUpdateItems : ((updates.data ?? []) as AiUpdate[]).map(toUpdateItem);
  return unreadOf(applyRead(base, read));
}
