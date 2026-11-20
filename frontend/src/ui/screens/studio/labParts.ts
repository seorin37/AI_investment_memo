import { mockLabLeaves, mockLabStocks, mockLabVars, type LabDir, type LabLeaf } from './Studio.mock';

/** 투자 실험실 결과 계산 (앱·웹 같이 씀). 문장·근거는 모두 Studio.mock */
export const NUM = '①②③④⑤⑥⑦⑧';
export const dirColor = (d: LabDir) => (d === '상승' ? '#E5484D' : d === '하락' ? '#2F6BDB' : '#16171A');

export interface LabGroup { i: number; d: LabDir; leaves: (LabLeaf & { no: string })[] }

/** 유지가 아닌 조건만 · 조건마다 경로 끝 항목에 ①②… 번호 */
export function labGroups(code: string, dirs: LabDir[]): LabGroup[] {
  const s = mockLabStocks.find((x) => x.stock_code === code) ?? mockLabStocks[0];
  let n = 0;
  return mockLabVars
    .map((_, i) => i)
    .filter((i) => dirs[i] !== '유지')
    .map((i) => ({ i, d: dirs[i], leaves: mockLabLeaves(i, s.fx_strong).map((l) => ({ ...l, no: NUM[n++] })) }));
}

export const labTitle = (code: string, dirs: LabDir[]) => {
  const s = mockLabStocks.find((x) => x.stock_code === code) ?? mockLabStocks[0];
  const picked = mockLabVars.filter((_, i) => dirs[i] !== '유지').map((v, k) => `${v.name.replace(/\(.*\)/, '')} ${dirs[mockLabVars.indexOf(v)]}`);
  return { title: `${s.name} · ${picked.join('·')} 실험`, sub: `투자 실험실 · ${s.name}`, k: picked.length };
};
