import { create } from 'zustand';

/**
 * 사용법 안내 4단계 (원본 앱 x/app.js 85~220줄 · 웹 coach.tsx · Lucian #197)
 * step: null = 꺼짐 · -1 = 첫 카드('30초만 둘러볼까요?') · 0~3 = 단계
 * seen: 가입 직후 처음 한 번만 — 지금은 앱을 켜 둔 동안 메모리에만 (연결 단계에서 서버 저장)
 */
interface CoachState {
  step: number | null;
  seen: boolean;
  /** 끝난 뒤 홈에서 띄울 알림 (key 가 바뀌면 한 번) */
  done: { key: number; finished: boolean } | null;
  /** 첫 홈에서 처음 한 번 (이미 봤으면 아무것도 안 함) */
  startFirst(): void;
  /** 사용법 다시 보기 — 본 적 있어도 다시 */
  replay(): void;
  go(step: number): void;
  end(finished: boolean): void;
}

let seq = 0;
export const useCoach = create<CoachState>((set, get) => ({
  step: null,
  seen: false,
  done: null,
  startFirst: () => {
    if (get().seen || get().step != null) return;
    set({ step: -1 });
  },
  replay: () => set({ step: -1 }),
  go: (step) => set({ step }),
  end: (finished) => set({ step: null, seen: true, done: { key: ++seq, finished } }),
}));
