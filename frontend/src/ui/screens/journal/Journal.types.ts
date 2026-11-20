/** 기록 한 줄의 글 모양 (원본 앱 #ned .b[data-s] · 웹 h1/h2/h3/p) */
export type JBlockStyle = 'title' | 'head' | 'sub' | 'body';

/** 기록 안의 한 줄. check 가 있으면 체크리스트 줄 (true = 끝냄) */
export interface JBlock {
  s: JBlockStyle;
  text: string;
  check?: boolean;
}

/**
 * 투자 기록 하나 (사용자가 직접 쓰는 일지 · AI 연결 없음)
 * 날짜 글자·묶음 이름은 mock 에 적어 둠 — 연결 단계에서 created_at·updated_at 으로 계산
 */
export interface JournalEntry {
  id: string;
  /** 첫 줄 = 제목 (비면 '새로운 기록') */
  title: string;
  /** 앱 목록 날짜 '2026. 10. 13.' (원본 n.d) */
  date: string;
  /** 웹 목록 날짜 '10월 13일' (원본 j.date) */
  web_date: string;
  /** 기록 화면 위 날짜 '2026년 10월 13일 오후 6:20' (원본 n.full) */
  full: string;
  /** 날짜 묶음 이름 '오늘' · '지난 30일' · '10월' … (원본 n.g) */
  group: string;
  pinned: boolean;
  blocks: JBlock[];
}

export interface JournalProps {
  entries: JournalEntry[];
  onOpen: (id: string) => void;
  onNew: () => void;
  /** 고정 / 고정 풀기 (여러 개) */
  onPin: (ids: string[], on: boolean) => void;
  /** 휴지통으로 옮기기 (되돌리기 가능 · 영구 삭제 없음) */
  onTrash: (ids: string[]) => void;
  /** 되돌리기 — 옮기기 전 목록 그대로 */
  onRestore: (entries: JournalEntry[]) => void;
}
