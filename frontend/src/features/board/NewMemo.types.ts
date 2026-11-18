/**
 * 새 메모 (아래에서 올라오는 전체 화면). 입력값은 호스트가 들고 있음(제어 컴포넌트):
 * 상단 바(TopBar left='cancel' · 'SK하이닉스 · 새 메모' · 완료)의 [완료]를 호스트가 처리하기 때문.
 */
export interface NewMemoProps {
  /** 입력 중인 글 (첫 줄 = 제목) */
  value: string;
  onChangeValue: (text: string) => void;
  /** 완료하면 AI 연결 확인(AiLinkConfirm)으로 이어갈지 */
  ai_link: boolean;
  onChangeAiLink: (on: boolean) => void;
  /** 시범 4종목 밖이라 AI 연결을 아직 못 켜는 종목이면 true */
  ai_unavailable?: boolean;
  /** 빈 칸일 때 흐리게 보여 줄 예시 글 (저장되지 않음) */
  placeholder_title: string;
  placeholder_lines: string[];
}
