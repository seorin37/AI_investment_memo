import { useEffect } from 'react';
import { env } from '@/config/env';
import { useStudioItems } from '@/hooks/queries';
import { useAuth } from '@/store/auth';
import { useStudioPlayer } from '@/store/studioPlayer';
import type { StudioItem } from '@/types/models';
import type { LabDir } from './Studio.mock';
import type { MadeItem } from './Studio.types';
import { labTitle } from './labParts';
import { fromServerReportItem } from './reportView';

const KIND_LABEL: Record<StudioItem['kind'], string> = { lab: '투자 실험실', report: '주간보고서', audio: '오디오' };

/** 서버 만든 항목(studio_items) → 화면 MadeItem (2026-11-23). 실험실은 앱이 만들던 제목 규칙(labTitle)을 그대로 쓴다 */
export function fromServerItem(s: StudioItem): MadeItem {
  const left = `${s.days_left}일 뒤 삭제`;
  if (s.kind === 'lab') {
    const code = s.content.stock_code ?? s.symbols[0] ?? '';
    const dirs = (s.content.dirs ?? ['유지', '유지', '유지', '유지']) as LabDir[];
    const name = s.content.name;
    const t = labTitle(code, dirs, name);
    return { id: s.id, server: true, kind: 'lab', title: t.title, sub: t.sub, meta: t.sub, left, lab: { code, dirs, name, groups: s.content.groups } };
  }
  if (s.kind === 'report') return fromServerReportItem(s);
  const meta = `${KIND_LABEL[s.kind]} · ${s.symbols.length}종목`;
  return { id: s.id, server: true, kind: s.kind, title: s.title, sub: meta, meta, left, codes: s.symbols };
}

/** 실제 모드: 로그인하면 서버 만든 항목을 받아 스튜디오 상태(store.made)에 넣는다. 앱·웹 레이아웃에서 한 번 부른다 */
export function useStudioItemsSync() {
  const signedIn = useAuth((s) => s.status === 'signedIn');
  const { data } = useStudioItems(!env.useMock && signedIn);
  const setServerMade = useStudioPlayer((s) => s.setServerMade);
  useEffect(() => {
    if (data) setServerMade(data.filter((s) => s.status === 'ready').map(fromServerItem));   // 만드는 중·실패는 목록에 안 보인다
  }, [data, setServerMade]);
}
