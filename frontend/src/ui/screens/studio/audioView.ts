import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, api } from '@/api';
import { env } from '@/config/env';
import { qk } from '@/hooks/queries';
import type { AudioPeriod, StudioItem } from '@/types/models';
import { mockAudioPeriods, mockAudioStocks, mockLastClose, type AudioStock } from './Studio.mock';
import type { MadeItem } from './Studio.types';
import type { AudioEp } from './audioEp';

/**
 * AI 오디오 서버 연결 (2026-11-24, backend app/studio_audio/routes.py).
 * 만들기 시트 값(GET /studio/audio/options) · 만들기(POST /studio/audio → GET /studio/audio/{id}로 완성 확인) ·
 * 서버 결과 → 화면 MadeItem. mock 모드는 Studio.mock 값과 store 타이머를 그대로 쓴다.
 */
type AudioContent = Partial<AudioEp> & { meta?: string; options?: { codes?: string[]; period?: string; market?: boolean } };

const mmss = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;

/** 음성 파일 주소 (같은 출처라 웹 <audio>가 로그인 쿠키를 함께 보낸다) */
export const audioFileUrl = (id: string) => `${env.apiBaseUrl}/studio/audio/${id}/file`;

function toMade(id: string, title: string, c: AudioContent, left: string): MadeItem {
  const ep: AudioEp = {
    hosts: c.hosts ?? ['진행자 A', '진행자 B'],
    dur: Math.max(1, Number(c.dur) || 1),
    chapters: c.chapters?.length ? c.chapters : [[0, '오프닝']],
    script: c.script?.length ? c.script : [[0, 'A', '']],
    sources: c.sources ?? [],
    market_source: c.market_source ?? '',
    memo_link: c.memo_link ?? null,
  };
  const o = c.options ?? {};
  const n = o.codes?.length ?? 0;
  const meta = c.meta ?? `오디오 · ${n}종목 · ${o.period ?? ''} · ${mmss(ep.dur)}`;
  return { id, server: true, kind: 'audio', title, sub: meta, meta, left, dur: mmss(ep.dur),
    foot: `종목 ${n}개 · ${o.period ?? ''} 기준${o.market ? ' · 증시 요약' : ''}`, codes: o.codes, market: o.market,
    audio: { ep, fileUrl: audioFileUrl(id) } };
}

/** 서버 만든 항목(kind=audio, ready) → 화면 MadeItem */
export const fromServerAudioItem = (s: StudioItem): MadeItem =>
  toMade(s.id, s.title, s.content as AudioContent, `${s.days_left}일 뒤 삭제`);

/** 만들기 시트 값. 실제 모드는 내 종목과 기간별 새 업데이트 수 (시트를 열었을 때만 읽음) */
export function useAudioPick(open: boolean): { stocks: AudioStock[]; periods: readonly string[]; lastClose: string; loading: boolean } {
  const q = useQuery({ queryKey: ['studioAudioOptions'], queryFn: api.getAudioOptions, enabled: !env.useMock && open, staleTime: 60_000 });
  if (env.useMock) return { stocks: mockAudioStocks, periods: mockAudioPeriods, lastClose: mockLastClose, loading: false };
  return { stocks: q.data?.stocks ?? [], periods: q.data?.periods ?? mockAudioPeriods, lastClose: q.data?.last_close ?? '직전 거래일',
    loading: q.isLoading };
}

const FAIL_TEXT: [string, string][] = [
  ['no_updates', '고른 종목에 이 기간 새 소식이 없어요. 기간을 늘리거나 증시 요약을 넣어 주세요'],
  ['tts_not_ready', '목소리 설정이 안 돼 있어 만들지 못했어요'],
];
const failText = (error: string | null) => FAIL_TEXT.find(([k]) => error?.startsWith(k))?.[1] ?? '오디오를 만들지 못했어요';
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** 실제 모드 오디오 만들기: POST → 완성될 때까지 3초마다 확인 (최대 10분). 완성된 항목을 돌려준다. 크레딧은 서버가 완성 때 뺀다 */
export function useCreateAudio() {
  const qc = useQueryClient();
  return async (codes: string[], period: string, market: boolean): Promise<MadeItem> => {
    let res;
    try {
      res = await api.createAudio({ codes, period: period as AudioPeriod, market });
    } catch (e) {
      throw new Error(e instanceof ApiError ? e.message : '오디오를 만들지 못했어요');
    }
    for (let k = 0; k < 200; k++) {
      let it;
      try {
        it = await api.getAudio(res.item_id);
      } catch {
        await sleep(3000);                // 잠깐 끊겨도 계속 확인 (서버는 뒤에서 계속 만든다)
        continue;
      }
      if (it.status === 'ready') {
        void qc.invalidateQueries({ queryKey: qk.studioItems });
        void qc.invalidateQueries({ queryKey: qk.usage });
        return toMade(it.id, it.title, it.content as AudioContent, '30일 뒤 삭제');
      }
      if (it.status === 'failed') throw new Error(failText(it.error));
      await sleep(3000);
    }
    throw new Error('오디오가 아직 만들어지는 중이에요. 잠시 뒤 만든 항목에서 확인해 주세요');
  };
}
