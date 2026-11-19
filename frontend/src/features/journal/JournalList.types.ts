import type { NativeScrollEvent, NativeSyntheticEvent } from 'react-native';
/** 투자 기록 목록 (최신 IR에서 제품 범위 제외 검토 중인 레거시 화면 · 체험판에 있어 추출만 함) */
export interface JournalNote {
  id: string;
  title: string;
  date_label: string; // '2026. 10. 13.'
  preview: string;
  /** '지난 30일' · '10월' · '9월' 같은 묶음 이름 */
  group: string;
  pinned: boolean;
}

export interface JournalListProps {
  notes: JournalNote[];
  onOpen: (id: string) => void;
  onNew: () => void;
  /** 받아쓰기(마이크) — 기기 음성 입력은 호스트에서 */
  onDictate?: () => void;
  /** 줄을 꾹 누름 → 고르기 (여러 개 고정 · 휴지통) */
  onLongPress?: (id: string) => void;
  /** 줄을 오른쪽으로 밀어 고정 / 고정 해제 */
  onPin?: (id: string, pinned: boolean) => void;
  /** 줄을 왼쪽으로 밀어 드러난 [휴지통] 버튼을 누름 (끝까지 밀어도 바로 지우지 않음) */
  onDelete?: (id: string) => void;
  /** 스크롤 위치를 호스트로 (Lucian #332 큰 제목 접기 · TopBar 아래 선): useLargeTitle().onScroll 을 넘김 */
  onScroll?: (e: NativeSyntheticEvent<NativeScrollEvent>) => void;
}
