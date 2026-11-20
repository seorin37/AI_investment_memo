import { create } from 'zustand';
import { useCoach } from './coach';

/** 스튜디오 넛지 종류 (원본 웹 store NudgeId) */
export type NudgeId = 'memo' | 'updates' | 'info' | 'lab' | 'home';

/**
 * 넛지 닫은 상태 한 곳 (원본 웹 nudgeOff · 앱 x/app.js 'memos-app-nudge-off')
 * 닫으면 다시 들어와도 안 뜸 — 지금은 앱을 켜 둔 동안 메모리에만 (연결 단계에서 저장).
 */
interface NudgeState {
  off: Partial<Record<NudgeId, boolean>>;
  hide(id: NudgeId): void;
}

export const useNudgeStore = create<NudgeState>((set) => ({
  off: {},
  hide: (id) => set((s) => ({ off: { ...s.off, [id]: true } })),
}));

/** 이 넛지를 지금 보여도 되는지 — 닫았거나 사용법 안내 중이면 숨김 (원본: !nudgeOff[id] && !coach) */
export function useNudge(id: NudgeId) {
  const off = useNudgeStore((s) => !!s.off[id]);
  const coaching = useCoach((s) => s.step != null);
  const hide = useNudgeStore((s) => s.hide);
  return { show: !off && !coaching, hide: () => hide(id) };
}
