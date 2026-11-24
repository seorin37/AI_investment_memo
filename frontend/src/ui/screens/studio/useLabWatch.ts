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

/**
 * '메모에 추가' (2026-11-24, 주간보고서와 같은 방식): 종목 메모 창을 이 내용으로 채워 열고 AI 연결을 켠다.
 * 제목 = check · 본문 = check_why + 추적 요청 + 출처 한 줄. 저장하면 만든 항목에 '추가됨'(key = 종목코드:w순번).
 */
export function labWatchDraft(w: LabWatch, labTitle: string): { title: string; body: string } {
  const lines = [w.why, `${w.check} 관련 공시·뉴스 나오면 알려줘`, `— 투자 실험실 「${labTitle}」에서 추가`].filter(Boolean);
  return { title: w.check, body: lines.join('\n') };
}

export const labWatchKey = (code: string, i: number) => `${code}:w${i}`;
