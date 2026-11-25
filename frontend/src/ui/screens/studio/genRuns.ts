import { useEffect } from 'react';
import { api } from '@/api';
import { env } from '@/config/env';
import { qk, useStudioItems } from '@/hooks/queries';
import { queryClient } from '@/lib/queryClient';
import { useAuth } from '@/store/auth';
import type { AudioPeriod } from '@/types/models';
import { GenError, GenTimeout, useGenJobs, type GenCtx } from '@/store/genJobs';
import { fmt, useStudioPlayer } from '@/store/studioPlayer';
import type { LabStock } from './useLabRun';
import { mockAudioEpisode, mockAudioGen, mockReport, type LabDir } from './Studio.mock';
import type { MadeItem } from './Studio.types';
import { failText, fromServerAudioItem } from './audioView';
import { labTitle } from './labParts';
import { fromServerReportItem } from './reportView';
import { fromServerItem } from './studioItems';

/**
 * 앱 스튜디오 만들기 (store/genJobs 가 실행).
 * - 단계 표시: 서버가 세부 단계를 주지 않아 시간으로 넘어가고(PACE) 마지막 단계에서 결과를 기다림 (store/genJobs)
 * - 주간보고서: 기다리는 시간(웹과 같은 6분)을 넘기면 그 작업만 실패.
 *   서버는 계속 만들고, 다시 시도하면 서버가 같은 조건의 항목을 돌려줘 이어서 기다림 (studio_report/routes.py SAME_SQL)
 * - 투자 실험실: 요청 하나로 답을 받음
 * - 오디오: POST /studio/audio → GET /studio/audio/{id} 로 완성 확인 (웹과 같은 10분). mock 모드는 예시
 * - mock 시간: EXPO_PUBLIC_MOCK_GEN_SECONDS (기본 5.5초)
 */
export const LAB_STEPS = ['조건 읽기', '영향 경로 찾기', '결과 정리하기'];
const POLL_MS = 3000;
/* 기다리는 시간: reportView useCreateReport 와 같음 */
const REPORT_WAIT_MS = 6 * 60_000;
/* audioView useCreateAudio 와 같음 */
const AUDIO_WAIT_MS = 10 * 60_000;
/* 서버는 15분 넘게 멈춘 항목을 버린 것으로 봄 (studio_report/routes.py SAME_SQL) */
const RESTORE_MS = 15 * 60_000;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const mockMs = () => env.mockGenSeconds * 1000;
const isReal = !env.useMock;
/* 다음 단계로 넘어가는 때 (ms). 보고서·오디오는 store/studioPlayer 의 SERVER_STEPS 와 같음 · mock 은 삼등분 */
const PACE = { report: [2500, 9000], audio: [3000, 40_000], lab: [1200, 4000] };
const pace = (kind: keyof typeof PACE) => (isReal ? PACE[kind] : [mockMs() / 3, (mockMs() * 2) / 3]);

async function waitReport(id: string, c: GenCtx): Promise<MadeItem> {
  let missing = 0;
  const until = Date.now() + REPORT_WAIT_MS;
  while (c.alive()) {
    /* 잠깐 끊긴 것은 실패가 아님 → 다음 번에 다시 */
    const items = await api.listStudioItems().catch(() => null);
    if (items) {
      const it = items.find((x) => x.id === id);
      if (it?.status === 'ready') {
        queryClient.setQueryData(qk.studioItems, items);
        void queryClient.invalidateQueries({ queryKey: qk.usage });
        return fromServerReportItem(it);
      }
      missing = it ? 0 : missing + 1;
      if (it?.status === 'failed' || missing >= 3) throw new Error('failed');
    }
    if (Date.now() >= until) throw new GenTimeout('timeout');
    await sleep(POLL_MS);
  }
  throw new Error('gone');
}

export function startReport(p: { sub: string; codes: string[]; market: boolean; fail?: boolean }, restore?: { id: string; startedAt: number }): string {
  return useGenJobs.getState().start({
    key: `report:${[...p.codes].sort().join(',')}:${p.market}`,
    kind: 'report',
    sub: p.sub,
    labels: mockReport.steps,
    pace: pace('report'),
    startedAt: restore?.startedAt,
    run: async (c) => {
      if (isReal) {
        if (restore && !c.again) return waitReport(restore.id, c);
        const res = await api.createReport({ codes: p.codes, market: p.market });
        return waitReport(res.item_id, c);
      }
      await sleep(mockMs());
      if (p.fail && !c.again) throw new Error('failed');
      const sub = `주간보고서 · ${p.codes.length}종목 · ${mockReport.made_label}`;
      return { id: `m${Date.now()}`, kind: 'report', title: mockReport.title, sub, meta: sub, left: '30일 뒤 삭제', codes: p.codes, market: p.market };
    },
  });
}

