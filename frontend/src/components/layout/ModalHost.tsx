import React from 'react';
import { BoardItemEditor } from '@/features/board/BoardItemEditor';
import { MemoDetailModal } from '@/features/board/MemoDetailModal';
import { FeedbackModal } from '@/features/feedback/FeedbackModal';
import { SettingsModal } from '@/features/settings/SettingsModal';
import { AddStockModal } from '@/features/stock/AddStockModal';
import { TrashModal } from '@/features/trash/TrashModal';
import { useUI } from '@/store/ui';

/** 전역 모달 렌더러 — useUI().openModal({...}) 로 어디서든 열 수 있습니다 */
export function ModalHost() {
  const modal = useUI((s) => s.modal);
  const close = useUI((s) => s.closeModal);
  if (!modal) return null;
  switch (modal.type) {
    case 'addStock':
      return <AddStockModal onClose={close} />;
    case 'trash':
      return <TrashModal onClose={close} />;
    case 'settings':
      return <SettingsModal onClose={close} initial={modal.section} />;
    case 'feedback':
      return <FeedbackModal onClose={close} initialTab={modal.tab} />;
    case 'newBoardItem':
      return <BoardItemEditor onClose={close} stockCode={modal.stockCode} initialKind={modal.kind ?? 'memo'} />;
    case 'editBoardItem':
      return <BoardItemEditor onClose={close} stockCode={modal.stockCode} itemId={modal.itemId} />;
    case 'memoDetail':
      return <MemoDetailModal onClose={close} stockCode={modal.stockCode} memoId={modal.memoId} initialTab={modal.tab} />;
    default:
      return null;
  }
}
