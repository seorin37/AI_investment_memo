/** 새 메모 예시 — 체험판과 같은 예시 글(흐리게 보이고 저장되지 않음) */
import type { NewMemoProps } from '@/features/board/NewMemo.types';

export const mockNewMemoProps: NewMemoProps = {
  value: '',
  onChangeValue: () => {},
  ai_link: false,
  onChangeAiLink: () => {},
  placeholder_title: 'HBM 실적 계속 보기',
  placeholder_lines: ['다음 정기보고서에서 HBM 매출 비중 확인하기', '종가 ○○만원 아래로 내려오면 다시 보기'],
};

/** 빈 보드 예시 칩으로 연 경우: 그 문장이 첫 줄 */
export const mockNewMemoFromExample: NewMemoProps = { ...mockNewMemoProps, value: '많이 빠지면 다시 생각해 보기\n' };