async function waitAudio(id: string, c: GenCtx): Promise<MadeItem> {
  const until = Date.now() + AUDIO_WAIT_MS;
  while (c.alive()) {
    /* 잠깐 끊긴 것은 실패가 아님 → 다음 번에 다시 */
    const it = await api.getAudio(id).catch(() => null);
    if (it?.status === 'failed') throw new GenError(failText(it.error));
    if (it?.status === 'ready') {
      const items = await api.listStudioItems().catch(() => null);
      const made = items?.find((x) => x.id === id);
      if (items && made) {
        queryClient.setQueryData(qk.studioItems, items);
        void queryClient.invalidateQueries({ queryKey: qk.usage });
        return fromServerAudioItem(made);
      }
    }
    if (Date.now() >= until) throw new GenTimeout('timeout');
    await sleep(POLL_MS);
  }
  throw new Error('gone');
}

export function startAudio(p: { sub: string; codes: string[]; period: string; market: boolean; fail?: boolean }): string {
  return useGenJobs.getState().start({
    key: `audio:${[...p.codes].sort().join(',')}:${p.period}:${p.market}`,
    kind: 'audio',
    sub: p.sub,
    labels: mockAudioGen.steps,
    pace: pace('audio'),
    run: async (c) => {
      if (isReal) {
        const res = await api.createAudio({ codes: p.codes, period: p.period as AudioPeriod, market: p.market });
        return waitAudio(res.item_id, c);
      }
      if (p.fail && !c.again) {
        await sleep((mockMs() * 2) / 3);
        throw new Error('failed');
      }
      await sleep(mockMs());
      const dur = fmt(mockAudioEpisode.dur);
      const meta = `오디오 · ${p.codes.length}종목 · ${dur}`;
      return { id: `m${Date.now()}`, kind: 'audio', title: mockAudioGen.result_title, sub: meta, meta, left: '30일 뒤 삭제', dur, foot: p.sub };
    },
  });
}

export function startLab(stock: LabStock, dirs: LabDir[]): string {
  const t = labTitle(stock.stock_code, dirs, stock.name);
  /* 시작할 때 이미 있던 항목 — 다시 시도에서 새로 생긴 것만 찾으려고 */
  const known = new Set(useStudioPlayer.getState().made.map((m) => m.id));
  return useGenJobs.getState().start({
    key: `lab:${stock.stock_code}:${dirs.join('')}`,
    kind: 'lab',
    sub: t.title,
    labels: LAB_STEPS,
    pace: pace('lab'),
    run: async (c) => {
      /* 다시 시도: 앞 요청이 끊겼어도 서버가 만들어 뒀으면 그것을 씀 */
      if (isReal && c.again) {
        const items = await api.listStudioItems();
        const made = items.find((x) => x.kind === 'lab' && x.status === 'ready' && !known.has(x.id) && Date.parse(x.created_at) > c.startedAt - 60_000
          && (x.content.stock_code ?? x.symbols[0]) === stock.stock_code && (x.content.dirs ?? []).join() === dirs.join());
        if (made) {
          queryClient.setQueryData(qk.studioItems, items);
          void queryClient.invalidateQueries({ queryKey: qk.usage });
          return fromServerItem(made);
        }
      }
      if (!isReal) await sleep(mockMs());
      const result = await api.runLab({ stock_code: stock.stock_code, dirs }, { timeoutMs: 300_000 });
      void queryClient.invalidateQueries({ queryKey: qk.usage });
      if (result.item_id) void queryClient.invalidateQueries({ queryKey: qk.studioItems });
      return {
        id: result.item_id ?? `m${Date.now()}`,
        server: !!result.item_id,
        kind: 'lab',
        title: t.title,
        sub: t.sub,
        meta: t.sub,
        left: '30일 뒤 삭제',
        lab: { code: stock.stock_code, dirs, name: stock.name, groups: result.groups },
      };
    },
  });
}

/** 앱을 다시 켰을 때 서버가 아직 만드는 중인 주간보고서를 '만드는 중'으로 이어 보여 줌. 앱 탭 레이아웃에서 한 번 */
export function useGenRestore() {
  const signedIn = useAuth((s) => s.status === 'signedIn');
  const { data } = useStudioItems(isReal && signedIn);
  useEffect(() => {
    for (const it of data ?? []) {
      const startedAt = Date.parse(it.created_at);
      if (it.kind !== 'report' || (it.status !== 'generating' && it.status !== 'queued') || Date.now() - startedAt > RESTORE_MS) continue;
      startReportOnce(it.symbols, !!it.content.market_on, it.id, startedAt);
    }
  }, [data]);
}

function startReportOnce(codes: string[], market: boolean, id: string, startedAt: number) {
  const key = `report:${[...codes].sort().join(',')}:${market}`;
  /* 이미 화면에 있는 작업(실패 포함)은 건드리지 않음 */
  if (useGenJobs.getState().jobs.some((j) => j.key === key)) return;
  startReport({ sub: `${codes.length}종목${market ? ' · 국내 증시 흐름 포함' : ''} · 지난주`, codes, market }, { id, startedAt });
}
