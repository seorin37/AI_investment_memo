import { router } from 'expo-router';
import { create } from 'zustand';
import { ApiError } from '@/api';
import { registerUserReset } from '@/lib/sessionReset';
import { useStudioPlayer } from '@/store/studioPlayer';
import { useUI } from '@/store/ui';
import { audioOff } from '@/ui/screens/studio/appAudio';
import type { MadeItem } from '@/ui/screens/studio/Studio.types';

/**
 * 앱 스튜디오 만들기 작업 (오디오 · 주간보고서 · 투자 실험실). 여러 개를 같이 만들 수 있고 다른 화면에 있어도 이어짐.
 * 웹은 store/studioPlayer 의 job 을 씀 (여기와 따로). 완성된 항목은 studioPlayer.made 에 넣음.
 * run 이 끝나거나(완성) 오류를 낼 때(실패)만 바뀜. 대기 시간은 run 이 정함 (genRuns). 실패해도 화면은 옮기지 않고 그 작업만 '다시 시도'.
 */
export type GenKind = MadeItem['kind'];
/** 화면에 그대로 보여 줄 실패 이유 */
export class GenError extends Error {}
/** 기다리는 시간을 넘김 (서버는 계속 만들 수 있음) */
export class GenTimeout extends Error {}
export const GEN_LATE = { title: '시간이 오래 걸리고 있어요', body: '아직 만드는 중일 수 있어요. 다시 시도하면 이어서 기다려요.' };
export type StepState = 'wait' | 'run' | 'done' | 'bad';
export interface GenCtx {
  /** 로그아웃 · 다시 시도로 이 실행이 버려졌으면 false */
  alive: () => boolean;
  step: (steps: StepState[]) => void;
  startedAt: number;
  /** 다시 시도한 실행 */
  again: boolean;
}
export interface AppGenJob {
  id: string;
  /** 같은 조건을 두 번 만들지 않게 */
  key: string;
  kind: GenKind;
  sub: string;
  labels: string[];
  steps: StepState[];
  status: 'run' | 'fail';
  startedAt: number;
  error?: string;
  /** 실패 이유가 시간 초과 */
  late?: boolean;
  attempt: number;
  run: (c: GenCtx) => Promise<MadeItem>;
}
const DONE_T: Record<GenKind, string> = { audio: '오디오가 완성됐어요', report: '주간보고서가 완성됐어요', lab: '실험 결과가 완성됐어요' };
const BAD_T: Record<GenKind, string> = { audio: '오디오를 만들지 못했어요', report: '주간보고서를 만들지 못했어요', lab: '실험 결과를 만들지 못했어요' };
const PATH = { audio: '/studio-player', report: '/studio-report', lab: '/studio-lab-result' } as const;

interface GenJobsState {
  jobs: AppGenJob[];
  /** 지금 보고 있는 생성 중 화면 */
  viewing: string | null;
  /** 스튜디오 탭을 보는 중 */
  studioOpen: boolean;
  /** 스튜디오 탭 점 (완성된 것이 있고 아직 안 열어 봄) */
  dot: boolean;
  /** 시작하고 작업 id 를 돌려줌. 같은 조건을 만드는 중이면 그 작업 */
  start(p: Pick<AppGenJob, 'key' | 'kind' | 'sub' | 'labels' | 'run'> & { startedAt?: number }): string;
  retry(id: string): void;
  setViewing(id: string | null): void;
  setStudioOpen(v: boolean): void;
  reset(): void;
}

/** 결과 열기 전에 studioPlayer 에 고른 항목을 알림 */
function choose(item: MadeItem, autoplay: boolean) {
  const s = useStudioPlayer.getState();
  if (item.kind === 'report') s.openReport(item.id);
  else if (item.kind === 'lab') s.openLab(item.id);
  else if (autoplay && !audioOff) s.play(item.id, true);
  else s.select(item.id);
}

let seq = 0;

export const useGenJobs = create<GenJobsState>((set, get) => {
  const patch = (id: string, f: (j: AppGenJob) => AppGenJob) => set((s) => ({ jobs: s.jobs.map((j) => (j.id === id ? f(j) : j)) }));
  const exec = (job: AppGenJob) => {
    const alive = () => get().jobs.some((j) => j.id === job.id && j.attempt === job.attempt);
    job
      .run({ alive, step: (steps) => alive() && patch(job.id, (j) => ({ ...j, steps })), startedAt: job.startedAt, again: job.attempt > 0 })
      .then(
        (item) => {
          if (!alive()) return;
          useStudioPlayer.setState((s) => ({ made: [item, ...s.made.filter((m) => m.id !== item.id)] }));
          const here = get().viewing === job.id;
          if (here) {
            choose(item, true);
            router.replace(PATH[item.kind]);
          } else {
            useUI.getState().showToast(DONE_T[job.kind], {
              label: '보기',
              onPress: () => {
                choose(item, false);
                router.push(PATH[item.kind]);
              },
            });
          }
          set((s) => ({ jobs: s.jobs.filter((j) => j.id !== job.id), dot: s.dot || (!here && !s.studioOpen) }));
        },
        (e: unknown) => {
          if (!alive()) return;
          patch(job.id, (j) => {
            const at = Math.max(0, j.steps.findIndex((x) => x !== 'done'));
            return { ...j, status: 'fail', late: e instanceof GenTimeout, error: e instanceof ApiError || e instanceof GenError ? e.message : undefined, steps: j.steps.map((x, i) => (i === at ? 'bad' : x)) };
          });
          if (get().viewing !== job.id) useUI.getState().showToast(e instanceof GenTimeout ? GEN_LATE.title : BAD_T[job.kind]);
        },
      );
  };
  return {
    jobs: [],
    viewing: null,
    studioOpen: false,
    dot: false,
    start: ({ startedAt = Date.now(), ...p }) => {
      const same = get().jobs.find((j) => j.key === p.key);
      if (same) {
        if (same.status === 'fail') get().retry(same.id);
        return same.id;
      }
      const job: AppGenJob = { ...p, id: `g${Date.now()}${(seq += 1)}`, steps: p.labels.map((_, i) => (i ? 'wait' : 'run')), status: 'run', startedAt, attempt: 0 };
      set((s) => ({ jobs: [job, ...s.jobs] }));
      exec(job);
      return job.id;
    },
    retry: (id) => {
      const old = get().jobs.find((j) => j.id === id);
      if (!old || old.status === 'run') return;
      /* startedAt 은 run 에는 처음 시각(앞서 만든 항목 찾기), 화면에는 다시 시작한 시각 */
      const job: AppGenJob = { ...old, steps: old.steps.map((_, i) => (i ? 'wait' : 'run')), status: 'run', error: undefined, late: false, attempt: old.attempt + 1 };
      patch(id, () => ({ ...job, startedAt: Date.now() }));
      exec(job);
    },
    setViewing: (viewing) => set({ viewing }),
    setStudioOpen: (v) => set((s) => ({ studioOpen: v, dot: v ? false : s.dot })),
    reset: () => set({ jobs: [], viewing: null, dot: false }),
  };
});

registerUserReset('genJobs', () => useGenJobs.getState().reset());
