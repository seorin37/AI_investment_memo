import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

/**
 * '메모에 추가'를 누른 항목 (주간보고서 '앞으로 지켜볼 것' · 투자 실험실 '추가로 확인할 것').
 * 서버에 표시할 곳이 없어 기기에 저장. 키에 사용자 id 가 들어 있어 로그아웃해도 남기고, 다른 사용자에게는 안 보임
 */
interface WatchAddedState {
  added: Record<string, true>;
  mark: (key: string, on: boolean) => void;
}

export const useWatchAdded = create<WatchAddedState>()(
  persist(
    (set) => ({
      added: {},
      mark: (key, on) =>
        set((s) => {
          const { [key]: _old, ...rest } = s.added;
          return { added: on ? { ...rest, [key]: true } : rest };
        }),
    }),
    { name: 'memos.watch_added', storage: createJSONStorage(() => AsyncStorage) },
  ),
);
