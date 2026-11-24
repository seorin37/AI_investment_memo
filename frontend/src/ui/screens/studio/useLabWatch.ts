import { useRef, useState } from 'react';
import { useCreateMemoFor } from '@/hooks/queries';
import type { Memo } from '@/types/models';
import type { LabGroup } from './labParts';

/** 실험 결과 '앞으로 지켜볼 것' 한 줄 — 백엔드가 만든(금지어 검사 거친) check · check_why 그대로 */
export type LabWatch = { check: string; why: string };

/** 경로 끝 항목의 check 를 모음: check 없는 항목은 건너뛰고 · 같은 check 는 하나로 · 최대 3개 */
export function labWatchItems(groups: LabGroup[]): LabWatch[] {
  const out: LabWatch[] = [];
  for (const l of groups.flatMap((g) => g.leaves)) {
    const check = l.check?.trim();
    if (!check || out.some((w) => w.check === check)) continue;
    out.push({ check, why: l.check_why?.trim() ?? '' });
    if (out.length === 3) break;
  }
  return out;
}

/* 이미 메모로 남긴 줄 (새로고침 전까지) — 키: 결과 id(저장된 항목) 또는 실험 제목 + check */
const ADDED = new Set<string>();

/**
 * '+ 메모로': 그 종목 보드에 메모 1개 (보라 · AI 연결 꺼짐 — 사용자가 메모에서 직접 켬)
 * 제목 = check · 본문 = check_why + 다음 줄 '— 투자 실험실 「실험 제목」에서 추가'
 */
export function useLabWatchMemo(result: { key: string; title: string; code: string }) {
  const create = useCreateMemoFor();
  const [, setTick] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  /* 화면이 다시 그려지기 전 빠른 두 번째 클릭도 막음 */
  const busyNow = useRef(false);
  const keyOf = (w: LabWatch) => `${result.key}\n${w.check}`;
  return {
    isAdded: (w: LabWatch) => ADDED.has(keyOf(w)),
    /* 요청 중이면 누른 줄뿐 아니라 다른 줄도 잠깐 막음 (끝나면 원래대로) */
    isBusy: () => busy !== null,
    /* 성공 → 만든 메모 · 'skip' → 무시(요청 중 · 이미 추가 · 종목 코드 없음, 안내 없음) · 'fail' → 진짜 실패 */
    add: async (w: LabWatch): Promise<Memo | 'skip' | 'fail'> => {
      const k = keyOf(w);
      if (!result.code || ADDED.has(k) || busyNow.current) return 'skip';
      busyNow.current = true;
      setBusy(k);
      try {
        const memo = await create.mutateAsync({
          code: result.code,
          input: { title: w.check, body: `${w.why ? `${w.why}\n` : ''}— 투자 실험실 「${result.title}」에서 추가`, tags: [], color: 'purple', ai_linked: false, pinned: false },
        });
        ADDED.add(k);
        setTick((n) => n + 1);
        return memo;
      } catch {
        return 'fail';
      } finally {
        busyNow.current = false;
        setBusy(null);
      }
    },
  };
}
