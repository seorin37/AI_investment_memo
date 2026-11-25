import React, { useState } from 'react';
import { Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/api';
import { env } from '@/config/env';
import { qk } from '@/hooks/queries';
import { useMockBoard } from '@/store/mockBoard';
import { useUI } from '@/store/ui';
import type { MemoColor } from '@/types/models';
import { mockBase, mockKey } from '@/ui/screens/board/useBoardCards';
import { useUsageView } from '@/ui/screens/my/useUsageView';
import { useMarkWatchAdded } from '@/ui/screens/studio/reportView';
import type { ChecklistDraft } from './ChecklistTab';
import { AppNewMemoDialog } from './NewMemoDialog';

export interface NewMemoTarget {
  code: string;
  name: string;
  text?: string;
  /** AI 연결을 켠 채로 */
  ai?: boolean;
  /** 스튜디오 '메모에 추가': 저장해도 보던 화면에 그대로 두고 [보기] 안내. itemId·key 가 있으면 서버 항목에 '추가됨' */
  studio?: { itemId?: string; key?: string };
}

/**
 * 앱 새 메모 = AppNewMemoDialog (항목·동작은 웹 새 메모 창과 같음) 을 아래에서 올라오는 전체 높이 시트로 (메모 쓰기 · 메모에 추가 같이 씀).
 * 실제 모드: 일반 메모로 저장 → AI 를 켰으면 AI 연결 창(/memo/link). '메모에 추가'는 확인·취소 뒤 보던 화면으로 돌아와 안내.
 * mock 모드: 앱 보드와 같은 store/mockBoard. 체크리스트 탭은 새 체크리스트 (앱은 여러 개).
 */
export function NewMemoSheet({ target, onClose, onSaved }: { target: NewMemoTarget | null; onClose: () => void; onSaved?: (code: string) => void }) {
  const router = useRouter();
  const qc = useQueryClient();
  const usage = useUsageView();
  const markWatch = useMarkWatchAdded();
  const toast = useUI((s) => s.showToast);
  /* 닫히는 동안에도 내용이 남아 있게 마지막 대상을 기억 · 열 때마다 새 창 */
  const [last, setLast] = useState<NewMemoTarget | null>(target);
  const [n, setN] = useState(0);
  const [busy, setBusy] = useState(false);
  if (target && target !== last) {
    setLast(target);
    setN(n + 1);
    setBusy(false);
  }
  if (!last) return null;
  const t = last;
  const spent = !env.useMock && (usage.paused || usage.usage_pct >= 100);

  const view = { label: '보기', onPress: () => router.navigate({ pathname: '/stocks/[code]', params: { code: t.code } }) };
  /* link: AI 연결 창으로 이어짐 — 저장 안내는 그 창이 닫힐 때 */
  const studioLink = t.studio ? { board_code: t.code, board_name: t.name, stock_name: t.name } : {};
  const saved = (link = false) => {
    onClose();
    if (t.studio && !link) toast(`${t.name} 보드에 저장했어요`, view);
    onSaved?.(t.code);
  };
  /* 시트(Modal)가 안내를 가리므로 알림 창으로. 시트는 그대로 두어 쓴 글이 남음 */
  const failed = (msg: string) => {
    setBusy(false);
    Alert.alert('', msg);
    toast(msg);
  };
  const save = ({ title, body, color, ai }: { title: string; body: string; color: MemoColor; ai: boolean }) => {
    if (busy) return;
    if (env.useMock) {
      const id = useMockBoard.getState().addMemo(mockKey(t.code), mockBase(t.code), { title, body, color });
      saved(ai);
      if (ai) router.push({ pathname: '/memo/link', params: { id: 'new', title, body, from: 'new', memo_id: id, ...studioLink } });
      else if (!t.studio) toast('메모를 저장했어요');
      return;
    }
    setBusy(true);
    void api.createMemo(t.code, { title, body, color, tags: [], ai_linked: false }).then(
      (m) => {
        setBusy(false);
        void qc.invalidateQueries({ queryKey: qk.board(t.code) });
        if (t.studio) markWatch(t.studio.itemId, t.studio.key, m.id);
        saved(ai);
        if (ai) router.push({ pathname: '/memo/link', params: { id: m.id, from: 'new', ...studioLink } });
        else if (!t.studio) toast('메모를 저장했어요');
      },
      () => failed('메모를 저장하지 못했어요 · 잠시 뒤 다시 해 주세요'),
    );
  };
  const saveChecklist = (d: ChecklistDraft) => {
    if (busy) return;
    const items = d.items.map(({ text, done }) => ({ text, done }));
    const ok = () => {
      saved();
      if (!t.studio) toast('체크리스트를 만들었어요');
    };
    if (env.useMock) {
      useMockBoard.getState().addChecklist(mockKey(t.code), mockBase(t.code), { title: d.title, items });
      return ok();
    }
    setBusy(true);
    void api.createChecklist(t.code, { title: d.title, items }).then(
      () => {
        setBusy(false);
        void qc.invalidateQueries({ queryKey: qk.board(t.code) });
        void qc.invalidateQueries({ queryKey: qk.homeChecklist });
        ok();
      },
      () => failed('체크리스트를 저장하지 못했어요 · 잠시 뒤 다시 해 주세요'),
    );
  };
  return (
    <AppNewMemoDialog
      key={n}
      open={!!target}
      stockName={t.name}
      initialText={t.text}
      initialAi={t.ai}
      aiSpent={spent}
      onSaveChecklist={saveChecklist}
      onEmptyChecklist={() => {
        onClose();
        toast('빈 체크리스트는 저장하지 않았어요');
      }}
      onCancel={onClose}
      onSave={save}
    />
  );
}
