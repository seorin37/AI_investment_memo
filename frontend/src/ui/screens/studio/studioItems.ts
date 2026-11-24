import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { api } from '@/api';
import { env } from '@/config/env';
import { qk, useStudioItems } from '@/hooks/queries';
import { useAuth } from '@/store/auth';
import { useStudioPlayer } from '@/store/studioPlayer';
import { useUI } from '@/store/ui';
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
    return { id: s.id, server: true, kind: 'lab', title: t.title, sub: t.sub, meta: t.sub, left, lab: { code, dirs, name, groups: s.content.groups, added: (s.content as { added?: Record<string, string> }).added } };
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

/**
 * 만든 항목 삭제 = 휴지통으로 (2026-11-24 팀장 결정, studio_items.deleted_at 0025).
 * 화면 목록에서 먼저 빼고, 서버 항목이면 DELETE /studio/items/{id} (서버가 휴지통으로 옮김) 뒤 목록·휴지통을 다시 받는다.
 * mock·이번 세션에서 만든 mock 항목은 화면에서만 뺀다. 복원은 설정 › 휴지통.
 */
export function useRemoveMade() {
  const qc = useQueryClient();
  const removeMade = useStudioPlayer((s) => s.removeMade);
  const toast = useUI((s) => s.showToast);
  return (m: MadeItem) => {
    removeMade(m.id);
    if (env.useMock || !m.server) return toast('휴지통으로 옮겼어요');
    api.deleteStudioItem(m.id).then(
      () => toast('휴지통으로 옮겼어요 · 설정 › 휴지통에서 되돌릴 수 있어요'),
      () => toast('지우지 못했어요 · 잠시 뒤 다시 해 주세요'),
    ).finally(() => {
      void qc.invalidateQueries({ queryKey: qk.studioItems });
      void qc.invalidateQueries({ queryKey: qk.trash });
    });
  };
}
